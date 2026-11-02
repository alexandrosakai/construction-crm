"""Envio do relatório estruturado (HTML com tabelas + CSV em anexo) para o e-mail do admin, pelo SMTP do Gmail."""
import csv
import html
import io
import smtplib
from email.message import EmailMessage

import buscar_emails as be

COR = {"lida": "#1F7A45", "entregue": "#1F7A45", "sem_confirmacao": "#9A5B00", "nao_enviada": "#B42318", "na_fila": "#5D6B72", "pausada": "#5D6B72"}
ROT = {"lida": "lida", "entregue": "entregue", "sem_confirmacao": "sem confirmação", "nao_enviada": "NÃO enviada", "na_fila": "na fila", "pausada": "pausada"}
E = html.escape


def csv_texto(cabecalho, linhas):
    s = io.StringIO()
    w = csv.writer(s, delimiter=";")
    w.writerow(cabecalho)
    w.writerows(linhas)
    return s.getvalue()


def tabela(cabecalho, linhas):
    """linhas: lista de listas; cada célula é texto ou HTML já pronto marcado como ('html', '<b>..</b>')."""
    th = "".join(f'<th style="text-align:left;padding:8px 10px;background:#1e3a8a;color:#fff;font-weight:600;font-size:13px">{E(c)}</th>' for c in cabecalho)
    tr = []
    for i, l in enumerate(linhas):
        bg = "#F6F8F7" if i % 2 else "#FFFFFF"
        tds = "".join(f'<td style="padding:8px 10px;border-bottom:1px solid #DDE3E1;vertical-align:top;font-size:13.5px;background:{bg}">'
                      f'{c[1] if isinstance(c, tuple) else E(str(c)).replace(chr(10), "<br>")}</td>' for c in l)
        tr.append(f"<tr>{tds}</tr>")
    return f'<table style="border-collapse:collapse;width:100%;margin:6px 0 18px">{f"<tr>{th}</tr>"}{"".join(tr)}</table>'


def kpi(valor, rotulo, cor="#1C2A30"):
    return (f'<td style="padding:12px 14px;background:#F6F8F7;border-radius:8px;text-align:center;min-width:90px">'
            f'<div style="font-size:24px;font-weight:700;color:{cor}">{valor}</div><div style="font-size:12px;color:#5D6B72">{E(rotulo)}</div></td>')


def pagina(titulo, subtitulo, kpis, blocos):
    cards = "".join(kpis)
    corpo = "".join(f'<h3 style="margin:18px 0 4px;font-size:16px;color:#1C2A30">{E(t)}</h3>{c}' for t, c in blocos if c)
    return (f'<div style="font-family:Segoe UI,Arial,sans-serif;max-width:900px;margin:auto;color:#1C2A30">'
            f'<h2 style="margin:0 0 2px">{E(titulo)}</h2><div style="color:#5D6B72;margin-bottom:12px">{E(subtitulo)}</div>'
            f'<table style="border-spacing:8px 0;margin:0 -8px 8px"><tr>{cards}</tr></table>{corpo}'
            f'<p style="color:#5D6B72;font-size:12px;margin-top:24px">Gerado automaticamente pelo robô de envios aos vendedores.</p></div>')


def enviar(assunto, corpo_html, anexos=()):
    e = be.env()
    msg = EmailMessage()
    msg["Subject"] = assunto
    msg["From"] = f"Robô Empresa Exemplo <{e['GMAIL_USER']}>"
    msg["To"] = e["GMAIL_USER"]
    msg.set_content("Este relatório está em HTML. Abra em um leitor de e-mail que mostre tabelas.")
    msg.add_alternative(corpo_html, subtype="html")
    for nome, txt in anexos:
        msg.add_attachment(txt.encode("utf-8-sig"), maintype="text", subtype="csv", filename=nome)
    with smtplib.SMTP_SSL("smtp.example.com", 465, timeout=40) as s:
        s.login(e["GMAIL_USER"], e["GMAIL_APP_PASSWORD"])
        s.send_message(msg)
