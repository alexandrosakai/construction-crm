#!/usr/bin/env python3
"""Gera mensagens personalizadas por vendedor a partir do relatório
"META POR VENDEDOR 3.0 - EXEMPLO TINTAS" (PDF).

Uso: python3 gerar_mensagens.py relatorio.pdf [--dias-restantes N] [--saida mensagens.md]
Requer: pip install pypdf
"""
import argparse
import json
import random
import re
import sys

NUM = r"-?\d[\d.]*,\d{2}|\d+"
CAMPOS = ["meta", "fat", "pct_alc", "fat_proj", "pct_proj", "falta", "meta_dia", "dev",
          "aberto_mes", "inad", "dif", "meta_mar", "mar", "atend", "itens", "ticket",
          "orc_aberto", "fat_orc", "pct_fat_orc"]


def br(v):
    return float(v.replace(".", "").replace(",", "."))


def money(v):
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def mil(v):
    return f"R$ {round(v / 1000):d} mil"


def pct(v):
    return f"{v:.1f}".replace(".", ",") + "%"


def ler_pdf(caminho):
    from pypdf import PdfReader
    texto = " ".join(p.extract_text() for p in PdfReader(caminho).pages)
    texto = re.sub(r"\s+", " ", texto)
    rx = re.compile(r"(\d{3})-([^\d]+?)\s*((?:%s)(?: (?:%s)){18})" % (NUM, NUM))
    vendedores = []
    for cod, nome, nums in rx.findall(texto):
        v = dict(zip(CAMPOS, (br(n) for n in nums.split())))
        v["cod"], v["nome"] = cod, nome.strip().title()
        vendedores.append(v)
    return vendedores


def ler_orcamentos(caminho, topo=15):
    """Orçamentos pendentes por vendedor: agrupa por cliente e devolve os `topo` maiores.
    'Consumidor final' fica de fora (não há a quem ligar)."""
    from pypdf import PdfReader
    texto = " ".join(p.extract_text() for p in PdfReader(caminho).pages)
    texto = re.sub(r"\s+", " ", texto)
    rx = re.compile(r"\d{12}-\d{3} (\d{8})-(.+?) (?:(\(\d{2}\) ?[\d-]+) )?(\d[\d.]*,\d{2}) (\d{3}) -?[\d,]+")
    por_vend = {}
    for cli, nome, tel, valor, vend in rx.findall(texto):
        if "CONSUMIDOR FINAL" in nome.upper():
            continue
        d = por_vend.setdefault(vend, {}).setdefault(cli, {"nome": nome.strip().title(), "tel": tel, "valor": 0.0, "qtd": 0})
        d["valor"] += br(valor)
        d["qtd"] += 1
        d["tel"] = d["tel"] or tel
    return {v: sorted(c.values(), key=lambda x: -x["valor"])[:topo] for v, c in por_vend.items()}


def total_impresso(caminho):
    """Total de registros que o próprio PDF declara ("REGISTROS IMPRESSOS: N"), ou None."""
    from pypdf import PdfReader
    texto = " ".join(p.extract_text() for p in PdfReader(caminho).pages)
    n = re.findall(r"REGISTROS IMPRESSOS:\s*(\d+)", texto)
    return int(n[-1]) if n else None


def ler_orcamentos_docs(caminho):
    """{vendedor: {doc: {cliente, valor}}}: todos os orçamentos pendentes, para comparar um dia com o outro."""
    from pypdf import PdfReader
    texto = " ".join(p.extract_text() for p in PdfReader(caminho).pages)
    texto = re.sub(r"\s+", " ", texto)
    rx = re.compile(r"(\d{12}-\d{3}) \d{8}-(.+?) (?:\(\d{2}\) ?[\d-]+ )?(\d[\d.]*,\d{2}) (\d{3}) -?[\d,]+")
    out = {}
    for doc, nome, valor, vend in rx.findall(texto):
        out.setdefault(vend, {})[doc] = {"cliente": nome.strip().title(), "valor": br(valor)}
    return out


def bloco_orcamentos(lista):
    if not lista:
        return []
    L = ["", f"*📞 Clientes para ligar hoje (seus {len(lista)} maiores orçamentos pendentes):*"]
    for i, c in enumerate(lista, 1):
        extra = f" ({c['qtd']} orçamentos)" if c["qtd"] > 1 else ""
        tel = f", tel. {c['tel']}" if c["tel"] else ""
        L.append(f"{i}. {c['nome']}{extra}: {money(c['valor'])}{tel}")
    L.append(f"Total da lista: {money(sum(c['valor'] for c in lista))}")
    return L


def _pick(*op):
    return random.choice(op)


def mensagem_orcamentos(v, lista, sabado=False):
    """Texto de reserva da lista de clientes para ligar (usado só se a IA falhar)."""
    nome = primeiro_nome(v["nome"])
    volto = "perto do meio-dia, antes de a loja fechar," if sabado else "no fim do dia"
    L = [_pick(f"{nome}, separei os {len(lista)} maiores orçamentos pendentes para você ligar hoje 📞",
               f"{nome}, estes são os {len(lista)} clientes que mais pesam nos seus orçamentos pendentes 📞",
               f"{nome}, segue a lista de {len(lista)} clientes para você ligar hoje 📞"), ""]
    for i, c in enumerate(lista, 1):
        extra = f" ({c['qtd']} orçamentos)" if c["qtd"] > 1 else ""
        tel = f", tel. {c['tel']}" if c["tel"] else ""
        L.append(f"{i}. {c['nome']}{extra}: {money(c['valor'])}{tel}")
    L += ["", f"Total da lista: {money(sum(c['valor'] for c in lista))}.",
          f"Pergunte o que falta para cada um decidir e combine uma data de retorno. {volto.capitalize()} eu volto aqui para saber como foi."]
    return "\n".join(L)


def followup(v, lista, sabado=False):
    """Texto de reserva da cobrança (usado só se a IA falhar)."""
    nome = primeiro_nome(v["nome"])
    L = [_pick(f"{nome}, hora de olhar os clientes que te passei de manhã.", f"{nome}, como ficaram os clientes da lista de hoje?"),
         "Cliente por cliente: já mandou mensagem, ligou ou fechou?", ""]
    for i, c in enumerate(lista, 1):
        L.append(f"{i}. {c['nome']}: {money(c['valor'])}")
    L += ["", "Me responde com o número do cliente e a situação, por exemplo: \"1 fechou, 2 liguei, 3 ainda não\". "
          "Você consegue, e quanto mais fechar, mais ganha. 💪"]
    return "\n".join(L)


def primeiro_nome(nome):
    return nome.split()[0]


def analisar(v, dias):
    """Retorna (faixa, pontos_fortes, planos). Cada plano é uma ação concreta."""
    fortes, planos = [], []
    alc = v["pct_alc"]
    faixa = "meta" if alc >= 100 else "quase" if alc >= 90 else "bom" if alc >= 70 else "atenção"
    falta = max(v["falta"], 0)
    por_dia = falta / dias if dias else falta

    # 1) Orçamentos em aberto: maior alavanca para fechar a meta
    if falta > 0 and v["orc_aberto"] > 0:
        conv = falta / v["orc_aberto"] * 100
        if conv <= 100:
            planos.append(
                f"Você tem {money(v['orc_aberto'])} em orçamentos abertos. Converter {pct(conv)} deles "
                f"fecha a sua meta. "+("Ligue hoje para os clientes da lista que te envio logo em seguida, um por um, e peça uma data de decisão." if v.get("_tem_lista", True) else "Procure hoje os clientes com orçamento em aberto, um por um, e peça uma data de decisão.")+"")
        else:
            planos.append(
                f"Seus orçamentos abertos somam {money(v['orc_aberto'])}, abaixo do que falta ({money(falta)}). "
                f"Hoje, reative clientes que compraram nos últimos 60 dias e gere novos orçamentos.")
    elif falta == 0:
        fortes.append("meta batida")

    # 2) Margem
    if v["mar"] >= v["meta_mar"]:
        fortes.append(f"margem de {pct(v['mar'])}, acima da meta de {pct(v['meta_mar'])}")
    else:
        dif = v["meta_mar"] - v["mar"]
        planos.append(
            f"Sua margem está em {pct(v['mar'])} e a meta é {pct(v['meta_mar'])} (faltam {str(round(dif, 1)).replace('.', ',')} p.p.). "
            f"Antes de dar desconto, ofereça o produto de linha mais alta ou uma marca com margem melhor. "
            f"Desconto acima do seu limite só com aval do gerente.")

    # 3) Ticket e itens por venda (sem projeções em R$: a coluna de atendimentos do relatório não bate com o faturamento)
    itens = str(round(v["itens"], 2)).replace(".", ",")
    if v["itens"] < 2.5:
        por_item = v["ticket"] / v["itens"]
        planos.append(
            f"*Ticket médio:* {money(v['ticket'])}, com {itens} itens por venda. Cada item vale em média {money(por_item)}, "
            f"então *vender 1 item a mais por cliente* sobe o ticket. Antes de fechar o pedido, pergunte: "
            f"\"Já separou tudo que precisa para finalizar o serviço?\"")
    elif v["ticket"] < 350:
        planos.append(
            f"*Ticket médio:* {money(v['ticket'])}. Você já vende bem em variedade ({itens} itens por venda), "
            f"então o ganho está no valor de cada item. Ofereça a embalagem maior ou a linha superior para subir o valor de cada venda.")
    elif v["ticket"] >= 500:
        fortes.append(f"ticket médio de {money(v['ticket'])}")

    # 4) Inadimplência
    if v["inad"] >= 2:
        planos.append(
            f"Sua inadimplência está em {pct(v['inad'])}, que é alta. Confira o limite e o histórico "
            f"do cliente antes de fechar prazo. Combine a cobrança dos atrasados com o financeiro ainda esta semana.")
    elif v["inad"] < 1:
        fortes.append(f"inadimplência baixíssima ({pct(v['inad'])})")

    # 5) Devoluções
    if v["fat"] and v["dev"] / v["fat"] >= 0.05:
        planos.append(
            f"As devoluções somam {money(v['dev'])} ({pct(v['dev'] / v['fat'] * 100)} do faturado). "
            f"Confirme cor, quantidade e produto com o cliente antes de lançar o pedido. "
            f"Isso evita perda de venda e retrabalho.")

    return faixa, fortes, planos, por_dia


def mensagem(v, dias, data_ref, lista=(), tom="normal", sabado=False):
    """Texto de reserva (usado só se a IA falhar): sem títulos de relatório, no tom do vendedor."""
    nome = primeiro_nome(v["nome"])
    faixa, fortes, planos, por_dia = analisar(v, dias)
    falta = max(v["falta"], 0)
    planos = [re.sub(r"\*", "", p) for p in planos]
    quando = "hoje (a loja fecha ao meio-dia)" if sabado else "hoje"
    if tom == "bem":
        L = [_pick(f"{nome}, parabéns pelo resultado! 🎉", f"{nome}, que resultado bonito! 👏", f"{nome}, muito bem! 🙌"),
             f"Você está em {pct(v['pct_alc'])} da meta, com {money(v['fat'])} faturados." + (f" {fortes[0].capitalize()}." if fortes else ""),
             "Meta batida, vamos para mais! 🚀" if falta == 0 else f"Faltam só {money(falta)} para bater a meta, e dá para fechar {quando}."]
    elif tom == "firme":
        L = [f"{nome}, vou ser direto: você está em {pct(v['pct_alc'])} da meta ({money(v['fat'])}) e há pontos para ajustar.",
             f"Faltam {money(falta)}, o que dá {money(por_dia)} por dia. Dá para virar, mas precisa começar {quando}."]
    elif tom == "duro":
        L = [f"{nome}, preciso ser franco: o cenário está sério. Você está em {pct(v['pct_alc'])} da meta ({money(v['fat'])}) e faltam {money(falta)}.",
             f"Isso dá {money(por_dia)} por dia. Assim a meta não chega sem outra postura a partir de {quando}."]
    else:
        L = [_pick(f"Bom dia, {nome}!", f"{nome}, bom dia!", f"{nome}, tudo bem?"),
             f"Você está em {pct(v['pct_alc'])} da meta ({money(v['fat'])}), faltam {money(falta)}."]
    if planos and tom != "bem":
        L.append("Prioridades para " + quando + ": " + " ".join(planos[:2]))
    fecho = {"duro": "Você consegue, e quanto mais fechar, mais vai ganhar. Me responde com o que vai fazer hoje?",
             "firme": "Você consegue, e quanto mais fechar, mais ganha. Me responde com o que vai fazer hoje?",
             "bem": "Quanto mais você fecha, mais ganha. Vamos em frente! 🚀"}.get(tom)
    L.append(fecho or _pick("Se algum cliente travar por preço, prazo ou estoque, me avise que eu ajudo. Bora! 💪",
                            "Qualquer coisa que travar uma venda, me responde aqui que eu olho com você. Bora! 💪"))
    return "\n\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--orcamentos", default=None, help="PDF 'Vendedor - Orçamentos pendentes'")
    ap.add_argument("--topo", type=int, default=15)
    ap.add_argument("--dias-restantes", type=int, default=1)
    ap.add_argument("--data-ref", default=None, help="Texto da data do relatório (ex.: 31/10/2026)")
    ap.add_argument("--saida", default="mensagens.md")
    ap.add_argument("--json", default=None, help="Também grava um JSON {cod, nome, mensagem}")
    a = ap.parse_args()

    vend = ler_pdf(a.pdf)
    if not vend:
        sys.exit("Nenhum vendedor encontrado no PDF.")
    orc = ler_orcamentos(a.orcamentos, a.topo) if a.orcamentos else {}
    data_ref = a.data_ref or "relatório"
    blocos, saida_json = [], []
    for v in vend:
        lista = orc.get(v["cod"], [])
        msg = mensagem(v, a.dias_restantes, data_ref, lista)
        blocos.append(f"## {v['cod']} - {v['nome']}\n\n{msg}\n")
        saida_json.append({"cod": v["cod"], "nome": v["nome"], "mensagem": msg,
                           "orcamentos": mensagem_orcamentos(v, lista) if lista else None,
                           "followup": followup(v, lista) if lista else None})
    open(a.saida, "w", encoding="utf-8").write("\n---\n\n".join(blocos))
    if a.json:
        json.dump(saida_json, open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"{len(vend)} mensagens geradas em {a.saida}")


if __name__ == "__main__":
    main()
