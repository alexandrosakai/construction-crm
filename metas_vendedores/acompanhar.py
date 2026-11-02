#!/usr/bin/env python3
"""Acompanhamento dos envios aos vendedores (tudo vai só para o admin).

  python3 acompanhar.py entrega   # ~09:00: se alguma mensagem da manhã não chegou, manda relatório ao admin
  python3 acompanhar.py resumo    # 17:49 (sábado 11:49): resumo do dia + interações dos vendedores

Opções: --data AAAA-MM-DD  --dry (só mostra)  --incluir-testes  --sempre (entrega: manda mesmo sem problema)
Entrega: usa a fila (fila_envio) + os avisos de entrega que a Evolution guarda (SERVER_ACK -> DELIVERY_ACK -> READ).
"""
import argparse
import json
import subprocess
import sys
import os
from datetime import date, datetime, timedelta

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import humanizar as h  # noqa: E402
import rodar_dia as rd  # noqa: E402
import relatorio_email as rem  # noqa: E402

TIPOS = {"metas": "metas", "orcamentos": "orçamentos", "cobranca": "cobrança"}
RANK = "case {c} when 'PLAYED' then 5 when 'READ' then 4 when 'DELIVERY_ACK' then 3 when 'SERVER_ACK' then 2 else 1 end"


def consulta(db, sql, **v):
    """Roda um SELECT e devolve a lista de dicts (o SELECT vira JSON no próprio banco)."""
    args = ["docker", "exec", "-i", "wa-stack-postgres-1", "psql", "-U", "postgres", "-d", db, "-tA", "-v", "ON_ERROR_STOP=1"]
    for k, val in v.items():
        args += ["-v", f"{k}={val}"]
    r = subprocess.run(args, input=f"select coalesce(jsonb_agg(t), '[]'::jsonb) from ({sql}) t", text=True, capture_output=True, check=True)
    return json.loads(r.stdout.strip().splitlines()[0])


def r8(numero):
    d = "".join(c for c in str(numero) if c.isdigit())
    return d[-8:]


def envios_do_dia(dia, testes):
    rows = consulta("wa", """
        select e.id, e.cod, e.nome, e.numero, e.tipo, e.fila_id, f.status, f.erro, f.tentativas, f.texto,
               extract(epoch from f.enviado_em)::bigint as env_ts, extract(epoch from e.agendado_para)::bigint as ag_ts
        from sales_rep_messages e left join send_queue f on f.id = e.fila_id
        where e.data = :'d' and e.tipo !~ '^(aviso|resumo|entrega|conferencia)$' order by e.id""", d=dia)
    out = []
    for x in rows:
        teste = x["tipo"].startswith("teste-")
        if teste and not testes:
            continue
        x["tipo"] = x["tipo"].replace("teste-", "")
        out.append(x)
    return out


def situacao(envios, dia):
    """Acrescenta a cada envio: estado = entregue | lida | sem_confirmacao | nao_enviada | na_fila."""
    ini = int(datetime.fromisoformat(f"{dia}T00:00:00").replace(tzinfo=rd.BRT).timestamp())
    evo = consulta("evolution", f"""
        select m.id, right(regexp_replace(coalesce(m.key->>'remoteJidAlt', m.key->>'remoteJid'), '\\D', '', 'g'), 8) as r8,
               m."messageTimestamp" as ts,
               greatest({RANK.format(c='m.status')},
                        coalesce((select max({RANK.format(c='u.status')}) from "MessageUpdate" u where u."messageId" = m.id), 1)) as rk
        from "Message" m where m.key->>'fromMe' = 'true' and m."messageTimestamp" >= :ini""", ini=ini)
    usados = set()
    for e in envios:
        if e["status"] == "erro" and e["erro"] in ("PAUSADO", "CANCELADO"):
            e["estado"] = "pausada"
        elif e["status"] == "erro":
            e["estado"] = "nao_enviada"
        elif e["status"] != "enviado":
            e["estado"] = "na_fila"
        else:
            cand = [m for m in evo if m["r8"] == r8(e["numero"]) and abs(m["ts"] - (e["env_ts"] or 0)) <= 240 and m["id"] not in usados]
            if not cand:
                e["estado"] = "sem_confirmacao"
                continue
            m = min(cand, key=lambda m: abs(m["ts"] - e["env_ts"]))
            usados.add(m["id"])
            e["estado"] = "lida" if m["rk"] >= 4 else "entregue" if m["rk"] == 3 else "sem_confirmacao"
    return envios


def contagem(envios):
    c = {k: 0 for k in ("lida", "entregue", "sem_confirmacao", "nao_enviada", "na_fila", "pausada")}
    for e in envios:
        c[e["estado"]] += 1
    return c


def problemas(envios):
    L = []
    nao = [e for e in envios if e["estado"] == "nao_enviada"]
    fila = [e for e in envios if e["estado"] == "na_fila"]
    paus = [e for e in envios if e["estado"] == "pausada"]
    sem = [e for e in envios if e["estado"] == "sem_confirmacao"]
    hora = lambda e: datetime.fromtimestamp(e["env_ts"] or e["ag_ts"], rd.BRT).strftime("%H:%M")
    if nao:
        L.append("❌ *Não enviadas:*")
        L += [f"• {e['nome']} ({TIPOS.get(e['tipo'], e['tipo'])}, {hora(e)}): {(e['erro'] or 'erro no envio')[:120]}" for e in nao]
    if fila:
        L.append("⏳ *Ainda na fila:*")
        L += [f"• {e['nome']} ({TIPOS.get(e['tipo'], e['tipo'])}, previsto {hora(e)})" for e in fila]
    if paus:
        L.append("⏸️ *Pausadas ou descartadas por você:*")
        L += [f"• {e['nome']} ({TIPOS.get(e['tipo'], e['tipo'])}, previsto {hora(e)})" for e in paus]
    if sem:
        L.append("⚠️ *Enviadas, mas sem confirmação de entrega* (o celular do vendedor pode estar desligado ou sem internet):")
        L += [f"• {e['nome']} ({TIPOS.get(e['tipo'], e['tipo'])}, {hora(e)})" for e in sem]
    return L


def hora(e):
    return datetime.fromtimestamp(e["env_ts"] or e["ag_ts"], rd.BRT).strftime("%H:%M")


def tabela_entrega(env):
    """Uma linha por vendedor, uma coluna por tipo de mensagem."""
    pv = {}
    for e in env:
        d = pv.setdefault(e["cod"], {"nome": e["nome"], "metas": "–", "orcamentos": "–", "cobranca": "–"})
        cor = rem.COR[e["estado"]]
        d[e["tipo"]] = ("html", f'<span style="color:{cor};font-weight:600">{rem.ROT[e["estado"]]}</span> <span style="color:#5D6B72">({hora(e)})</span>')
    linhas = [[d["nome"], d["metas"], d["orcamentos"], d["cobranca"]] for d in sorted(pv.values(), key=lambda x: x["nome"])]
    return rem.tabela(["Vendedor", "Metas", "Orçamentos", "Cobrança"], linhas)


def csv_envios(env):
    return rem.csv_texto(["vendedor", "codigo", "tipo", "agendado_para", "enviado_em", "estado", "erro"],
                         [[e["nome"], e["cod"], e["tipo"], datetime.fromtimestamp(e["ag_ts"], rd.BRT).strftime("%d/%m/%Y %H:%M"),
                           datetime.fromtimestamp(e["env_ts"], rd.BRT).strftime("%d/%m/%Y %H:%M") if e["env_ts"] else "",
                           rem.ROT[e["estado"]], e["erro"] or ""] for e in env])


def kpis_envio(env, extra=()):
    c = contagem(env)
    ok = c["lida"] + c["entregue"]
    k = [rem.kpi(len(env), "mensagens"), rem.kpi(ok, "entregues", "#1F7A45")]
    if c["sem_confirmacao"]:
        k.append(rem.kpi(c["sem_confirmacao"], "sem confirmação", "#9A5B00"))
    if c["nao_enviada"]:
        k.append(rem.kpi(c["nao_enviada"], "não enviadas", "#B42318"))
    if c["na_fila"]:
        k.append(rem.kpi(c["na_fila"], "na fila"))
    if c["pausada"]:
        k.append(rem.kpi(c["pausada"], "pausadas"))
    return k + list(extra)


def lista_problemas_html(env):
    ruins = [e for e in env if e["estado"] in ("nao_enviada", "sem_confirmacao", "na_fila", "pausada")]
    if not ruins:
        return ""
    linhas = [[e["nome"], TIPOS.get(e["tipo"], e["tipo"]), hora(e),
               ("html", f'<span style="color:{rem.COR[e["estado"]]};font-weight:600">{rem.ROT[e["estado"]]}</span>'),
               (e["erro"] or "") if e["estado"] == "nao_enviada" else ""] for e in ruins]
    return rem.tabela(["Vendedor", "Mensagem", "Hora", "Situação", "Detalhe"], linhas)


def entrega(dia, dry, testes, sempre):
    env = situacao(envios_do_dia(dia, testes), dia)
    if not env:
        print("Nenhum envio a vendedores neste dia.")
        return
    c = contagem(env)
    ruins = problemas(env)
    ok = c["lida"] + c["entregue"]
    if not ruins and not sempre:
        print(f"Tudo entregue ({ok}/{len(env)}). Sem relatório.")
        return
    d = date.fromisoformat(dia)
    n_ruins = len(env) - ok
    pagina = rem.pagina("Relatório de entrega", f"Mensagens aos vendedores, {d:%d/%m/%Y}", kpis_envio(env),
                        [("Problemas encontrados", lista_problemas_html(env)), ("Situação por vendedor", tabela_entrega(env))])
    assunto = f"{'⚠️ ' if ruins else '✅ '}Entrega aos vendedores {d:%d/%m}: {n_ruins} com problema" if ruins else f"✅ Entrega aos vendedores {d:%d/%m}: tudo certo"
    cab = (f"{'⚠️' if ruins else '✅'} *Relatório de entrega, {d:%d/%m}*\n\nDe {len(env)} mensagens aos vendedores: {ok} entregues"
           + (f", {c['sem_confirmacao']} sem confirmação" if c["sem_confirmacao"] else "")
           + (f", {c['nao_enviada']} não enviadas" if c["nao_enviada"] else "")
           + (f", {c['na_fila']} ainda na fila" if c["na_fila"] else "") + ".")
    enviar_relatorio(assunto, pagina, [(f"envios-{dia}.csv", csv_envios(env))], dia, dry, "entrega", cab + "\n\n" + "\n".join(ruins), cab)


def enviar_relatorio(assunto, pagina, anexos, dia, dry, tipo, zap_completo, zap_curto):
    """E-mail estruturado (tabelas + CSV). No WhatsApp vai a versão curta; se o e-mail falhar, vai a completa."""
    if dry:
        print("E-MAIL (não enviado) | assunto:", assunto, "| anexos:", [a[0] for a in anexos], "| html:", len(pagina), "bytes")
        enviar(zap_curto + "\n\n📧 O relatório completo foi enviado para o seu e-mail.", dia, True, tipo)
        return
    try:
        rem.enviar(assunto, pagina, anexos)
        print("E-mail enviado.")
        enviar(zap_curto + "\n\n📧 O relatório completo foi enviado para o seu e-mail.", dia, False, tipo)
    except Exception as e:
        print("Falha no e-mail:", e)
        enviar(zap_completo + f"\n\n(Não consegui enviar o e-mail: {str(e)[:80]})", dia, False, tipo)


def interacoes(dia, numeros):
    ini = int(datetime.fromisoformat(f"{dia}T00:00:00").replace(tzinfo=rd.BRT).timestamp())
    rows = consulta("evolution", r"""
        select right(regexp_replace(coalesce(m.key->>'senderPn', m.key->>'remoteJidAlt', m.key->>'remoteJid'), '\D', '', 'g'), 8) as r8,
               m."messageTimestamp" as ts, m."messageType" as tp,
               coalesce(m.message->>'conversation', m.message->'extendedTextMessage'->>'text',
                        m.message->'imageMessage'->>'caption', m.message->'videoMessage'->>'caption', '') as txt,
               m.message->'audioMessage'->>'seconds' as secs
        from "Message" m where m.key->>'fromMe' = 'false' and m."messageTimestamp" >= :ini
          and m.key->>'remoteJid' not like '%@g.us'
          and m."messageType" not in ('reactionMessage', 'protocolMessage', 'senderKeyDistributionMessage', 'messageContextInfo') order by 2""", ini=ini)
    alvo = {r8(n) for n in numeros}
    return [x for x in rows if x["r8"] in alvo]


def descrever(msg):
    hora = datetime.fromtimestamp(msg["ts"], rd.BRT).strftime("%H:%M")
    if msg["txt"]:
        return f"{hora} {msg['txt'][:300]}"
    tipo = {"audioMessage": f"áudio de {msg['secs'] or '?'}s (não transcrito)", "imageMessage": "imagem", "videoMessage": "vídeo",
            "documentMessage": "documento", "stickerMessage": "figurinha"}.get(msg["tp"], msg["tp"])
    return f"{hora} [{tipo}]"


def resumo(dia, dry, testes):
    env = situacao(envios_do_dia(dia, testes), dia)
    if not env:
        print("Nenhum envio a vendedores neste dia. Sem resumo.")
        return
    vend = {}
    for e in env:
        vend.setdefault(e["cod"], {"nome": e["nome"], "numero": e["numero"], "cobranca": None})
        if e["tipo"] == "cobranca":
            vend[e["cod"]]["cobranca"] = e["texto"]
    msgs = interacoes(dia, [v["numero"] for v in vend.values()])
    por_vend = {}
    for cod, v in vend.items():
        mine = [(m, descrever(m)) for m in msgs if m["r8"] == r8(v["numero"])]
        if mine:
            por_vend[cod] = {"vendedor": v["nome"], "cobranca_enviada": v["cobranca"], "mensagens_recebidas": [d for _, d in mine], "_msgs": [m for m, _ in mine]}
    linha_ia = {}
    if por_vend:
        sistema = ("Você resume, para o gestor, o que cada vendedor respondeu hoje no WhatsApp. Para cada vendedor, escreva UMA linha começando por "
                   "'• Nome:' (até 230 caracteres) dizendo o que ele informou. Quando a cobrança tiver clientes numerados e ele responder por número "
                   "(ex.: '1 fechou, 2 liguei'), traduza para o nome do cliente. Use SOMENTE o que está nas mensagens. Áudios e imagens sem texto: diga que "
                   "mandou e que o conteúdo não foi lido. Não invente nada, não opine, sem emojis. Responda só com as linhas.")
        t = h.claude(sistema, json.dumps([{k: x for k, x in v.items() if k != "_msgs"} for v in por_vend.values()], ensure_ascii=False, indent=1))
        for ln in (t or "").splitlines():
            if ln.startswith("•") and ":" in ln:
                nome, resto = ln[1:].split(":", 1)
                linha_ia[nome.strip().lower()] = resto.strip()
    c = contagem(env)
    ok = c["lida"] + c["entregue"]
    d = date.fromisoformat(dia)
    sem = sorted(v["nome"] for cod, v in vend.items() if cod not in por_vend)
    # ---- e-mail estruturado
    linhas_int = []
    for cod, v in sorted(por_vend.items(), key=lambda kv: kv[1]["vendedor"]):
        resumo_ia = linha_ia.get(v["vendedor"].lower()) or linha_ia.get(v["vendedor"].split()[0].lower()) or "(sem resumo)"
        linhas_int.append([v["vendedor"], resumo_ia, "\n".join(v["mensagens_recebidas"])])
    bloco_int = rem.tabela(["Vendedor", "Resumo", "Mensagens recebidas (hora e texto)"], linhas_int) if linhas_int else ""
    bloco_sem = f'<p>{", ".join(rem.E(n) for n in sem)}</p>' if sem else ""
    pagina = rem.pagina("Resumo do dia, vendedores", f"{d:%A, %d/%m/%Y}".capitalize(),
                        kpis_envio(env, [rem.kpi(f"{len(por_vend)}/{len(vend)}", "interagiram", "#1e3a8a")]),
                        [("Problemas de entrega", lista_problemas_html(env)), ("Interações dos vendedores", bloco_int),
                         ("Sem interação hoje", bloco_sem), ("Situação das mensagens por vendedor", tabela_entrega(env))])
    csv_int = rem.csv_texto(["vendedor", "hora", "tipo", "texto"],
                            [[v["vendedor"], datetime.fromtimestamp(m["ts"], rd.BRT).strftime("%H:%M"), m["tp"], m["txt"] or (f"audio {m['secs']}s" if m["secs"] else "")]
                             for v in por_vend.values() for m in v["_msgs"]])
    # ---- WhatsApp (completo, se o e-mail falhar; curto, se funcionar)
    Z = [f"📊 *Resumo do dia, vendedores ({d:%d/%m})*", "",
         f"Mensagens: {len(env)} enviadas ao todo, {ok} entregues"
         + (f", {c['sem_confirmacao']} sem confirmação" if c["sem_confirmacao"] else "")
         + (f", {c['nao_enviada']} não enviadas" if c["nao_enviada"] else "") + ".",
         f"Interagiram: {len(por_vend)} de {len(vend)} vendedores."]
    if por_vend:
        Z += ["", *[f"• {v['vendedor']}: {linha_ia.get(v['vendedor'].lower()) or linha_ia.get(v['vendedor'].split()[0].lower()) or str(len(v['mensagens_recebidas'])) + ' mensagem(ns)'}" for v in por_vend.values()]]
    if sem:
        Z += ["", "Sem interação: " + ", ".join(sem) + "."]
    ruins = problemas(env)
    if ruins:
        Z += ["", *ruins]
    completo = "\n".join(Z)
    curto = "\n".join(Z[:5] + (["", "Sem interação: " + ", ".join(sem) + "."] if sem else []) + (["", f"⚠️ {len(env) - ok} mensagem(ns) com problema de entrega."] if len(env) - ok else []))
    enviar_relatorio(f"📊 Resumo do dia dos vendedores, {d:%d/%m}: {len(por_vend)}/{len(vend)} interagiram", pagina,
                     [(f"envios-{dia}.csv", csv_envios(env)), (f"interacoes-{dia}.csv", csv_int)], dia, dry, "resumo", completo, curto)


def enviar(texto, dia, dry, tipo):
    print("\n" + texto + "\n")
    if dry:
        print("(dry: não enfileirado)")
        return
    rd.DIA = dia
    rd.enfileirar(rd.ADMIN, texto, datetime.now(rd.BRT) + timedelta(seconds=5), False, ("admin", "Funcionário 7", tipo))
    print("Enfileirado para o admin.")


def conferir(dia, dry):
    """~08:10: se hoje é dia útil e nada foi agendado (nem aviso), alerta o admin."""
    d = date.fromisoformat(dia)
    if d.weekday() == 6 or rd.fer.nome_do_feriado(d):
        print("Domingo ou feriado: nada a conferir.")
        return
    n = consulta("wa", "select count(*)::int as n from sales_rep_messages where data = :'d' and tipo in ('metas', 'aviso')", d=dia)[0]["n"]
    if n:
        print("Envio de hoje foi agendado (ou já avisou o motivo). Tudo certo.")
        return
    enviar("🚨 *Alerta: o envio aos vendedores não rodou hoje.*\n\nSão 08:10 e não há nenhuma mensagem agendada para os vendedores, nem aviso de motivo "
           "(como e-mail que não chegou). Pode ser falha do robô ou do servidor. Se quiser, avise e eu verifico. "
           "Para o robô tentar de novo, é só pedir.", dia, dry, "conferencia")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("acao", choices=["entrega", "resumo", "conferir"])
    ap.add_argument("--data", default=None)
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--incluir-testes", action="store_true")
    ap.add_argument("--sempre", action="store_true")
    a = ap.parse_args()
    dia = a.data or datetime.now(rd.BRT).date().isoformat()
    if a.acao == "conferir":
        conferir(dia, a.dry)
    elif a.acao == "entrega":
        entrega(dia, a.dry, a.incluir_testes, a.sempre)
    else:
        resumo(dia, a.dry, a.incluir_testes)


if __name__ == "__main__":
    main()
