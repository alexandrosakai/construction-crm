"""Compilado da semana passada (segunda a sábado) por vendedor, a partir dos relatórios diários do Gmail."""
import os
from datetime import date, timedelta

import buscar_emails as be
import gerar_mensagens as g

AQUI = os.path.dirname(os.path.abspath(__file__))
PASTA = os.path.join(AQUI, "relatorios")
DIAS = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado"]


_CACHE = {}


def _dia(d):
    if d not in _CACHE:
        _CACHE[d] = _dia_sem_cache(d)
    return _CACHE[d]


def _dia_sem_cache(d):
    pasta = os.path.join(PASTA, d.isoformat())
    if not (os.path.exists(f"{pasta}/meta.pdf") and os.path.exists(f"{pasta}/orcamentos.pdf")):
        try:
            be.baixar(d.isoformat(), pasta)
        except Exception:
            return None
    if not (os.path.exists(f"{pasta}/meta.pdf") and os.path.exists(f"{pasta}/orcamentos.pdf")):
        return None
    return {"vend": {v["cod"]: v for v in g.ler_pdf(f"{pasta}/meta.pdf")}, "docs": g.ler_orcamentos_docs(f"{pasta}/orcamentos.pdf")}


def compilar(hoje, cod):
    """Fatos da semana passada para o vendedor `cod`, ou None se não houver relatório nenhum."""
    seg = hoje - timedelta(days=hoje.weekday() + 7)
    dias = [seg + timedelta(days=i) for i in range(6)]
    base = _dia(seg - timedelta(days=2))  # sábado anterior (ponto de partida)
    dados = [(d, _dia(d)) for d in dias]
    dados = [(d, x) for d, x in dados if x and cod in x["vend"]]
    if not dados:
        return None
    anterior = base["vend"][cod] if base and cod in base["vend"] else None
    ant_dia = seg - timedelta(days=2) if anterior else None
    if anterior is None:  # sem relatório antes da semana: o primeiro disponível é só o ponto de partida
        anterior, ant_dia = dados[0][1]["vend"][cod], dados[0][0]
        dados_calc = dados[1:]
    else:
        dados_calc = dados
    deltas, atend = [], 0.0
    prev, prev_d = anterior, ant_dia
    for d, x in dados_calc:
        v = x["vend"][cod]
        mesmo_mes = prev_d.month == d.month
        deltas.append((d, v["fat"] - prev["fat"] if mesmo_mes else v["fat"]))
        atend += (v["atend"] - prev["atend"]) if mesmo_mes else v["atend"]
        prev, prev_d = v, d
    if not deltas:
        return None
    primeiro_d, ultimo_d = dados[0][0], dados[-1][0]
    ini = anterior
    fim = dados[-1][1]["vend"][cod]
    total = sum(x for _, x in deltas)
    melhor = max(deltas, key=lambda t: t[1])
    docs_ini = (base["docs"] if base else dados[0][1]["docs"]).get(cod, {})
    docs_fim = dados[-1][1]["docs"].get(cod, {})
    sairam = {k: x for k, x in docs_ini.items() if k not in docs_fim}
    novos = {k: x for k, x in docs_fim.items() if k not in docs_ini}
    completa = base is not None and len(dados) == 6
    return {
        "periodo": f"{dados[0][0]:%d/%m} a {ultimo_d:%d/%m}" ,
        "semana_completa_com_todos_os_relatorios": completa,
        "faturado_na_semana": g.money(total),
        "melhor_dia_da_semana": f"{DIAS[melhor[0].weekday()]} ({g.money(melhor[1])})",
        "percentual_da_meta_no_comeco_da_semana": g.pct(ini["pct_alc"]),
        "percentual_da_meta_no_fim_da_semana": g.pct(fim["pct_alc"]),
        "margem_no_fim_da_semana": g.pct(fim["mar"]),
        "ticket_medio_no_fim_da_semana": g.money(fim["ticket"]),
        "orcamentos_que_sairam_da_lista_de_pendentes_na_semana": f"{len(sairam)} no valor de {g.money(sum(x['valor'] for x in sairam.values()))}",
        "orcamentos_novos_na_semana": f"{len(novos)} no valor de {g.money(sum(x['valor'] for x in novos.values()))}",
        "orcamentos_ainda_pendentes_no_fim_da_semana": f"{len(docs_fim)} no valor de {g.money(sum(x['valor'] for x in docs_fim.values()))}",
    }
