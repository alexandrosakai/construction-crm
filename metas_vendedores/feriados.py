"""Feriados do robô: nacionais + do estado definido em HOLIDAY_STATE, padrão SP (biblioteca `holidays`) + municipais/outros em feriados_extra.json.

feriados_extra.json: {"2026-12-08": "Aniversário do município", ...}
"""
import json
import os
from datetime import date

import holidays

AQUI = os.path.dirname(os.path.abspath(__file__))


def feriados(ano):
    f = dict(holidays.Brazil(state=os.environ.get("HOLIDAY_STATE", "SP"), years=ano, language="pt_BR"))
    try:
        for k, v in json.load(open(os.path.join(AQUI, "feriados_extra.json"), encoding="utf-8")).items():
            f[date.fromisoformat(k)] = v
    except Exception:
        pass
    return f


def nome_do_feriado(d):
    return feriados(d.year).get(d)
