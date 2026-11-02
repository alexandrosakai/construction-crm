"""Backend do app Checklist Empresa Exemplo: recebe envios, valida, guarda em SQLite e fotos em disco."""
import base64, csv, hmac, io, json, os, secrets, sqlite3, threading, time, urllib.request
from datetime import datetime
from flask import Flask, Response, abort, g, jsonify, request, send_file
from PIL import Image, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("CHECKLIST_DATA", "/var/lib/exemplo-checklist")
FOTOS = os.path.join(DATA, "fotos")
DB = os.path.join(DATA, "checklist.db")
ADMIN_PIN = os.environ.get("CHECKLIST_ADMIN_PIN", "")
INTERNO = os.environ.get("CHECKLIST_INTERNO", "")
CATALOGO = json.load(open(os.path.join(HERE, "checklists.json"), encoding="utf8"))
POR_ID = {c["id"]: c for c in CATALOGO}
MAX_FOTOS_CAMPO, MAX_FOTO_BYTES, MAX_TEXTO = 8, 6_000_000, 2000
os.makedirs(FOTOS, exist_ok=True)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 40 * 1024 * 1024

SCHEMA = """CREATE TABLE IF NOT EXISTS resposta(
  id INTEGER PRIMARY KEY, cid TEXT NOT NULL, criado TEXT NOT NULL, quem TEXT, extra TEXT,
  nok INTEGER NOT NULL DEFAULT 0, dados TEXT NOT NULL, fotos TEXT NOT NULL DEFAULT '{}', envio_id TEXT UNIQUE);
CREATE INDEX IF NOT EXISTS ix_resp_cid ON resposta(cid, id);"""


def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
        g.db.executescript(SCHEMA)
        try:                                  # coluna do link personalizado (tarefa enviada pelo WhatsApp)
            g.db.execute("ALTER TABLE resposta ADD COLUMN tarefa TEXT")
        except sqlite3.OperationalError:
            pass
    return g.db


@app.teardown_appcontext
def _close(_):
    d = g.pop("db", None)
    if d:
        d.close()


# limitação simples por IP (envio público)
_hits = {}
def _limite(ip, n=30, janela=600):
    agora = time.time()
    h = [t for t in _hits.get(ip, []) if agora - t < janela]
    if len(h) >= n:
        return False
    h.append(agora)
    _hits[ip] = h
    return True


def _ip():
    return request.headers.get("X-Real-IP") or request.remote_addr


def _admin():
    pin = request.headers.get("X-Admin", "")
    if not ADMIN_PIN or not hmac.compare_digest(pin.encode(), ADMIN_PIN.encode()):
        abort(401)


def _salva_foto(data_url):
    try:
        raw = base64.b64decode(data_url.split(",", 1)[1], validate=False)
        if len(raw) > MAX_FOTO_BYTES:
            raise ValueError("grande")
        im = Image.open(io.BytesIO(raw))
        im.verify()
        im = ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert("RGB")
        im.thumbnail((1600, 1600))
    except Exception:
        raise ValueError("Foto inválida")
    nome = secrets.token_hex(16) + ".jpg"      # nome imprevisível; metadados removidos ao reencodar
    im.save(os.path.join(FOTOS, nome), "JPEG", quality=80, optimize=True)
    return nome


def _valida(cl, corpo):
    """Retorna (dados, nok, fotos) ou levanta ValueError com mensagem amigável."""
    resp, nok, fotos, tem_nok = {}, 0, {}, False
    ent = corpo.get("dados") or {}
    for c in cl["campos"]:
        k, v = c["k"], ent.get(c["k"])
        if c["t"] == "itens":
            v = v if isinstance(v, dict) else {}
            r = {}
            for it in c["itens"]:
                x = v.get(it)
                if x == "Não OK":          # valor antigo (fila offline de versões anteriores)
                    x = "COM PROBLEMA"
                if x not in ("OK", "COM PROBLEMA"):
                    raise ValueError(f"Responda todos os itens de “{c['label']}”.")
                r[it] = x
                if x == "COM PROBLEMA":
                    nok += 1; tem_nok = True
            resp[k] = r
        elif c["t"] == "foto":
            lst = v if isinstance(v, list) else []
            if c["req"] and not lst:
                raise ValueError(f"Envie ao menos uma foto em “{c['label']}”.")
            if len(lst) > MAX_FOTOS_CAMPO:
                raise ValueError("Muitas fotos.")
            fotos[k] = lst
        else:
            v = (v or "").strip() if isinstance(v, str) else ""
            if len(v) > MAX_TEXTO:
                raise ValueError(f"Texto muito longo em “{c['label']}”.")
            if c["t"] == "select" and v and v not in c["opcoes"]:
                raise ValueError(f"Opção inválida em “{c['label']}”.")
            resp[k] = v
    for c in cl["campos"]:   # obrigatórios (depois, para saber se há COM PROBLEMA)
        if c["t"] in ("select", "text", "textarea"):
            obrig = c["req"] or (c.get("req_se_nok") and tem_nok)
            if obrig and not resp[c["k"]]:
                raise ValueError(f"Preencha “{c['label']}”" + (" (há itens “COM PROBLEMA”)." if not c["req"] else "."))
    return resp, nok, fotos


@app.get("/catalogo")
def catalogo():
    return jsonify(CATALOGO)


@app.post("/enviar")
def enviar():
    if not _limite(_ip()):
        return jsonify(erro="Muitos envios. Tente mais tarde."), 429
    corpo = request.get_json(silent=True) or {}
    cl = POR_ID.get(corpo.get("checklist"))
    if not cl:
        return jsonify(erro="Checklist desconhecido"), 400
    eid = str(corpo.get("envio_id") or "")[:64] or None
    if eid and db().execute("SELECT 1 FROM resposta WHERE envio_id=?", (eid,)).fetchone():
        return jsonify(ok=True, repetido=True)          # reenvio da fila offline
    try:
        dados, nok, fotos_in = _valida(cl, corpo)
        fotos = {k: [_salva_foto(u) for u in lst] for k, lst in fotos_in.items()}
    except ValueError as e:
        return jsonify(erro=str(e)), 400
    quem = next((dados[c["k"]] for c in cl["campos"] if c["k"] in ("motorista", "operador", "responsavel", "colaborador")), "")
    extra = dados.get("veiculo", "")
    tarefa = "".join(ch for ch in str(corpo.get("tarefa") or "") if ch.isalnum())[:64] or None
    db().execute("INSERT INTO resposta(cid,criado,quem,extra,nok,dados,fotos,envio_id,tarefa) VALUES(?,?,?,?,?,?,?,?,?)",
                 (cl["id"], datetime.now().isoformat(timespec="seconds"), quem, extra, nok,
                  json.dumps(dados, ensure_ascii=False), json.dumps(fotos), eid, tarefa))
    db().commit()
    threading.Thread(target=_avisa_whatsapp, args=(tarefa, cl["id"], quem), daemon=True).start()
    return jsonify(ok=True, nok=nok), 201


def _avisa_whatsapp(token, cid, nome):
    """Melhor esforço: o fluxo de tarefas do WhatsApp conclui a tarefa e manda o incentivo. Se falhar, a conferência periódica resolve depois."""
    try:
        req = urllib.request.Request("http://127.0.0.1:5678/webhook/checklist-concluido",
                                     data=json.dumps({"token": token or "", "cid": cid, "nome": nome}).encode(),
                                     headers={"Content-Type": "application/json", "X-Interno": INTERNO}, method="POST")
        urllib.request.urlopen(req, timeout=5).read()
    except Exception as e:
        print("aviso ao WhatsApp falhou:", e, flush=True)


@app.get("/foto/<nome>")
def foto(nome):
    if not (len(nome) == 36 and nome.endswith(".jpg") and nome[:-4].isalnum()):
        abort(404)
    p = os.path.join(FOTOS, nome)
    if not os.path.isfile(p):
        abort(404)
    return send_file(p, mimetype="image/jpeg", max_age=86400)


def _linha(r):
    return {"id": r["id"], "cid": r["cid"], "titulo": POR_ID[r["cid"]]["titulo"] if r["cid"] in POR_ID else r["cid"],
            "criado": r["criado"], "quem": r["quem"], "extra": r["extra"], "nok": r["nok"],
            "dados": json.loads(r["dados"]), "fotos": json.loads(r["fotos"])}


@app.get("/admin/respostas")
def admin_respostas():
    _admin()
    q, args = "SELECT * FROM resposta WHERE 1=1", []
    if request.args.get("cid"):
        q += " AND cid=?"; args.append(request.args["cid"])
    if request.args.get("de"):
        q += " AND criado>=?"; args.append(request.args["de"])
    if request.args.get("ate"):
        q += " AND criado<?"; args.append(request.args["ate"] + "T99")
    if request.args.get("so_nok") == "1":
        q += " AND nok>0"
    q += " ORDER BY id DESC LIMIT ?"
    args.append(min(int(request.args.get("limite", 300)), 2000))
    return jsonify([_linha(r) for r in db().execute(q, args)])


@app.delete("/admin/respostas/<int:rid>")
def admin_del(rid):
    _admin()
    r = db().execute("SELECT fotos FROM resposta WHERE id=?", (rid,)).fetchone()
    if not r:
        abort(404)
    for lst in json.loads(r["fotos"]).values():
        for n in lst:
            try: os.remove(os.path.join(FOTOS, n))
            except OSError: pass
    db().execute("DELETE FROM resposta WHERE id=?", (rid,)); db().commit()
    return "", 204


@app.get("/admin/csv")
def admin_csv():
    _admin()
    out = io.StringIO(); w = csv.writer(out, delimiter=";")
    w.writerow(["Data/hora", "Checklist", "Responsável", "Veículo", "Itens COM PROBLEMA", "Detalhe COM PROBLEMA", "Observações"])
    for r in db().execute("SELECT * FROM resposta ORDER BY id DESC"):
        l = _linha(r)
        nok = "; ".join(f"{i}" for g_ in l["dados"].values() if isinstance(g_, dict) for i, v in g_.items() if v == "COM PROBLEMA")
        obs = " | ".join(str(l["dados"].get(k, "")) for k in ("ajustes", "obs") if l["dados"].get(k))
        w.writerow([l["criado"].replace("T", " "), l["titulo"], l["quem"], l["extra"], l["nok"], nok, obs])
    return Response("﻿" + out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=checklists.csv"})


@app.get("/interno/concluido")
def interno_concluido():
    """Usado pelo sistema de WhatsApp: o checklist da tarefa de hoje já foi preenchido? (por link personalizado OU pelo nome do responsável)"""
    k = request.headers.get("X-Interno", "")
    if not INTERNO or not hmac.compare_digest(k.encode(), INTERNO.encode()):
        abort(401)
    tok = "".join(ch for ch in request.args.get("token", "") if ch.isalnum())[:64] or "-"
    desde = request.args.get("desde") or request.args.get("data", "")
    op = ">=" if request.args.get("desde") else "="
    r = db().execute(f"SELECT criado FROM resposta WHERE cid=? AND substr(criado,1,10){op}? AND (tarefa=? OR lower(quem)=lower(?)) ORDER BY id DESC LIMIT 1",
                     (request.args.get("cid", ""), desde, tok, request.args.get("nome", ""))).fetchone()
    return jsonify(concluido=bool(r), em=r["criado"] if r else None)


@app.get("/saude")
def saude():
    return "ok"
