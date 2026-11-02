#!/usr/bin/env python3
"""Fluxo diário: Gmail -> mensagens humanas -> fila de envio do WhatsApp.

  python3 rodar_dia.py                 # execução normal (cron, seg a sáb, 07:45)
  python3 rodar_dia.py --teste         # manda TUDO só para o número do admin, com aviso de teste
  python3 rodar_dia.py --dry           # gera e mostra, sem enfileirar nada
  python3 rodar_dia.py --data 2026-10-31 --so 031,026 --forcar

Regras:
- Metas + orçamentos saem entre 08:00 e 08:15; a cobrança das 17:00 sai entre 17:00 e 17:15 (janela do robô: 08:00-18:00).
- Falta algum dos 2 e-mails: avisa o admin e não manda nada a ninguém.
- Vendedor que não está no relatório (ou está sem faturamento e sem atendimentos): não recebe nada.
- Vendedor sem número em vendedores.json: pulado e listado no aviso ao admin.
"""
import argparse
import calendar
import json
import os
import random
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import buscar_emails as be  # noqa: E402
import gerar_mensagens as g  # noqa: E402
import humanizar as h  # noqa: E402
import semana as sem  # noqa: E402
import feriados as fer  # noqa: E402

ADMIN = "5511900000000"
BRT = timezone(timedelta(hours=-3))
VENDEDORES = os.path.join(AQUI, "vendedores.json")
SNAP = os.path.join(AQUI, "dados_diarios.json")
ENVIADOS = os.path.join(AQUI, "enviados.json")
PASTA = os.path.join(AQUI, "relatorios")
LOGS = os.path.join(AQUI, "logs")
DIA = None  # data da execução (AAAA-MM-DD), usada no log de envios


def pausado():
    """True se os envios aos vendedores estão pausados (página /whatsapp/pausa/)."""
    r = subprocess.run(["docker", "exec", "-i", "wa-stack-postgres-1", "psql", "-U", "postgres", "-d", "wa", "-tA", "-c",
                        "select valor from config where chave='envio_pausado'"], capture_output=True, text=True)
    return r.stdout.strip() == "sim"


def normalizar_numero(txt):
    """Devolve o número no formato do robô (55 + DDD + número) ou None se for inválido."""
    d = "".join(c for c in str(txt) if c.isdigit())
    if len(d) in (10, 11):
        d = "55" + d
    return d if len(d) in (12, 13) and d.startswith("55") else None


def cadastrados():
    """{últimos 8 dígitos + DDD: (grupo, ativo)} dos contatos do robô. A limpeza apaga o que não for cadastrado."""
    r = subprocess.run(["docker", "exec", "-i", "wa-stack-postgres-1", "psql", "-U", "postgres", "-d", "wa", "-tA", "-F", "|", "-c",
                        "select numero, grupo, ativo from contacts"], capture_output=True, text=True, check=True)
    out = {}
    for ln in r.stdout.splitlines():
        n, g_, a_ = ln.split("|")
        out[(n[2:4], n[-8:])] = (g_, a_ == "t")
    return out


def whatsapp_conectado():
    import urllib.request
    try:
        return json.load(urllib.request.urlopen("http://127.0.0.1:8110/saude", timeout=15)).get("estado") == "open"
    except Exception:
        return False


def ja_agendado(data, cod, tipo):
    r = subprocess.run(["docker", "exec", "-i", "wa-stack-postgres-1", "psql", "-U", "postgres", "-d", "wa", "-tA", "-v", f"d={data}",
                        "-v", f"c={cod}", "-v", f"t={tipo}"], input="select count(*) from sales_rep_messages where data=:'d'::date and cod=:'c' and tipo=:'t'",
                       capture_output=True, text=True, check=True)
    return int(r.stdout.strip() or 0) > 0


def carregar(caminho, padrao):
    try:
        return json.load(open(caminho, encoding="utf-8"))
    except Exception:
        return padrao


def dias_mes(d):
    """(dias de trabalho no mês, dias restantes contando hoje), de segunda a sábado, sem feriados."""
    ult = calendar.monthrange(d.year, d.month)[1]
    fer_ano = fer.feriados(d.year)
    todos = [date(d.year, d.month, x) for x in range(1, ult + 1)
             if date(d.year, d.month, x).weekday() < 6 and date(d.year, d.month, x) not in fer_ano]
    return len(todos), len([x for x in todos if x >= d])


def enfileirar(numero, texto, quando, dry=False, log=None):
    """Coloca na fila de envio. `log` = (cod, nome, tipo) grava também no log de envios (tabela + arquivo)."""
    if dry:
        return None
    if log and log[2] not in ("aviso", "resumo", "entrega", "conferencia") and ja_agendado(DIA, log[0], log[2]):
        print(f"  já agendado hoje: {log[1]} ({log[2]}), não repito.")
        return None
    if log:
        sql = ("with f as (insert into send_queue(numero,texto,liberar_em) values (:'n', :'t', :'q'::timestamptz) returning id) "
               "insert into sales_rep_messages(data,cod,nome,numero,tipo,fila_id,agendado_para) "
               "select :'d'::date, :'c', :'nm', :'n', :'tp', f.id, :'q'::timestamptz from f returning fila_id")
        extra = ["-v", f"d={DIA}", "-v", f"c={log[0]}", "-v", f"nm={log[1]}", "-v", f"tp={log[2]}"]
    else:
        sql = "insert into send_queue(numero,texto,liberar_em) values (:'n', :'t', :'q'::timestamptz) returning id"
        extra = []
    r = subprocess.run(["docker", "exec", "-i", "wa-stack-postgres-1", "psql", "-U", "postgres", "-d", "wa", "-tA", "-v", "ON_ERROR_STOP=1",
                        "-v", f"n={numero}", "-v", f"t={texto}", "-v", f"q={quando.isoformat()}"] + extra,
                       input=sql, text=True, check=True, capture_output=True)
    fila_id = (r.stdout.strip().splitlines() or [""])[0]
    if log:
        os.makedirs(LOGS, exist_ok=True)
        with open(os.path.join(LOGS, "envios.jsonl"), "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"registrado": datetime.now(BRT).isoformat(timespec="seconds"), "data": DIA, "cod": log[0], "nome": log[1],
                                 "tipo": log[2], "numero": numero, "agendado_para": quando.isoformat(), "fila_id": fila_id}, ensure_ascii=False) + "\n")
    return fila_id


def aviso(texto, quando, dry):
    enfileirar(ADMIN, "🤖 *Aviso do envio diário*\n\n" + texto, quando, dry, ("admin", "Funcionário 7", "aviso"))
    print("AVISO ao admin:", texto)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=None)
    ap.add_argument("--teste", action="store_true")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--forcar", action="store_true")
    ap.add_argument("--so", default=None, help="códigos separados por vírgula")
    ap.add_argument("--relatorio-de", default=None, help="usa os e-mails desta data (AAAA-MM-DD), p/ simular")
    a = ap.parse_args()

    global DIA
    hoje = date.fromisoformat(a.data) if a.data else datetime.now(BRT).date()
    chave = DIA = hoje.isoformat()
    base_manha = datetime(hoje.year, hoje.month, hoje.day, 8, 0, tzinfo=BRT)
    # sábado a loja só funciona das 8h às 12h: a cobrança sai às 11h (às 17h nos outros dias)
    sabado = hoje.weekday() == 5
    base_tarde = datetime(hoje.year, hoje.month, hoje.day, 11 if sabado else 17, 0, tzinfo=BRT)
    if datetime.now(BRT) > base_manha and not a.data:
        base_manha = datetime.now(BRT) + timedelta(seconds=30)  # rodou atrasado: envia já (a janela do robô protege)
    if hoje.weekday() == 6:
        print("Domingo: nada a fazer.")
        return
    feriado = fer.nome_do_feriado(hoje)
    if feriado and not a.forcar:
        aviso(f"Hoje é feriado ({feriado}). Não enviei mensagens aos vendedores.", base_manha, a.dry)
        return
    if pausado() and not a.forcar:
        aviso("Os envios aos vendedores estão PAUSADOS (página /whatsapp/pausa/). Hoje não agendei nada.", base_manha, a.dry)
        return
    enviados = carregar(ENVIADOS, {})
    if enviados.get(chave) and not (a.forcar or a.dry or a.teste):
        print("Já enviado hoje. Use --forcar para repetir.")
        return

    # 1) relatórios do Gmail
    pasta = os.path.join(PASTA, chave)
    try:
        achados = be.baixar(a.relatorio_de or chave, pasta)
    except Exception as e:
        aviso(f"Não consegui ler o Gmail ({e}). Nenhuma mensagem foi enviada aos vendedores hoje.", base_manha, a.dry)
        sys.exit(1)
    faltam = [n for n in ("meta", "orcamentos") if n not in achados]
    if faltam:
        nomes = {"meta": "META POR VENDEDOR 3.0", "orcamentos": "ORÇAMENTOS PENDENTES"}
        aviso("O e-mail de " + " e ".join(nomes[x] for x in faltam) + f" de {hoje:%d/%m} não chegou. "
              "Nenhuma mensagem foi enviada aos vendedores hoje.", base_manha, a.dry)
        sys.exit(1)

    if not a.dry and not whatsapp_conectado() and not a.forcar:
        aviso("O WhatsApp do robô não está conectado (precisa reler o QR). Não agendei nada aos vendedores.", base_manha, False)
        sys.exit(1)

    # 2) dados
    relatorio = g.ler_pdf(achados["meta"])
    orc = g.ler_orcamentos(achados["orcamentos"])
    if not relatorio:
        aviso("O relatório de metas veio sem nenhum vendedor. Nada foi enviado.", base_manha, a.dry)
        sys.exit(1)
    # confere se a leitura do PDF pegou todos os registros que ele declara (layout mudou? linha quebrada?)
    docs = g.ler_orcamentos_docs(achados["orcamentos"])
    lidos = {"metas": (len(relatorio), g.total_impresso(achados["meta"])),
             "orçamentos": (sum(len(x) for x in docs.values()), g.total_impresso(achados["orcamentos"]))}
    erros = [f"{k}: li {a_} e o PDF declara {b_}" for k, (a_, b_) in lidos.items() if b_ is not None and a_ != b_]
    if erros:
        aviso("A leitura dos relatórios não bateu com o total do PDF (" + "; ".join(erros) + "). "
              "Não enviei nada aos vendedores para não mandar dados errados. Pode ser mudança no layout do relatório.", base_manha, a.dry)
        sys.exit(1)
    equipe = h.media_equipe(relatorio)
    total, restantes = dias_mes(hoje)
    snaps = carregar(SNAP, {})
    anteriores = sorted(k for k in snaps if k < chave)
    ontem = snaps[anteriores[-1]] if anteriores else {}
    hist = h.historico()
    cadastro = {x["cod"]: x for x in carregar(VENDEDORES, [])}
    so = set(a.so.split(",")) if a.so else None

    # 3) mensagens por vendedor
    manha, tarde, sem_numero, ausentes, pulados = [], [], [], [], []
    invalidos, nao_cadastrados = [], []
    por_cod = {v["cod"]: v for v in relatorio}
    for cod, cad in cadastro.items():
        if so and cod not in so:
            continue
        v = por_cod.get(cod)
        if not v or (v["fat"] == 0 and v["atend"] == 0):
            ausentes.append(cad["nome"])
            continue
        if not cad.get("numero") and not a.teste:
            sem_numero.append(cad["nome"])
            continue
        numero = ADMIN if a.teste else normalizar_numero(cad["numero"])
        if not numero:
            invalidos.append(cad["nome"])
            continue
        if not a.teste and not a.dry:
            reg = cadastrados().get((numero[2:4], numero[-8:]))
            if not reg or not reg[1]:
                nao_cadastrados.append(cad["nome"])
                continue
        if cod in ontem:
            v["_ontem"] = ontem[cod]
        abaixo, duro = h.nivel_tom(v, equipe, total, restantes)  # 'duro', 'firme', 'normal' ou 'bem'
        v["_comparativo"] = h.comparativo(v, equipe) if duro != "normal" else None
        dia = min(hoje.weekday(), 5)
        lista = orc.get(cod, [])
        v["_tem_lista"] = bool(lista)
        semana = sem.compilar(hoje, cod) if hoje.weekday() == 0 else None
        m = h.texto_metas(v, restantes, f"{hoje:%d/%m/%Y}", dia, hist, abaixo, duro, semana) or g.mensagem(v, restantes, f"{hoje:%d/%m/%Y}", lista, duro, sabado)
        o = f = None
        if lista:
            t = h.texto_com_lista(v, lista, dia, hist, "orcamentos", duro)
            o = t.replace(h.MARCA, h.linhas_lista(lista, True)) if t else g.mensagem_orcamentos(v, lista, sabado)
            top5 = lista[:5]  # a cobrança do fim do dia é só sobre os 5 maiores (a lista já vem ordenada por valor)
            t = h.texto_com_lista(v, top5, dia, hist, "followup", duro)
            f = t.replace(h.MARCA, h.linhas_lista(top5, False)) if t else g.followup(v, top5, sabado)
        pre = f"🧪 *TESTE – {cad['nome']}*\n\n" if a.teste else ""
        manha.append((numero, cad["nome"], pre + m, (pre + o) if o else None, duro, cod))
        if f:
            tarde.append((numero, cad["nome"], pre + f, cod))
        h.lembrar(hist, cod, "metas", m)
        if o:
            h.lembrar(hist, cod, "orcamentos", o)
        if f:
            h.lembrar(hist, cod, "followup", f)
        print(f"  {cad['nome']}: ok{' (tom ' + duro + ')'}{'' if lista else ' (sem orçamentos)'}")

    # 4) fila: manhã entre 08:00 e 08:30 (espaçada, p/ evitar bloqueio); cobrança em até 15 min
    pre_t = "teste-" if a.teste else ""
    random.shuffle(manha)
    random.shuffle(tarde)
    passo = max(60, 1380 // max(len(manha), 1))
    for i, (num, nome, m, o, duro, cod) in enumerate(manha):
        t0 = base_manha + timedelta(seconds=i * passo + random.randint(0, 20))
        enfileirar(num, m, t0, a.dry, (cod, nome, pre_t + "metas"))
        if o:
            enfileirar(num, o, t0 + timedelta(seconds=random.randint(45, 100)), a.dry, (cod, nome, pre_t + "orcamentos"))
    passo = max(30, (540 if sabado else 840) // max(len(tarde), 1))
    for i, (num, nome, f, cod) in enumerate(tarde):
        enfileirar(num, f, base_tarde + timedelta(seconds=i * passo + random.randint(0, 8)), a.dry, (cod, nome, pre_t + "cobranca"))

    # 5) resumo ao admin
    linhas = [f"{len(manha)} vendedor(es) vão receber as mensagens de hoje (08:00 a 08:30) e a cobrança das " + ("11h" if sabado else "17h") + "."]
    if sem_numero:
        linhas.append("Sem número cadastrado, não receberam: " + ", ".join(sem_numero) + ".")
    if invalidos:
        linhas.append("Número inválido no cadastro, não receberam: " + ", ".join(invalidos) + ".")
    if nao_cadastrados:
        linhas.append("Não estão cadastrados no robô (grupo vendedores), não receberam: " + ", ".join(nao_cadastrados) + ".")
    if ausentes:
        linhas.append("Fora do relatório de hoje, não receberam nada: " + ", ".join(ausentes) + ".")
    desconhecidos = [v["nome"] for v in relatorio if v["cod"] not in cadastro]
    if desconhecidos:
        linhas.append("No relatório mas não cadastrados: " + ", ".join(x.split()[0] for x in desconhecidos) + ".")
    aviso("\n".join(linhas), base_manha - timedelta(seconds=1) if not a.dry else base_manha, a.dry)

    if not a.dry:
        snaps[chave] = {v["cod"]: {"fat": v["fat"], "pct_alc": v["pct_alc"], "mar": v["mar"], "ticket": v["ticket"]} for v in relatorio}
        json.dump(snaps, open(SNAP, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        json.dump(hist, open(h.HIST, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        if not a.teste:
            enviados[chave] = True
            json.dump(enviados, open(ENVIADOS, "w", encoding="utf-8"), indent=1)
    if a.dry:
        json.dump({"manha": manha, "tarde": tarde}, open(os.path.join(AQUI, "ultimo_dry.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print("dry-run salvo em ultimo_dry.json")


if __name__ == "__main__":
    DIA = datetime.now(BRT).date().isoformat()
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:  # erro inesperado: registra e avisa o admin
        import traceback
        os.makedirs(LOGS, exist_ok=True)
        with open(os.path.join(LOGS, "erros.log"), "a", encoding="utf-8") as fh:
            fh.write(f"{datetime.now(BRT).isoformat(timespec='seconds')}\n{traceback.format_exc()}\n")
        try:
            aviso(f"O envio diário falhou com um erro inesperado ({type(e).__name__}: {str(e)[:160]}). "
                  "Parte das mensagens pode já ter sido agendada: confira o log de envios. Se precisar, pause em /whatsapp/pausa/.",
                  datetime.now(BRT) + timedelta(seconds=10), False)
        except Exception:
            pass
        sys.exit(1)
