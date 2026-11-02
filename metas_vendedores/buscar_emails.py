#!/usr/bin/env python3
"""Baixa do Gmail os dois PDFs (Meta 3.0 e Orçamentos pendentes) de um dia.

Uso: python3 buscar_emails.py AAAA-MM-DD pasta_saida
Lê GMAIL_USER / GMAIL_APP_PASSWORD de /opt/whatsapp-stack/.env
"""
import email
import imaplib
import os
import sys
from datetime import date, timedelta
from email.header import decode_header, make_header

REMETENTE = "user@example.com"
ENV = "/opt/whatsapp-stack/.env"


def env():
    return dict(l.strip().split("=", 1) for l in open(ENV) if "=" in l and not l.startswith("#"))


def baixar(dia, pasta):
    e = env()
    d = date.fromisoformat(dia)
    m = imaplib.IMAP4_SSL("imap.example.com")
    m.login(e["GMAIL_USER"], e["GMAIL_APP_PASSWORD"])
    m.select("INBOX", readonly=True)
    MESES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    fmt = lambda x: f"{x.day:02d}-{MESES[x.month - 1]}-{x.year}"  # IMAP exige mês em inglês, independente do locale do servidor
    _, ids = m.search(None, f'(FROM "{REMETENTE}" SINCE {fmt(d)} BEFORE {fmt(d + timedelta(days=1))})')
    achados = {}
    for i in ids[0].split():
        _, dados = m.fetch(i, "(RFC822)")
        msg = email.message_from_bytes(dados[0][1])
        assunto = str(make_header(decode_header(msg["Subject"]))).upper()
        tipo = "meta" if "META POR VENDEDOR" in assunto else "orcamentos" if "ORÇAMENTOS PENDENTES" in assunto else None
        if not tipo:
            continue
        for parte in msg.walk():
            if parte.get_content_type() == "application/pdf" or (parte.get_filename() or "").lower().endswith(".pdf"):
                os.makedirs(pasta, exist_ok=True)
                caminho = os.path.join(pasta, f"{tipo}.pdf")
                open(caminho, "wb").write(parte.get_payload(decode=True))
                achados[tipo] = caminho
    m.logout()
    return achados


if __name__ == "__main__":
    r = baixar(sys.argv[1], sys.argv[2])
    print(r)
    sys.exit(0 if len(r) == 2 else 1)
