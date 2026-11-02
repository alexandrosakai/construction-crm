#!/usr/bin/env python3
"""Escreve as mensagens dos vendedores com o Claude, em tom humano e variando por dia da semana.
Números e listas de clientes vêm dos relatórios; o modelo só escreve o texto em volta.

Uso: python3 humanizar.py meta.pdf --orcamentos orc.pdf [--so 031] [--dia-semana 0-5]
                         [--data-ref DD/MM/AAAA] [--dias-restantes N] [--json saida.json]
Requer ANTHROPIC_API_KEY em /opt/whatsapp-stack/.env
"""
import argparse
import json
import os
import re
import urllib.request
from datetime import date

import gerar_mensagens as g

ENV = "/opt/whatsapp-stack/.env"
HIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "historico.json")
MODELO = "claude-sonnet-5-5"
MARCA = "[[LISTA]]"

# 0 = segunda ... 5 = sábado
TEMAS = {
    0: "SEGUNDA, largada da semana: energia de recomeço, semana nova e placar zerado, foco em traçar o plano da semana e começar forte.",
    1: "TERÇA, ritmo: constância, manter o embalo da largada, foco nas primeiras ligações e orçamentos abertos.",
    2: "QUARTA, virada: metade do caminho, olhar onde está, ajustar a rota e decidir o que fazer na segunda metade da semana.",
    3: "QUINTA, aceleração: urgência positiva, hora de levar os orçamentos mais maduros para a decisão.",
    4: "SEXTA, fechamento forte: garra para fechar a semana com força, converter o que está pendente, fechar as pontas soltas e terminar com orgulho.",
    5: "SÁBADO, meio período: a loja só abre das 8h às 12h, então tudo é rápido. Tom leve, vendas ágeis do balcão e deixar a semana seguinte encaminhada.",
}

REGRAS = """Você escreve mensagens de WhatsApp como o gestor comercial da Empresa Exemplo (materiais de construção), em primeira pessoa, para um vendedor da equipe.
Objetivo: soar como um gestor de verdade falando com o seu vendedor: profissional, educado, próximo e proativo. Nada de relatório nem de robô.

Regras de estilo:
- Português do Brasil, profissional e próximo, frases curtas e claras, como um gestor digitando no WhatsApp. Gíria só leve; nada de linguagem de grupo de amigos.
- Chame o vendedor pelo primeiro nome, mas não precisa ser na primeira palavra.
- Sem títulos em negrito, sem seções fixas, sem cabeçalhos tipo "Seu placar" ou "Plano de ação". Pode usar *negrito* em no máximo 2 destaques.
- Nada de lista numerada nos textos. Se citar mais de uma ação, ligue com frases naturais.
- Use 1 a 3 emojis, bem colocados, sem exagerar.
- Varie a abertura. Não comece de jeito parecido com as mensagens anteriores que vou mostrar.
- Não repita as dicas, frases e perguntas que já apareceram nas mensagens anteriores (ex.: se já sugeriu oferecer item a mais, hoje escolha outra ação). Cada dia pede um foco diferente.
- Se houver dados do dia anterior, compare de forma natural ("ontem você estava em..."), reconhecendo a evolução.
- Seja específico: use os números reais do vendedor, mas só os poucos que importam. Não despeje todos.
- Se está bem, reconheça com sinceridade e de forma específica. Se está atrás, seja encorajador e prático, sem culpar nem passar pano.
- Dê 2 a 3 ações concretas que ele possa fazer hoje, escolhidas entre as sugestões fornecidas, reescritas com suas palavras.
- Não invente números, clientes, datas, promessas nem fatos. Só use os dados fornecidos.
- Não use superlativos nem comparações que não estejam escritos nos dados (ex.: "o maior", "o melhor", "recorde", "primeira vez", "melhor semana"). Só compare o que os dados trazem: ontem, média do time, posição no ranking, meta.
- Não projete valores em reais que não estejam nos dados (ex.: "isso renderia R$ X mil").
- Não assine como pessoa nem diga que é robô ou IA. Não escreva rodapé (ele é acrescentado depois).
- Nunca diga "no caixa": faturado não é dinheiro recebido.
- Pode lembrar, de forma motivadora e sem prometer valores, que quanto mais ele fecha, mais ele ganha.
- Sempre educado e respeitoso, com linguagem de gestor comercial falando com o vendedor.
- Seja proativo: antecipe o que pode atrapalhar (preço, prazo, condição, falta de produto, estoque, entrega) e coloque-se à disposição de forma concreta, com palavras diferentes a cada mensagem. NUNCA copie a mesma frase de ajuda de uma mensagem para outra, e não prometa resolver "na hora" nem garantir resultado: ofereça ajudar, acompanhar ou verificar. Feche com um próximo passo claro.
- Tamanho: entre 400 e 900 caracteres.
Responda só com o texto da mensagem, sem comentários."""


def chave():
    e = dict(l.strip().split("=", 1) for l in open(ENV) if "=" in l and not l.startswith("#"))
    return e["ANTHROPIC_API_KEY"]


_FALHAS = 0
MAX_FALHAS = 4  # falhas seguidas da API: depois disso, não tenta mais nesta execução (usa os textos de reserva)


def claude(sistema, usuario, tentativas=2):
    global _FALHAS
    if _FALHAS >= MAX_FALHAS:
        return None
    corpo = {"model": MODELO, "max_tokens": 3000, "system": sistema,
             "messages": [{"role": "user", "content": usuario}]}
    for i in range(tentativas):
        try:
            r = urllib.request.Request(
                "https://api.anthropic.com/v1/messages", data=json.dumps(corpo).encode(),
                headers={"x-api-key": chave(), "anthropic-version": "2023-06-01", "content-type": "application/json"})
            d = json.load(urllib.request.urlopen(r, timeout=60))
            txt = "".join(b["text"] for b in d["content"] if b["type"] == "text").strip()
            if txt:
                _FALHAS = 0
                return txt
        except Exception as e:
            _FALHAS += 1
            print("  aviso Claude:", e)
            if _FALHAS >= MAX_FALHAS:
                print("  API do Claude indisponível: usando textos de reserva nesta execução.")
                return None
    return None


def tokens(t):
    return set(re.findall(r"\d[\d.,]*\d|\d", t))


def _valor(tok):
    t = tok.replace(".", "").replace(",", ".") if "," in tok else tok.replace(".", "")
    try:
        return float(t)
    except ValueError:
        return None


def valido(texto, permitido, exigir_marca=False):
    """Todo número com 3+ dígitos ou vírgula precisa bater, em valor, com algum número dos dados.
    "R$ 128.000" vale por "128.000,00"; "R$ 128 mil" vale se arredonda (até 1%) um valor dos dados."""
    if not texto or (exigir_marca and MARCA not in texto):
        return False
    vals = [x for x in (_valor(t) for t in tokens(permitido)) if x is not None]
    for m in re.finditer(r"(\d[\d.,]*\d|\d)(\s*(?:mil\b|milh))?", texto):
        n, mil = m.group(1), m.group(2)
        if not (len(re.sub(r"\D", "", n)) >= 3 or "," in n or mil):
            continue
        v = _valor(n)
        if v is None:
            return False
        if mil:
            v *= 1_000_000 if "milh" in mil else 1000
            ok = any(abs(v - a) <= 0.01 * max(a, 1) for a in vals) or v / 1000 in vals
        else:
            ok = any(abs(v - a) <= 0.001 * a + 0.011 for a in vals)
        if not ok:
            return False
    return True


MIN_ABAIXO = 3
NIVEL_FIRME = 3  # indicadores abaixo (de 5) para o tom firme
NIVEL_DURO = 4   # ... e para o tom duro


def nivel_alerta(v, equipe, dias_uteis_mes, dias_restantes):
    """Conta os indicadores abaixo do esperado. Devolve (lista_de_indicadores_abaixo, duro?)."""
    ab = []
    decorrido = max(0.0, min(1.0, 1 - dias_restantes / dias_uteis_mes)) * 100 if dias_uteis_mes else 100
    if v["pct_alc"] < decorrido:
        ab.append(f"ritmo da meta ({g.pct(v['pct_alc'])} feito, esperado {g.pct(decorrido)} neste ponto do mês)")
    if v["mar"] < v["meta_mar"]:
        ab.append(f"margem ({g.pct(v['mar'])} contra meta de {g.pct(v['meta_mar'])})")
    if equipe and v["ticket"] < equipe["ticket"]:
        ab.append(f"ticket médio ({g.money(v['ticket'])}, média do time {g.money(equipe['ticket'])})")
    if equipe and v["itens"] < equipe["itens"]:
        ab.append(f"itens por venda ({str(round(v['itens'], 2)).replace('.', ',')}, média do time {str(round(equipe['itens'], 2)).replace('.', ',')})")
    if v["orc_aberto"] < max(v["falta"], 0):
        ab.append(f"orçamentos abertos ({g.money(v['orc_aberto'])}) menores que o que falta para a meta ({g.money(max(v['falta'], 0))})")
    return ab, len(ab) >= MIN_ABAIXO


def nivel_tom(v, equipe, dias_uteis_mes, dias_restantes):
    """(indicadores_abaixo, nível): 'duro' (4+ abaixo), 'firme' (3 abaixo), 'bem' (95%+ da meta ou 0-1 abaixo), senão 'normal'."""
    ab, _ = nivel_alerta(v, equipe, dias_uteis_mes, dias_restantes)
    n = len(ab)
    if v["pct_alc"] >= 95:  # perto de bater (ou batendo) a meta: reconhecer e empurrar, não cobrar
        return ab, "bem"
    if n >= NIVEL_DURO:
        return ab, "duro"
    if n >= NIVEL_FIRME:
        return ab, "firme"
    if n <= 1 or v["pct_alc"] >= 95:
        return ab, "bem"
    return ab, "normal"


def media_equipe(vendedores):
    n = len(vendedores)
    if not n:
        return None
    ordem = sorted(vendedores, key=lambda x: -x["pct_alc"])
    return {"ticket": sum(x["ticket"] for x in vendedores) / n, "itens": sum(x["itens"] for x in vendedores) / n,
            "media_pct": sum(x["pct_alc"] for x in vendedores) / n, "lider": g.primeiro_nome(ordem[0]["nome"]),
            "lider_pct": ordem[0]["pct_alc"], "ordem": [x["cod"] for x in ordem], "total": n}


def comparativo(v, equipe):
    if not equipe or v["cod"] not in equipe["ordem"]:
        return None
    return {"media_do_time_percentual_da_meta": g.pct(equipe["media_pct"]),
            "posicao_do_vendedor_no_ranking_de_metas": f"{equipe['ordem'].index(v['cod']) + 1}º de {equipe['total']}",
            "lider_do_time": equipe["lider"], "percentual_da_meta_do_lider": g.pct(equipe["lider_pct"])}


TOM_DURO = """

NÍVEL DE ALERTA ALTO: este vendedor está abaixo do esperado em todos os indicadores principais e, sem mudança de postura, não chega na meta.
Escreva como um gestor de verdade falaria com um vendedor que está deixando a meta escapar: humano, franco e firme.
- Seja direto, sem rodeio e sem enrolar. Pode ser seco. Pode dizer coisas como "tá abaixo do que a gente precisa", "assim a meta não chega", "preciso ver outra postura". Fale como gente, com gíria leve do dia a dia de loja.
- Use os números para mostrar a gravidade e quanto ele precisa faturar por dia (valor fornecido).
- Pode comparar com o time: use os dados de "comparativo_com_o_time" (média do time, posição, líder e percentual do líder). Fale do líder pelo nome se isso ajudar, como referência de que dá para chegar lá.
- Mostre que acredita nele e por isso cobra: diga que ele consegue, que ainda há tempo, que depende de agir hoje e que quanto mais fechar, mais vai ganhar. Empurre e motive, sem ameaçar.
- Sempre educado: firme não é grosso.
- Exija compromisso: peça que responda com o que vai fazer hoje, de forma objetiva.
- Dê 2 ou 3 ações concretas, curtas e na ordem de prioridade.
- Não elogie indicadores isolados só para suavizar. Reconheça algo bom apenas se ajudar a cobrar.
- Não xingue, não humilhe e não ironize. Não invente consequências (demissão, corte, punição, perda de comissão ou de qualquer coisa) que não estejam nos dados; fale só do que o número já mostra.
- No máximo 1 ou 2 emojis."""


TOM_FIRME = """

NÍVEL DE ALERTA MÉDIO: este vendedor está abaixo do esperado em vários indicadores e precisa de um empurrão firme.
Escreva como um gestor comercial franco, mas mais leve que numa cobrança dura: diga com clareza o que está fora do lugar (use os números), cobre atitude e mostre que dá para virar.
- Direto e educado, sem rodeio. Pode comparar com a média do time (dados em "comparativo_com_o_time"), sem citar colegas pelo nome.
- Diga que ele consegue, que o resultado está ao alcance e que quanto mais fechar, mais vai ganhar.
- 2 ou 3 ações concretas, em ordem de prioridade, e peça que responda com o que vai fazer hoje.
- Não xingue, não humilhe, não ironize e não invente consequências. No máximo 2 emojis."""

TOM_BEM = """

NÍVEL: ESTÁ INDO BEM. Este vendedor está com bons resultados. Parabenize de verdade, com entusiasmo e de forma específica:
- Cite 2 ou 3 resultados reais dos dados que estão bons (meta, margem, ticket, inadimplência, posição no time etc.), sem exagerar nem inventar.
- Tom de reconhecimento e festa, de quem fica orgulhoso do resultado. Pode usar mais emojis (2 ou 3).
- Em seguida, empurre para o próximo nível: manter o ritmo, passar da meta e lembrar que quanto mais ele fecha, mais ganha.
- Cobre no máximo 1 ação, leve, e não faça cobrança dura nem fale de problema, a não ser que seja um ajuste pequeno."""

TONS = {"duro": TOM_DURO, "firme": TOM_FIRME, "bem": TOM_BEM}


def historico():
    try:
        return json.load(open(HIST, encoding="utf-8"))
    except Exception:
        return {}


def lembrar(h, cod, tipo, texto):
    h.setdefault(cod, {}).setdefault(tipo, []).append(texto)
    h[cod][tipo] = h[cod][tipo][-5:]


def comparar(v):
    """Compara com o dia anterior (v["_ontem"] = {fat, pct_alc, mar, ticket}) já com as contas feitas."""
    o = v.get("_ontem")
    if not o:
        return None
    return {"percentual_da_meta_ontem": g.pct(o["pct_alc"]), "faturado_ontem": g.money(o["fat"]),
            "faturado_a_mais_desde_ontem": g.money(v["fat"] - o["fat"]),
            "pontos_percentuais_a_mais_na_meta": f"{v['pct_alc'] - o['pct_alc']:.1f}".replace(".", ","),
            "margem_ontem": g.pct(o["mar"]), "ticket_medio_ontem": g.money(o["ticket"])}


def fatos_metas(v, dias, data_ref, dia=0, abaixo=None):
    falar_inad = dia == 1 or (v["inad"] >= 4 and dia == 3)  # terça; quinta também se estiver alta
    faixa, fortes, planos, por_dia = g.analisar(v, dias)
    if not falar_inad:
        planos = [p for p in planos if "nadimplência" not in p] or planos
        fortes = [x for x in fortes if "nadimplência" not in x]
    f = {
        "vendedor": g.primeiro_nome(v["nome"]), "dados_de": data_ref,
        "meta_mensal": g.money(v["meta"]), "faturado": g.money(v["fat"]), "percentual_da_meta": g.pct(v["pct_alc"]),
        "falta_para_a_meta": g.money(max(v["falta"], 0)), "dias_uteis_restantes_no_mes": dias,
        "margem_atual": g.pct(v["mar"]), "meta_de_margem": g.pct(v["meta_mar"]),
        "ticket_medio": g.money(v["ticket"]), "itens_por_venda": str(round(v["itens"], 2)).replace(".", ","),
        "orcamentos_em_aberto": g.money(v["orc_aberto"]),
        "inadimplencia": g.pct(v["inad"]) if falar_inad else None, "devolucoes": g.money(v["dev"]),
        "faturar_por_dia_necessario_para_bater_a_meta": g.money(max(v["falta"], 0) / dias) if dias else None,
        "indicadores_abaixo_do_esperado": abaixo or None, "comparativo_com_o_time": v.get("_comparativo"), "dados_do_dia_anterior": comparar(v), "pontos_fortes": fortes, "sugestoes_de_acao_para_reescrever": [re.sub(r"\*", "", planos[(dia + k) % len(planos)]) for k in range(min(2, len(planos)))],
    }
    return f


def texto_metas(v, dias, data_ref, dia, hist, abaixo=None, duro=False, semana=None):
    f = fatos_metas(v, dias, data_ref, dia, abaixo)
    if semana:
        f["resumo_da_semana_passada"] = semana
    ant = hist.get(v["cod"], {}).get("metas", [])
    usuario = (f"TEMA DO DIA: {TEMAS[dia]}\n\nDADOS DO VENDEDOR (use só estes):\n{json.dumps(f, ensure_ascii=False, indent=1)}\n\n"
               f"MENSAGENS ANTERIORES PARA ESTE VENDEDOR (não repita abertura nem estrutura):\n"
               + ("\n---\n".join(a[:450] for a in ant) if ant else "(nenhuma)")
               + ("\n\nHOJE É SEGUNDA: abra com um compilado curto da SEMANA PASSADA usando só \"resumo_da_semana_passada\" "
                  "(o que foi bom, o que ficou pendente, como os orçamentos andaram) e depois mande-o para a nova semana com força, "
                  "dizendo o que fazer hoje. Se a semana não estiver completa, fale só do que há nos dados, sem comentar a falta."
                  if semana else "\n\nEscreva a mensagem de hoje com o resumo de como ele está e o que fazer hoje."))
    for _ in range(3):
        t = claude(REGRAS + TONS.get(duro, ""), usuario)
        if valido(t, json.dumps(f, ensure_ascii=False)):
            return t
        if os.environ.get("HUMANIZAR_DEBUG"):
            print("  [rejeitado]", t.replace("\n", " ")[:700])
    return None


def texto_com_lista(v, lista, dia, hist, tipo, duro=False):
    sabado = dia == 5
    volto = "perto do meio-dia, antes de a loja fechar" if sabado else "no fim do dia"
    nome = g.primeiro_nome(v["nome"])
    fatos = {"vendedor": nome, "quantidade_de_clientes": len(lista),
             "valor_total_da_lista": g.money(sum(c["valor"] for c in lista)),
             "maior_cliente": {"nome": lista[0]["nome"], "valor": g.money(lista[0]["valor"])}}
    if tipo == "orcamentos":
        tarefa = ("Escreva a mensagem que acompanha a LISTA DE CLIENTES PARA LIGAR hoje. Escreva a abertura (2 a 3 frases), depois a marca "
                  f"{MARCA} sozinha em uma linha (a lista será colocada ali automaticamente) e depois um fechamento curto (1 a 2 frases) "
                  "com uma dica de abordagem (perguntar o que falta para decidir e combinar data) e avisando que "+volto+" você volta para saber como foi.")
    else:
        momento = "fim de expediente de sábado (a loja fecha ao meio-dia)" if sabado else "fim do dia"
        tarefa = (f"Escreva a cobrança de {momento} sobre os {len(lista)} maiores clientes da lista que ele recebeu de manhã (esses são os que mais pesam). "
                  "Abertura curta (1 a 2 frases) perguntando, "
                  f"cliente por cliente, se já mandou mensagem, ligou ou fechou; depois {MARCA} sozinha em uma linha (a lista entra ali), "
                  "e um fechamento pedindo que responda com o número do cliente e a situação (ex.: \"1 fechou, 2 liguei, 3 ainda não\"), "
                  "com um incentivo no tom do dia.")
    ant = hist.get(v["cod"], {}).get(tipo, [])
    usuario = (f"TEMA DO DIA: {TEMAS[dia]}\n\nDADOS:\n{json.dumps(fatos, ensure_ascii=False)}\n\n{tarefa}\n\n"
               f"MENSAGENS ANTERIORES DESTE TIPO (não repita abertura):\n" + ("\n---\n".join(a[:350] for a in ant) if ant else "(nenhuma)"))
    for _ in range(3):
        t = claude(REGRAS.replace("Tamanho: entre 400 e 900 caracteres.", "Tamanho curto, sem contar a lista.") + TONS.get(duro, ""), usuario)
        if valido(t, json.dumps(fatos, ensure_ascii=False), exigir_marca=True):
            return t
    return None


def linhas_lista(lista, com_tel):
    L = []
    for i, c in enumerate(lista, 1):
        extra = f" ({c['qtd']} orçamentos)" if c["qtd"] > 1 else ""
        if com_tel:
            tel = f", tel. {c['tel']}" if c["tel"] else ""
            L.append(f"{i}. {c['nome']}{extra}: {g.money(c['valor'])}{tel}")
        else:
            L.append(f"{i}. {c['nome']}: {g.money(c['valor'])}")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--orcamentos", required=True)
    ap.add_argument("--so", default=None, help="código de um vendedor")
    ap.add_argument("--dia-semana", type=int, default=None, help="0=seg ... 5=sáb (padrão: hoje)")
    ap.add_argument("--data-ref", default="relatório")
    ap.add_argument("--dias-restantes", type=int, default=1)
    ap.add_argument("--dias-uteis-mes", type=int, default=26)
    ap.add_argument("--json", default="mensagens_humanas.json")
    ap.add_argument("--sem-historico", action="store_true", help="não grava no histórico (teste)")
    a = ap.parse_args()

    dia = a.dia_semana if a.dia_semana is not None else min(date.today().weekday(), 5)
    orc = g.ler_orcamentos(a.orcamentos)
    hist = historico()
    saida = []
    todos = g.ler_pdf(a.pdf)
    eq = media_equipe(todos)
    for v in todos:
        if a.so and v["cod"] != a.so:
            continue
        lista = orc.get(v["cod"], [])
        item = {"cod": v["cod"], "nome": v["nome"], "dia_semana": dia}
        abaixo, duro = nivel_alerta(v, eq, a.dias_uteis_mes, a.dias_restantes)
        v["_comparativo"] = comparativo(v, eq) if duro else None
        item["tom_duro"], item["indicadores_abaixo"] = duro, abaixo
        m = texto_metas(v, a.dias_restantes, a.data_ref, dia, hist, abaixo, duro)
        item["mensagem"] = m or g.mensagem(v, a.dias_restantes, a.data_ref, lista)
        item["mensagem_modelo_fixo"] = m is None
        if lista:
            t = texto_com_lista(v, lista, dia, hist, "orcamentos", duro)
            item["orcamentos"] = t.replace(MARCA, linhas_lista(lista, True)) if t else g.mensagem_orcamentos(v, lista)
            t = texto_com_lista(v, lista, dia, hist, "followup", duro)
            item["followup"] = t.replace(MARCA, linhas_lista(lista, False)) if t else g.followup(v, lista)
        if not a.sem_historico:
            lembrar(hist, v["cod"], "metas", item["mensagem"])
            if lista:
                lembrar(hist, v["cod"], "orcamentos", item["orcamentos"])
                lembrar(hist, v["cod"], "followup", item["followup"])
        saida.append(item)
    json.dump(saida, open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    if not a.sem_historico:
        json.dump(hist, open(HIST, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{len(saida)} vendedores gerados -> {a.json}")


if __name__ == "__main__":
    main()
