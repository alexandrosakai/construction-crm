#!/usr/bin/env python3
"""Cadastra no robô os vendedores de vendedores.json, no grupo "vendedores" (sem mandar mensagem de boas-vindas).
Obrigatório: a limpeza do robô apaga, a cada 15 min, o histórico de quem não está cadastrado.

  python3 cadastrar_vendedores.py            # mostra o que faria
  python3 cadastrar_vendedores.py --aplicar  # grava
"""
import json
import os
import subprocess
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
from rodar_dia import normalizar_numero  # noqa: E402

aplicar = "--aplicar" in sys.argv
vend = json.load(open(os.path.join(AQUI, "vendedores.json"), encoding="utf-8"))
ok, ruins = [], []
for v in vend:
    n = normalizar_numero(v.get("numero", ""))
    (ok if n else ruins).append((v, n))
print(f"{len(ok)} com número válido, {len(ruins)} sem número ou inválido: {', '.join(v['nome'] for v, _ in ruins) or '-'}")
for v, n in ok:
    print(f"  {v['cod']} {v['nome']:<10} -> {n}")
if aplicar and ok:
    for v, n in ok:
        sql = ("insert into contacts(nome, numero, grupo, ativo) values (:'nm', :'n', 'vendedores', true) "
               "on conflict (numero) do update set nome = excluded.nome, grupo = 'vendedores', ativo = true")
        subprocess.run(["docker", "exec", "-i", "wa-stack-postgres-1", "psql", "-U", "postgres", "-d", "wa", "-v", "ON_ERROR_STOP=1",
                        "-v", f"nm={v['nome']}", "-v", f"n={n}"], input=sql, text=True, check=True, capture_output=True)
    print("Cadastro gravado.")
elif not aplicar:
    print("(simulação: use --aplicar para gravar)")
