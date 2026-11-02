import csv, io, json, os, sqlite3
from datetime import date
from flask import Blueprint, Response, g, jsonify, render_template, request

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DIAGNOSTICO_DB", os.path.join(HERE, "diagnostico.db"))
MODULOS = json.load(open(os.path.join(HERE, "modulos.json"), encoding="utf8"))
MOD_IDS = {m["id"] for m in MODULOS}

bp = Blueprint("diagnostico", __name__, url_prefix="/diagnostico",
               template_folder="templates")

SCHEMA = """
CREATE TABLE IF NOT EXISTS diag(id INTEGER PRIMARY KEY, empresa TEXT NOT NULL, consultor TEXT,
  data TEXT, concl TEXT NOT NULL DEFAULT '{}');
CREATE TABLE IF NOT EXISTS resp(diag_id INTEGER, mod TEXT, idx INTEGER, valor INTEGER,
  PRIMARY KEY(diag_id, mod, idx));
CREATE TABLE IF NOT EXISTS meta(diag_id INTEGER, mod TEXT, evidencias TEXT DEFAULT '',
  parecer TEXT DEFAULT '', PRIMARY KEY(diag_id, mod));
CREATE TABLE IF NOT EXISTS acao(id INTEGER PRIMARY KEY, diag_id INTEGER, mod TEXT, idx INTEGER,
  acao TEXT, motivo TEXT DEFAULT '', responsavel TEXT DEFAULT '', prazo TEXT DEFAULT '',
  onde TEXT DEFAULT '', como TEXT DEFAULT '', custo TEXT DEFAULT '',
  prioridade TEXT DEFAULT 'Média', status TEXT DEFAULT 'A fazer', obs TEXT DEFAULT '');
"""
ACAO_CAMPOS = ["acao", "motivo", "responsavel", "prazo", "onde", "como", "custo",
               "prioridade", "status", "obs", "mod"]


def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.executescript(SCHEMA)
    return g.db


@bp.teardown_app_request
def _close(_):
    d = g.pop("db", None)
    if d:
        d.close()


@bp.before_request
def _auth():
    from flask import current_app
    if "login_manager" in current_app.extensions or hasattr(current_app, "login_manager"):
        from flask_login import current_user
        if not current_user.is_authenticated:
            return current_app.login_manager.unauthorized()


def _get(did):
    r = db().execute("SELECT * FROM diag WHERE id=?", (did,)).fetchone()
    if not r:
        from flask import abort
        abort(404)
    return r


def _estado(did):
    d = _get(did)
    resp = {}
    for r in db().execute("SELECT mod,idx,valor FROM resp WHERE diag_id=?", (did,)):
        resp.setdefault(r["mod"], {})[str(r["idx"])] = r["valor"]
    meta = {r["mod"]: {"evidencias": r["evidencias"], "parecer": r["parecer"]}
            for r in db().execute("SELECT * FROM meta WHERE diag_id=?", (did,))}
    acoes = [dict(r) for r in db().execute(
        "SELECT * FROM acao WHERE diag_id=? ORDER BY id", (did,))]
    return {"id": d["id"], "empresa": d["empresa"], "consultor": d["consultor"],
            "data": d["data"], "concl": json.loads(d["concl"]),
            "resp": resp, "meta": meta, "acoes": acoes}


@bp.get("/")
def pagina():
    return render_template("diagnostico/index.html")


@bp.get("/api/modulos")
def api_modulos():
    return jsonify(MODULOS)


@bp.get("/api/diagnosticos")
def api_lista():
    return jsonify([dict(r) for r in db().execute(
        "SELECT id,empresa,consultor,data FROM diag ORDER BY id DESC")])


@bp.post("/api/diagnosticos")
def api_criar():
    j = request.get_json(force=True)
    if not (j.get("empresa") or "").strip():
        return jsonify(erro="Informe a empresa"), 400
    c = db().execute("INSERT INTO diag(empresa,consultor,data) VALUES(?,?,?)",
                     (j["empresa"].strip(), j.get("consultor", ""),
                      j.get("data") or date.today().isoformat()))
    db().commit()
    return jsonify(_estado(c.lastrowid)), 201


@bp.get("/api/diagnosticos/<int:did>")
def api_estado(did):
    return jsonify(_estado(did))


@bp.delete("/api/diagnosticos/<int:did>")
def api_excluir(did):
    _get(did)
    for t in ("resp", "meta", "acao"):
        db().execute(f"DELETE FROM {t} WHERE diag_id=?", (did,))
    db().execute("DELETE FROM diag WHERE id=?", (did,))
    db().commit()
    return "", 204


@bp.put("/api/diagnosticos/<int:did>/resposta")
def api_resposta(did):
    _get(did)
    j = request.get_json(force=True)
    if j.get("mod") not in MOD_IDS:
        return jsonify(erro="módulo inválido"), 400
    n = len(next(m for m in MODULOS if m["id"] == j["mod"])["perguntas"])
    idx, v = j.get("idx"), j.get("valor")
    if not isinstance(idx, int) or not 0 <= idx < n or v not in (None, -1, 0, 1, 2, 3, 4):
        return jsonify(erro="dados inválidos"), 400
    if v is None:
        db().execute("DELETE FROM resp WHERE diag_id=? AND mod=? AND idx=?", (did, j["mod"], idx))
    else:
        db().execute("REPLACE INTO resp VALUES(?,?,?,?)", (did, j["mod"], idx, v))
    db().commit()
    return "", 204


@bp.put("/api/diagnosticos/<int:did>/meta")
def api_meta(did):
    _get(did)
    j = request.get_json(force=True)
    if j.get("mod") not in MOD_IDS:
        return jsonify(erro="módulo inválido"), 400
    db().execute("REPLACE INTO meta VALUES(?,?,?,?)",
                 (did, j["mod"], j.get("evidencias", ""), j.get("parecer", "")))
    db().commit()
    return "", 204


@bp.put("/api/diagnosticos/<int:did>/conclusoes")
def api_concl(did):
    _get(did)
    db().execute("UPDATE diag SET concl=? WHERE id=?",
                 (json.dumps(request.get_json(force=True), ensure_ascii=False), did))
    db().commit()
    return "", 204


@bp.post("/api/diagnosticos/<int:did>/gerar-acoes")
def api_gerar(did):
    """Cria uma ação para cada requisito com nota <= limite que ainda não tem ação."""
    _get(did)
    limite = int((request.get_json(silent=True) or {}).get("limite", 2))
    existentes = {(r["mod"], r["idx"]) for r in db().execute(
        "SELECT mod,idx FROM acao WHERE diag_id=? AND idx IS NOT NULL", (did,))}
    novas = 0
    for r in db().execute("SELECT mod,idx,valor FROM resp WHERE diag_id=? AND valor BETWEEN 0 AND ?",
                          (did, limite)).fetchall():
        if (r["mod"], r["idx"]) in existentes:
            continue
        m = next(m for m in MODULOS if m["id"] == r["mod"])
        pergunta = m["perguntas"][r["idx"]]
        prio = "Alta" if r["valor"] <= 1 else "Média"
        db().execute("INSERT INTO acao(diag_id,mod,idx,acao,motivo,prioridade) VALUES(?,?,?,?,?,?)",
                     (did, r["mod"], r["idx"], "Adequar requisito: " + pergunta.rstrip("? "),
                      f"Nota {r['valor']}/4 em “{pergunta}”", prio))
        novas += 1
    db().commit()
    return jsonify(criadas=novas, acoes=_estado(did)["acoes"])


@bp.post("/api/diagnosticos/<int:did>/acoes")
def api_acao_nova(did):
    _get(did)
    j = request.get_json(force=True)
    if j.get("mod") not in MOD_IDS:
        return jsonify(erro="módulo inválido"), 400
    c = db().execute("INSERT INTO acao(diag_id,mod,acao) VALUES(?,?,?)",
                     (did, j["mod"], j.get("acao") or "Nova ação"))
    db().commit()
    return jsonify(dict(db().execute("SELECT * FROM acao WHERE id=?", (c.lastrowid,)).fetchone())), 201


@bp.put("/api/acoes/<int:aid>")
def api_acao_edit(aid):
    j = request.get_json(force=True)
    sets = {k: v for k, v in j.items() if k in ACAO_CAMPOS and isinstance(v, str)}
    if sets.get("mod", "x") not in MOD_IDS | {"x"}:
        return jsonify(erro="módulo inválido"), 400
    if sets:
        db().execute(f"UPDATE acao SET {','.join(k + '=?' for k in sets)} WHERE id=?",
                     (*sets.values(), aid))
        db().commit()
    return "", 204


@bp.delete("/api/acoes/<int:aid>")
def api_acao_del(aid):
    db().execute("DELETE FROM acao WHERE id=?", (aid,))
    db().commit()
    return "", 204


@bp.get("/api/diagnosticos/<int:did>/acoes.csv")
def api_csv(did):
    e = _estado(did)
    nomes = {m["id"]: m["nome"] for m in MODULOS}
    out = io.StringIO()
    w = csv.writer(out, delimiter=";")
    w.writerow(["Módulo", "Ação (O quê)", "Por quê", "Quem", "Quando", "Onde", "Como",
                "Quanto", "Prioridade", "Status", "Observações"])
    for a in e["acoes"]:
        w.writerow([nomes[a["mod"]], a["acao"], a["motivo"], a["responsavel"], a["prazo"],
                    a["onde"], a["como"], a["custo"], a["prioridade"], a["status"], a["obs"]])
    return Response("﻿" + out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=plano_acao_{did}.csv"})
