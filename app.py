print('start')
import os
import threading
from slugify import slugify as _slugify

import time
import traceback
from datetime import datetime
from flask import (
    Flask, render_template, jsonify, request,
    redirect, url_for, session, flash
)
from PIL import Image

import pandas as pd
from sqlalchemy import create_engine, text as sa_text
import pymysql
from pymysql.cursors import DictCursor
import bcrypt
from flask_login import (
    LoginManager, UserMixin, login_user,
    logout_user, current_user, login_required
)
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

import logging, json
from flask import request
from sqlalchemy import text as sa_text
from werkzeug.wrappers import Request
from urllib.parse import parse_qs
#=========================================================================================#
app = Flask(__name__, static_folder="static", template_folder="templates")
app.config['SECRET_KEY'] = os.environ.get("FLASK_SECRET_KEY", "dev-super-secret-please-change")
class HTTPMethodOverrideMiddleware:
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        # método atual
        method = (environ.get('REQUEST_METHOD') or '').upper()

        # 1) header tem prioridade e NÃO consome body
        override = environ.get('HTTP_X_HTTP_METHOD_OVERRIDE')

        # 2) se não houver header, checa query string _method=PUT/PATCH/DELETE
        if not override:
            qs = environ.get('QUERY_STRING') or ''
            override = (parse_qs(qs).get('_method') or [None])[0]

        # 3) aplica override apenas se existir
        if override:
            environ['REQUEST_METHOD'] = override.upper()

        return self.app(environ, start_response)
app.wsgi_app = HTTPMethodOverrideMiddleware(app.wsgi_app)
# Atrás do Nginx: respeita X-Forwarded-For / X-Forwarded-Proto (IP real e https)
from werkzeug.middleware.proxy_fix import ProxyFix
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
#=========================================================================================#


DB_USER = os.environ.get("DB_USER", "root")
DB_PASS = os.environ["DB_PASS"]  # obrigatória: sem valor padrão no código
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = int(os.environ.get("DB_PORT", 3306))
DB_NAME = os.environ.get("DB_NAME", "app_db")
DB_URI = f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
#=========================================================================================#
def build_engine(): # Opcional: engine do SQLAlchemy (útil para relatórios/queries maiores)
    return create_engine(DB_URI, pool_recycle=3600, pool_pre_ping=True)
#=========================================================================================#
def get_db_connection():
    return pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME,
        port=DB_PORT,
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=False,
    )
engine = build_engine()
#=========================================================================================#
login_manager = LoginManager(app)
login_manager.login_view = "login"
#=========================================================================================#
# PERMISSÕES — cada usuário tem um nível de acesso (perfil) e, por módulo, as ações liberadas
ACOES = {"ver": "Ver", "inserir": "Inserir", "alterar": "Alterar", "excluir": "Excluir"}
MODULOS = [
    # (chave, nome na tela, ações que o módulo tem)
    ("obras",      "Obras",                      ("ver", "inserir", "alterar", "excluir")),
    ("etapas",     "Etapas das obras",           ("ver", "inserir", "excluir")),
    ("visitas",    "Visitas das obras",          ("ver", "inserir", "excluir")),
    ("relatorios", "Relatórios",                 ("ver",)),
    ("pessoas",    "Profissionais",              ("ver", "inserir", "alterar")),
    ("pesquisas",  "Pesquisas",                  ("ver", "inserir")),
]
_MOD_ACOES = {m: acoes for m, _, acoes in MODULOS}

def _perm_todas(exceto=()):
    return {m: list(acoes) for m, _, acoes in MODULOS if m not in exceto}

# Níveis de acesso, do maior para o menor. "permissoes" None = acesso total.
PERFIS = {
    "admin":    {"nome": "Administrador", "descricao": "Acesso total: vê os dados de todos e cadastra usuários.", "permissoes": None},
    "gerente":  {"nome": "Gerente", "descricao": "Tudo, menos cadastrar usuários.", "permissoes": _perm_todas(exceto=("usuarios",))},
    "operador": {"nome": "Operador", "descricao": "Cadastra e altera obras, etapas e visitas. Não exclui.",
                 "permissoes": {"obras": ["ver", "inserir", "alterar"], "etapas": ["ver", "inserir"],
                                "visitas": ["ver", "inserir"], "pessoas": ["ver", "inserir", "alterar"],
                                "pesquisas": ["ver", "inserir"]}},
    "consulta": {"nome": "Consulta", "descricao": "Só visualiza obras e relatórios.",
                 "permissoes": {"obras": ["ver"], "etapas": ["ver"], "visitas": ["ver"],
                                "relatorios": ["ver"], "pessoas": ["ver"]}},
    "personalizado": {"nome": "Personalizado", "descricao": "Você marca o que a pessoa pode fazer.", "permissoes": {}},
}

STATUS_USUARIO = {"aprovado": "Ativo", "pendente": "Pendente", "bloqueado": "Bloqueado"}

def _limpar_permissoes(perm):
    """Mantém só módulos/ações que existem."""
    limpo = {}
    for m, acoes in (perm or {}).items():
        validas = [a for a in _MOD_ACOES.get(m, ()) if a in (acoes or [])]
        if validas:
            limpo[m] = validas
    return limpo

def _ler_permissoes(raw):
    if not raw:
        return {}
    try:
        return _limpar_permissoes(json.loads(raw))
    except Exception:
        return {}

def _permissoes_efetivas(perfil, raw):
    """Níveis prontos seguem PERFIS; só o Personalizado usa o que foi salvo. None = acesso total."""
    if perfil in PERFIS and perfil != "personalizado":
        return PERFIS[perfil]["permissoes"]
    return _ler_permissoes(raw)

class User(UserMixin):
    def __init__(self, id, username, password, email, name,
                 status, categoria, profile_picture, member_status,
                 telefone, created_at, perfil=None, permissoes=None, tipo_usuario=None):
        self.id = str(id)
        self.username = username
        self.password = password
        self.email = email
        self.name = name
        self.status = status
        self.categoria = categoria
        self.profile_picture = profile_picture
        self.member_status = member_status
        self.telefone = telefone
        self.created_at = created_at
        self.perfil = perfil or "personalizado"
        self.permissoes = _permissoes_efetivas(self.perfil, permissoes) or {}
        self.tipo_usuario = tipo_usuario
    @property
    def is_active(self):
        # considere "aprovado" como ativo
        return (self.status or "").lower() == "aprovado"

    @property
    def is_admin(self):
        return self.perfil == "admin"

    def pode(self, modulo, acao="ver"):
        if not self.is_active:
            return False
        if self.is_admin:
            return True
        return acao in self.permissoes.get(modulo, [])
#=========================================================================================#

import re
def _slugify(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return re.sub(r"_+", "_", s).strip("_")

@login_manager.user_loader
def load_user(user_id: str):
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, username, password, email, name, status, categoria,
                       member_status, telefone, created_at, perfil, permissoes, tipo_usuario,
                       COALESCE(profile_picture, 'PLACEHOLDER-IMAGE.png') AS profile_picture
                FROM users
                WHERE id=%s
            """, (user_id,))
            row = cur.fetchone()
        conn.close()
        if not row:
            return None
        return User(
            id=row["id"],
            username=row["username"],
            password=row["password"],
            email=row["email"],
            name=row["name"],
            status=row["status"],
            categoria=row["categoria"],
            profile_picture=row.get("profile_picture", "PLACEHOLDER-IMAGE.png"),
            member_status=row.get("member_status"),
            telefone=row.get("telefone"),
            created_at=row.get("created_at"),
            perfil=row.get("perfil"),
            permissoes=row.get("permissoes"),
            tipo_usuario=row.get("tipo_usuario"),
        )
    except Exception:
        traceback.print_exc()
        return None
#=========================================================================================#
def _garantir_colunas_permissao():
    """
    Cria as colunas perfil/permissoes em users (uma vez só) e migra quem já existia:
    - quem tinha categoria 'admin' (ou, se ninguém tiver, o usuário 'admin') vira Administrador
    - os demais usuários antigos viram Gerente, para continuarem acessando o que já acessavam
    """
    try:
        with engine.begin() as conn:
            cols = {r[0] for r in conn.execute(sa_text("""
                SELECT COLUMN_NAME FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'users'
            """))}
            if "perfil" in cols and "permissoes" in cols:
                return
            if "perfil" not in cols:
                conn.execute(sa_text("ALTER TABLE users ADD COLUMN perfil VARCHAR(30) NULL AFTER categoria"))
            if "permissoes" not in cols:
                conn.execute(sa_text("ALTER TABLE users ADD COLUMN permissoes TEXT NULL AFTER perfil"))

            admins = conn.execute(sa_text("SELECT id FROM users WHERE LOWER(categoria) = 'admin'")).fetchall()
            if not admins:
                admins = conn.execute(sa_text("SELECT id FROM users WHERE username = 'admin'")).fetchall()
            if not admins:
                admins = conn.execute(sa_text("SELECT MIN(id) FROM users")).fetchall()
            ids_admin = [r[0] for r in admins if r[0] is not None]
            for uid in ids_admin:
                conn.execute(sa_text("UPDATE users SET perfil = 'admin', permissoes = NULL WHERE id = :id"), {"id": uid})
            conn.execute(sa_text("""
                UPDATE users SET perfil = 'gerente', permissoes = :p WHERE perfil IS NULL
            """), {"p": json.dumps(PERFIS["gerente"]["permissoes"])})
            print("[permissoes] colunas criadas; administradores:", ids_admin)
    except Exception:
        traceback.print_exc()

_garantir_colunas_permissao()

from functools import wraps

# Telas de entrada, na ordem: o usuário cai na primeira que puder ver
_PAGINAS_INICIAIS = [
    ("relatorios", "ver", "relatorio_obras_page"),  # o painel é a primeira tela
    ("obras", "ver", "lista_obras"),
    ("obras", "inserir", "cadastro_obras"),
    ("pesquisas", "ver", "pesquisa_funcionario"),
    ("pessoas", "ver", "lista_profissionais"),
    ("usuarios", "ver", "lista_usuarios"),
]

def pagina_inicial(user=None):
    """URL da primeira tela que o usuário pode acessar, ou None se não tiver nenhuma."""
    user = user or current_user
    for modulo, acao, endpoint in _PAGINAS_INICIAIS:
        if user.pode(modulo, acao):
            return url_for(endpoint)
    return None

def requer_permissao(modulo, acao="ver"):
    """
    Exige login e a permissão no módulo. `acao` pode ser um dict por método HTTP,
    ex.: {"GET": "ver", "POST": "inserir"}.
    """
    def deco(f):
        @wraps(f)
        @login_required
        def wrapper(*args, **kwargs):
            acao_req = acao.get(request.method, "ver") if isinstance(acao, dict) else acao
            if current_user.pode(modulo, acao_req):
                return f(*args, **kwargs)
            nome_mod = dict((m, n) for m, n, _ in MODULOS).get(modulo, modulo)
            msg = f"Você não tem permissão para {ACOES.get(acao_req, acao_req).lower()} em {nome_mod}."
            if request.path.startswith("/api/") or request.path.endswith("/delete"):
                return jsonify(ok=False, error=msg), 403
            flash(msg, "error")
            destino = pagina_inicial()
            if not destino or destino == request.path:
                logout_user()
                flash("Seu usuário não tem acesso a nenhuma tela. Fale com o administrador.", "error")
                return redirect(url_for("login"))
            return redirect(destino)
        return wrapper
    return deco

@app.context_processor
def _injetar_permissoes():
    def pode(modulo, acao="ver"):
        return current_user.is_authenticated and current_user.pode(modulo, acao)
    return {"pode": pode}

#=========================================================================================#
# DADOS POR USUÁRIO — cada um vê só o que cadastrou; o administrador vê tudo
def _ve_tudo():
    return current_user.is_authenticated and current_user.is_admin

def _filtro_dono(alias):
    """(trecho SQL, parâmetros) que limita aos registros do usuário logado."""
    if _ve_tudo():
        return "1=1", {}
    return f"{alias}.created_by = :dono", {"dono": int(current_user.id)}

def _obra_e_do_usuario(obra_id):
    if _ve_tudo():
        return True
    try:
        obra_id = int(obra_id)
    except (TypeError, ValueError):
        return False
    with engine.begin() as conn:
        return bool(conn.execute(sa_text(
            "SELECT 1 FROM projects WHERE id = :id AND created_by = :dono"
        ), {"id": obra_id, "dono": int(current_user.id)}).first())

def dono_da_obra(f):
    """Barra o acesso a obras de outros usuários (use abaixo de @requer_permissao)."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        obra_id = (kwargs.get("obra_id") or request.values.get("obra_id") or request.form.get("id"))
        if obra_id and not _obra_e_do_usuario(obra_id):
            if request.path.startswith("/api/") or request.path.endswith("/delete"):
                return jsonify(ok=False, error="Obra não encontrada."), 404
            flash("Obra não encontrada.", "error")
            return redirect(url_for("lista_obras"))
        return f(*args, **kwargs)
    return wrapper
#=========================================================================================#
#=========================================================================================#
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        print('efetuando login')
        username = (request.form.get('username') or '').strip()
        password = request.form.get('password') or ''
        print('username:', username)

        if not username or not password:
            flash('Informe usuário e senha.', 'error')
            return render_template('login.html')

        try:
            connection = get_db_connection()
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT id, username, password, email, name, status, categoria,
                           member_status, telefone, created_at, perfil, permissoes, tipo_usuario,
                           COALESCE(profile_picture, 'PLACEHOLDER-IMAGE.png') AS profile_picture
                    FROM users
                    WHERE username=%s
                """, (username,))
                user = cursor.fetchone()
        except Exception as e:
            traceback.print_exc()
            flash('Erro de conexão ao banco.', 'error')
            return render_template('login.html')
        finally:
            try:
                connection.close()
            except:
                pass

        print('dados_user:', user)
        if not user:
            flash('Usuário não encontrado.', 'error')
            return render_template('login.html')

        # conferência de senha (bcrypt)
        user_password_hash = user['password'] or ''
        try:
            senha_confere = bcrypt.checkpw(password.encode('utf-8'), user_password_hash.encode('utf-8'))
        except Exception:
            # caso a coluna esteja em texto claro (não recomendado), cai no fallback
            senha_confere = (password == user_password_hash)

        if not senha_confere:
            flash('Senha incorreta. Tente novamente.', 'error')
            return render_template('login.html')

        # status de conta
        user_status = (user.get('status') or '').lower()
        if user_status == 'aprovado':
            user_obj = User(
                id=user['id'],
                username=user['username'],
                password=user['password'],
                email=user['email'],
                name=user['name'],
                status=user['status'],
                categoria=user.get('categoria'),
                profile_picture=user.get('profile_picture', 'PLACEHOLDER-IMAGE.png'),
                member_status=user.get('member_status'),
                telefone=user.get('telefone'),
                created_at=user.get('created_at'),
                perfil=user.get('perfil'),
                permissoes=user.get('permissoes'),
                tipo_usuario=user.get('tipo_usuario'),
            )
            # vai para a primeira tela que o nível de acesso dele permite
            destino = pagina_inicial(user_obj)
            if not destino:
                flash('Seu usuário ainda não tem acesso a nenhuma tela. Fale com o administrador.', 'error')
                return render_template('login.html')
            login_user(user_obj)
            flash('Login realizado com sucesso!', 'success')
            return redirect(destino)

        elif user_status == 'pendente':
            flash('Acesso não autorizado: sua conta está pendente.', 'error')
            return render_template('login.html')

        elif user_status == 'bloqueado':
            flash('Acesso bloqueado. Fale com o administrador.', 'error')
            return render_template('login.html')

        else:
            flash('Acesso negado: status de conta inválido.', 'error')
            return render_template('login.html')

    return render_template('login.html')
#=========================================================================================#
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        print('Efetuando registro')
        username = (request.form.get('username') or '').strip()
        name = (request.form.get('name') or '').strip()
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password') or ''
        telefone = (request.form.get('telefone') or '').strip()

        # NOVOS CAMPOS
        cidade = (request.form.get('cidade') or '').strip()
        data_nascimento = (request.form.get('data_nascimento') or '').strip()  # yyyy-mm-dd
        tipo_usuario = (request.form.get('tipo_usuario') or '').strip().lower()  # 'arquiteto'|'funcionario'
        razao_social = (request.form.get('razao_social') or '').strip() if tipo_usuario == 'arquiteto' else None

        if not username or not name or not email or not password:
            flash('Preencha todos os campos obrigatórios.', 'error')
            return render_template('register.html')

        if tipo_usuario not in ('arquiteto', 'funcionario'):
            flash('Selecione se é Arquiteto ou Funcionário.', 'error')
            return render_template('register.html')

        # gera hash bcrypt
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        try:
            connection = get_db_connection()
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1 FROM users WHERE email=%s OR username=%s", (email, username))
                existing_user = cursor.fetchone()
                if existing_user:
                    flash('Email ou username já registrado(s). Use outro(s) ou faça login.', 'error')
                    return render_template('register.html')

                categoria = 'user_padrao'
                default_picture = 'PLACEHOLDER-IMAGE.png'
                member_status = 'inativo'
                status = 'pendente'

                # quem se cadastra sozinho só responde pesquisas; o administrador libera o resto
                perfil = 'personalizado'
                permissoes = json.dumps({"pesquisas": ["ver", "inserir"]})

                # users
                cursor.execute("""
                    INSERT INTO users (
                       username, password, email, name, status, categoria, perfil, permissoes,
                       profile_picture, member_status, telefone,
                       cidade, data_nascimento, tipo_usuario, created_at
                    ) VALUES (
                       %s, %s, %s, %s, %s, %s, %s, %s,
                       %s, %s, %s,
                       %s, %s, %s, NOW()
                    )
                """, (
                    username, hashed_password, email, name, status, categoria, perfil, permissoes,
                    default_picture, member_status, telefone,
                    cidade if cidade else None,
                    data_nascimento if data_nascimento else None,
                    tipo_usuario
                ))
                user_id = cursor.lastrowid

                # detalhe por tipo
                if tipo_usuario == 'arquiteto':
                    cursor.execute("""
                        INSERT INTO architects (user_id, razao_social)
                        VALUES (%s, %s)
                    """, (user_id, razao_social if razao_social else None))
                else:
                    cursor.execute("""
                        INSERT INTO employees (user_id)
                        VALUES (%s)
                    """, (user_id,))

                connection.commit()

            flash('Registro realizado com sucesso! Faça login (após aprovação).', 'success')
            return redirect(url_for('login'))

        except Exception as e:
            traceback.print_exc()
            try:
                connection.rollback()
            except:
                pass
            flash(f'Ocorreu um erro ao registrar: {str(e)}', 'error')
            return render_template('register.html')
        finally:
            try:
                connection.close()
            except:
                pass

    return render_template('register.html')
#=========================================================================================#
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Você saiu da sua conta.', 'success')
    return redirect(url_for('login'))
#=========================================================================================#
@app.route('/novo_orcamento')
@requer_permissao('orcamentos', 'ver')
def novo_orcamento():
    return render_template('novo_orcamento.html') if os.path.exists(
        os.path.join(app.template_folder or 'templates', 'novo_orcamento.html')
    ) else "Área autenticada: Novo Orçamento"
#=========================================================================================#
# Página inicial: leva cada usuário para a primeira tela que ele pode acessar
@app.route('/')
@login_required
def index():
    return redirect(pagina_inicial() or url_for('logout'))
#=========================================================================================#
import json
import secrets
from pathlib import Path
from flask import current_app
from sqlalchemy import text as sa_text


# --- HELPER DE UPLOAD (NÃO É ROTA) ---
def ensure_upload_dir():
    up = Path(current_app.static_folder) / "uploads" / "visitas"
    up.mkdir(parents=True, exist_ok=True)
    return up

# ====== UTIL: DETECTA ONDE ESTÁ O HTML ======
def _resolve_cadastro_obras_source():
    """
    Retorna ('template', 'cadastro_obras.html') se existir em templates/,
    senão ('static', 'cadastro_obras.html') se existir em static/.
    Se não existir em nenhum, retorna (None, None).
    """
    tpl_path = Path(app.template_folder or "templates") / "cadastro_obras.html"
    if tpl_path.exists():
        return ("template", "cadastro_obras.html")
    static_path = Path(app.static_folder or "static") / "cadastro_obras.html"
    if static_path.exists():
        return ("static", "cadastro_obras.html")
    return (None, None)

import json, os, secrets
from pathlib import Path
from datetime import datetime as _dt
from flask import current_app, send_from_directory
from sqlalchemy import text as sa_text

#=====================================================================================
def _slugify(txt: str) -> str:
    import re, unicodedata
    if not txt: return ""
    s = unicodedata.normalize("NFD", txt)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s
# =============================================================
# ===================== LISTAR OBRAS =====================
# =============================================================
@app.route("/obras", methods=["GET"])
@requer_permissao('obras', 'ver')
def lista_obras():
    dono_sql, dono_params = _filtro_dono("o")
    with engine.begin() as conn:
        rows = conn.execute(sa_text("""
            SELECT
                o.id,
                o.numero_obra,
                o.nome,
                o.cidade,
                o.tipo_obra,
                o.padrao_obra,
                o.status,           -- <<< pega o status real
                o.data_inicio,
                o.proxima_visita,
                (o.proxima_visita IS NOT NULL AND o.proxima_visita < CURDATE()
                 AND UPPER(COALESCE(o.status, 'INICIANDO')) IN ('INICIANDO', 'ANDAMENTO')) AS visita_atrasada,
                COALESCE(e.qtd, 0)  AS etapas_count,
                COALESCE(v.qtd, 0)  AS visitas_count
            FROM projects o
            LEFT JOIN (
                SELECT obra_id, COUNT(*) AS qtd
                FROM project_stages
                GROUP BY obra_id
            ) e ON e.obra_id = o.id
            LEFT JOIN (
                SELECT obra_id, COUNT(*) AS qtd
                FROM project_visits
                GROUP BY obra_id
            ) v ON v.obra_id = o.id
            WHERE {dono}
            ORDER BY o.id DESC
        """.replace("{dono}", dono_sql)), dono_params).mappings().all()
    return render_template("lista_obras.html", obras=rows)

#================================================================
# ===================== ETAPAS DA OBRA =====================
# =============================================================
@app.route('/obras/<int:obra_id>/etapas/<int:etapa_id>/delete', methods=['POST'])
@requer_permissao('etapas', 'excluir')
@dono_da_obra
def delete_etapa(obra_id, etapa_id):
    """
    Deleta a etapa da obra (obra_etapas).
    Retorna JSON.
    """
    try:
        with engine.begin() as conn:
            result = conn.execute(sa_text("""
                DELETE FROM project_stages
                WHERE id = :eid AND obra_id = :oid
            """), {"eid": etapa_id, "oid": obra_id})

            if result.rowcount == 0:
                return jsonify({"ok": False, "error": "Etapa não encontrada para esta obra."}), 404

        return jsonify({"ok": True}), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e), "type": e.__class__.__name__}), 500



@app.route("/obras/<int:obra_id>/etapas", methods=["GET", "POST"])
@requer_permissao('etapas', {'GET': 'ver', 'POST': 'inserir'})
@dono_da_obra
def etapas_obra(obra_id):
    if request.method == "POST":
        data_prevista = request.form.get("data_prevista") or None
        tipo_etapa = request.form.get("tipo_etapa") or ""
        observacoes = request.form.get("observacoes") or ""
        if not data_prevista or not tipo_etapa:
            flash("Preencha data prevista e tipo da etapa.", "error")
            return redirect(url_for("etapas_obra", obra_id=obra_id))
        with engine.begin() as conn:
            conn.execute(sa_text("""
                INSERT INTO project_stages (obra_id, data_prevista, tipo_etapa, observacoes)
                VALUES (:obra_id, :data_prevista, :tipo_etapa, :observacoes)
            """), {
                "obra_id": obra_id,
                "data_prevista": data_prevista,
                "tipo_etapa": tipo_etapa,
                "observacoes": observacoes
            })
        flash("Etapa adicionada com sucesso.", "success")
        return redirect(url_for("etapas_obra", obra_id=obra_id))

    # GET: carregar obra e suas etapas
    with engine.begin() as conn:
        obra = conn.execute(sa_text("""
            SELECT id,
                   numero_obra,
                   nome,
                   data_inicio,
                   data_termino_prevista
            FROM projects
            WHERE id = :obra_id
        """), {"obra_id": obra_id}).mappings().first()
        if not obra:
            flash("Obra não encontrada.", "error")
            return redirect(url_for("lista_obras"))

        etapas = conn.execute(sa_text("""
            SELECT id, data_prevista, tipo_etapa, observacoes
            FROM project_stages
            WHERE obra_id = :obra_id
            ORDER BY (data_prevista IS NULL), data_prevista ASC, id DESC
        """), {"obra_id": obra_id}).mappings().all()

    return render_template("etapas_obra.html", obra=obra, etapas=etapas)
# =============================================================
# ===================== VISITAS DA OBRA =====================
# =============================================================
def _ensure_base_visitas_dir():
    """
    Garante a pasta base: static/uploads/visitas
    """
    base = Path(app.static_folder) / "uploads" / "visitas"
    base.mkdir(parents=True, exist_ok=True)
    return base

def _save_and_compress_image(src_file, dest_path):
    """
    Salva imagem comprimida:
      - Converte para RGB
      - Redimensiona se lado maior > 1600px
      - PNG mantém PNG; demais formatos salvam em JPEG qualidade 80
    """
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        img = Image.open(src_file.stream).convert("RGB")
    except Exception:
        # fallback: salva sem processar
        src_file.save(dest_path.as_posix())
        return dest_path

    max_side = 1600
    w, h = img.size
    scale = min(1.0, max_side / max(w, h))
    if scale < 1.0:
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

    ext = dest_path.suffix.lower()
    if ext == ".png":
        img.save(dest_path.as_posix(), format="PNG", optimize=True)
        return dest_path

    if ext not in (".jpg", ".jpeg"):
        dest_path = dest_path.with_suffix(".jpg")

    img.save(dest_path.as_posix(), format="JPEG", optimize=True, quality=80)
    return dest_path


@app.route('/obras/<int:obra_id>/visitas/<int:visita_id>/delete', methods=['POST'])
@requer_permissao('visitas', 'excluir')
@dono_da_obra
def delete_visita(obra_id, visita_id):
    """
    Deleta a visita (obra_visitas) e suas fotos (visita_fotos),
    removendo também os arquivos do disco.
    Retorna JSON.
    """
    try:
        # 1) Buscar paths das fotos antes de apagar (pra deletar do disco)
        with engine.begin() as conn:
            fotos = conn.execute(sa_text("""
                SELECT id, file_path
                FROM visit_photos
                WHERE visita_id = :vid
            """), {"vid": visita_id}).mappings().all()

        # 2) Apagar fotos (BD) e a visita (BD)
        with engine.begin() as conn:
            conn.execute(sa_text("""
                DELETE FROM visit_photos
                WHERE visita_id = :vid
            """), {"vid": visita_id})

            result = conn.execute(sa_text("""
                DELETE FROM project_visits
                WHERE id = :vid AND obra_id = :oid
            """), {"vid": visita_id, "oid": obra_id})

            if result.rowcount == 0:
                return jsonify({"ok": False, "error": "Visita não encontrada para esta obra."}), 404

            # recalcula a próxima visita: última que restou (ou o início da obra) + 7 dias
            base = conn.execute(sa_text("""
                SELECT COALESCE(
                    (SELECT MAX(data_visita) FROM project_visits WHERE obra_id = :oid),
                    (SELECT COALESCE(data_inicio, DATE(created_at)) FROM projects WHERE id = :oid)
                )
            """), {"oid": obra_id}).scalar()
            if base:
                conn.execute(sa_text("UPDATE projects SET proxima_visita = :p WHERE id = :oid"),
                            {"p": base + timedelta(days=DIAS_ENTRE_VISITAS), "oid": obra_id})

        # 3) Remover arquivos do disco (se existirem)
        if fotos:
            base_static = Path(app.static_folder)
            for f in fotos:
                rel = f.get("file_path") or ""
                if not rel:
                    continue
                path = (base_static / rel).resolve()
                # segurança: garantir que está dentro de /static
                try:
                    path.relative_to(base_static)
                except Exception:
                    continue
                if path.exists():
                    try:
                        path.unlink()
                    except Exception:
                        # não interromper por falha de IO
                        pass

        return jsonify({"ok": True}), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e), "type": e.__class__.__name__}), 500


@app.route("/obras/<int:obra_id>/visitas", methods=["GET", "POST"])
@requer_permissao('visitas', {'GET': 'ver', 'POST': 'inserir'})
@dono_da_obra
def visitas_obra(obra_id):
    if request.method == "POST":
        data_visita_dt = _to_date_safe(request.form.get("data_visita")) or date.today()
        responsavel    = (request.form.get("responsavel") or "").strip() or (current_user.name or current_user.username)
        estagio_obra   = request.form.get("estagio_obra") or ""
        contato_nome   = (request.form.get("contato_nome") or "").strip() or None
        concorrente    = (request.form.get("concorrente") or "").strip() or None
        observacoes    = (request.form.get("observacoes") or "").strip() or None
        proxima_dt     = _to_date_safe(request.form.get("proxima_visita")) or (data_visita_dt + timedelta(days=DIAS_ENTRE_VISITAS))

        if estagio_obra not in ESTAGIOS_NOMES:
            flash("Selecione o estágio da obra.", "error")
            return redirect(url_for("visitas_obra", obra_id=obra_id))

        # palavra-chave = o estágio, para manter buscável o que já existia
        palavras_chave = ESTAGIOS_NOMES[estagio_obra]

        # 1) cria a visita e captura o ID
        with engine.begin() as conn:
            visita_id = conn.execute(sa_text("""
                INSERT INTO project_visits
                (obra_id, data_visita, responsavel, estagio_obra, contato_nome, concorrente, palavras_chave, observacoes)
                VALUES (:obra_id, :data_visita, :responsavel, :estagio_obra, :contato_nome, :concorrente, :palavras_chave, :observacoes)
            """), {
                "obra_id": obra_id,
                "data_visita": data_visita_dt,
                "responsavel": responsavel,
                "estagio_obra": estagio_obra,
                "contato_nome": contato_nome,
                "concorrente": concorrente,
                "palavras_chave": palavras_chave,
                "observacoes": observacoes
            }).lastrowid
            # agenda a próxima visita (padrão: 7 dias depois desta)
            conn.execute(sa_text("UPDATE projects SET proxima_visita = :p WHERE id = :oid"),
                        {"p": proxima_dt, "oid": obra_id})

        # 2) processa fotos (input name="fotos[]" multiple)
        files = request.files.getlist("fotos[]")
        if files:
            base = _ensure_base_visitas_dir()
            visita_dir = base / str(visita_id)
            visita_dir.mkdir(parents=True, exist_ok=True)

            with engine.begin() as conn:
                for f in files:
                    if not f or not f.filename:
                        continue
                    token = secrets.token_hex(6)
                    ext = os.path.splitext(f.filename)[1].lower() or ".jpg"
                    raw_name = f"{_dt.utcnow().strftime('%Y%m%d_%H%M%S')}_{token}{ext}"
                    dest = visita_dir / raw_name

                    out_path = _save_and_compress_image(f, dest)
                    rel_path = out_path.relative_to(Path(app.static_folder)).as_posix()  # uploads/visitas/<id>/arquivo.jpg

                    conn.execute(sa_text("""
                        INSERT INTO visit_photos (visita_id, file_path, mime_type)
                        VALUES (:visita_id, :file_path, :mime)
                    """), {
                        "visita_id": visita_id,
                        "file_path": rel_path,
                        "mime": f.mimetype
                    })

        flash(f"Visita registrada. Próxima visita prevista para {proxima_dt.strftime('%d/%m/%Y')}.", "success")
        return redirect(url_for("visitas_obra", obra_id=obra_id))

    # -------------------------- GET --------------------------
    with engine.begin() as conn:
        obra = conn.execute(sa_text("""
            SELECT id,
                   numero_obra,
                   nome,
                   data_inicio,
                   data_termino_prevista,
                   proxima_visita
            FROM projects
            WHERE id = :obra_id
        """), {"obra_id": obra_id}).mappings().first()
        if not obra:
            flash("Obra não encontrada.", "error")
            return redirect(url_for("lista_obras"))

        visitas = conn.execute(sa_text("""
            SELECT id, data_visita, responsavel, estagio_obra, contato_nome, concorrente, palavras_chave, observacoes
            FROM project_visits
            WHERE obra_id = :obra_id
            ORDER BY (data_visita IS NULL), data_visita DESC, id DESC
        """), {"obra_id": obra_id}).mappings().all()

    # Busca fotos das visitas desta obra e mapeia por visita_id
    with engine.begin() as conn:
        fotos = conn.execute(sa_text("""
            SELECT id, visita_id, file_path, mime_type
            FROM visit_photos
            WHERE visita_id IN (
                SELECT id FROM project_visits WHERE obra_id = :obra_id
            )
            ORDER BY id ASC
        """), {"obra_id": obra_id}).mappings().all()

    fotos_por_visita = {}
    for f in fotos:
        fotos_por_visita.setdefault(f["visita_id"], []).append(f)

    return render_template(
        "visitas_obra.html",
        obra=obra,
        visitas=visitas,
        fotos_por_visita=fotos_por_visita,
        estagios=ESTAGIOS_VISITA,
        estagios_nomes=ESTAGIOS_NOMES,
        estagio_cores=ESTAGIO_CORES,
        dias_entre_visitas=DIAS_ENTRE_VISITAS,
        now_date=date.today(),
    )
#================================================================
# ===================== CADASTRO DE OBRAS =====================
# =============================================================
#================================================================
# ===================== CADASTRO DE OBRAS =====================
# imports esperados:
# from flask import request, render_template, redirect, url_for, flash
# from flask_login import login_required
# from sqlalchemy import text as sa_text
# from datetime import date, datetime, timedelta

VALID_STATUSES = {"INICIANDO","ANDAMENTO","CONCLUIDA","PARADA","CANCELADA"}

def _str_or_none(v):
    v = (v or "").strip()
    return v if v else None

def _date_or_none(v):
    v = (v or "").strip()
    if not v: return None
    # aceita yyyy-mm-dd ou dd/mm/yyyy -> retorna yyyy-mm-dd
    try:
        if len(v) == 10 and v[4] == "-" and v[7] == "-":
            return v
        d, m, y = v.split("/")
        return f"{y}-{int(m):02d}-{int(d):02d}"
    except Exception:
        return None

def _float_or_none(v):
    try:
        return float(str(v).replace(",", ".").strip())
    except Exception:
        return None

@app.route('/editar_cadastro', methods=['GET', 'POST'])
@requer_permissao('obras', 'alterar')
@dono_da_obra
def editar_cadastro():
    """
    GET  /editar_cadastro?obra_id=<id>  -> carrega dados e renderiza o form preenchido
    POST /editar_cadastro               -> UPDATE (não duplica)
    """
    obra_id = (request.args.get('obra_id') or request.form.get('obra_id') or "").strip()
    if not obra_id:
        flash("ID da obra não informado.", "error")
        return redirect(url_for('lista_obras'))

    # -------- GET: abrir formulário preenchido --------
    if request.method == 'GET':
        with engine.begin() as conn:
            row = conn.execute(sa_text("""
                SELECT
                    o.id, o.numero_obra, o.nome_obra,
                    o.responsavel_cadastro,
                    o.nome, o.sobrenome,
                    o.logradouro, o.numero, o.bairro, o.cidade, o.estado, o.cep, o.regiao,
                    o.telefone, o.email, o.cpf,
                    o.latitude, o.longitude,
                    o.observacoes,
                    o.tipo_obra, o.padrao_obra, o.tipo_cliente, o.potencial_obra,
                    o.metragem_m2,
                    o.data_inicio, o.data_termino_prevista,
                    o.favorito,
                    o.status
                FROM projects o
                WHERE o.id = :id
            """), {"id": obra_id}).mappings().first()

        if not row:
            flash("Obra não encontrada.", "error")
            return redirect(url_for('lista_obras'))

        # Dica: no template, inclua <input type="hidden" name="obra_id" value="{{ obra.id }}">
        return render_template('cadastro_obras.html', obra=row)

    # -------- POST: atualizar (sem duplicar) --------
    f = request.form

    numero_obra          = _str_or_none(f.get('numero_obra'))
    nome_obra            = _str_or_none(f.get('nome_obra'))
    responsavel_cadastro = _str_or_none(f.get('responsavel_cadastro'))
    nome                 = _str_or_none(f.get('nome'))
    sobrenome            = _str_or_none(f.get('sobrenome'))
    logradouro           = _str_or_none(f.get('logradouro'))
    numero               = _str_or_none(f.get('numero'))
    bairro               = _str_or_none(f.get('bairro'))
    cidade               = _str_or_none(f.get('cidade'))
    estado               = _str_or_none(f.get('estado'))
    cep                  = _str_or_none(f.get('cep'))
    regiao               = _str_or_none(f.get('regiao'))
    telefone             = _str_or_none(f.get('telefone'))
    email                = _str_or_none(f.get('email'))
    cpf                  = _str_or_none(f.get('cpf'))
    latitude             = _float_or_none(f.get('latitude'))
    longitude            = _float_or_none(f.get('longitude'))
    observacoes          = _str_or_none(f.get('observacoes'))
    tipo_obra            = _str_or_none(f.get('tipo_obra'))
    padrao_obra          = _str_or_none(f.get('padrao_obra'))
    tipo_cliente         = _str_or_none(f.get('tipo_cliente'))
    potencial_obra       = _str_or_none(f.get('potencial_obra'))
    metragem_m2          = _float_or_none(f.get('metragem_m2'))
    data_inicio          = _date_or_none(f.get('data_inicio'))
    data_termino_prevista= _date_or_none(f.get('data_termino_prevista'))
    favorito             = 1 if (f.get('favorito') or '').lower() in ('on','true','1','yes','y','sim') else 0
    status               = (f.get('status') or 'INICIANDO').strip().upper()
    if status not in VALID_STATUSES:
        status = 'INICIANDO'

    if not numero_obra:
        flash("Informe o número da obra.", "error")
        return redirect(request.referrer or url_for('lista_obras'))

    with engine.begin() as conn:
        # Checa duplicidade de numero_obra (excluindo o próprio registro)
        dup = conn.execute(sa_text("""
            SELECT COUNT(*) AS qtd
            FROM projects
            WHERE numero_obra = :numero_obra
              AND id <> :id
        """), {"numero_obra": numero_obra, "id": obra_id}).scalar_one()

        if dup and int(dup) > 0:
            flash("Já existe outra obra com este número.", "error")
            return redirect(request.referrer or url_for('lista_obras'))

        # UPDATE
        upd_sql = sa_text("""
            UPDATE projects
            SET
                numero_obra = :numero_obra,
                nome_obra   = :nome_obra,
                responsavel_cadastro = :responsavel_cadastro,
                nome = :nome,
                sobrenome = :sobrenome,
                logradouro = :logradouro,
                numero = :numero,
                bairro = :bairro,
                cidade = :cidade,
                estado = :estado,
                cep = :cep,
                regiao = :regiao,
                telefone = :telefone,
                email = :email,
                cpf = :cpf,
                latitude = :latitude,
                longitude = :longitude,
                observacoes = :observacoes,
                tipo_obra = :tipo_obra,
                padrao_obra = :padrao_obra,
                tipo_cliente = :tipo_cliente,
                potencial_obra = :potencial_obra,
                metragem_m2 = :metragem_m2,
                data_inicio = :data_inicio,
                data_termino_prevista = :data_termino_prevista,
                favorito = :favorito,
                status = :status
            WHERE id = :id
        """)

        conn.execute(upd_sql, {
            "id": obra_id,
            "numero_obra": numero_obra,
            "nome_obra": nome_obra,
            "responsavel_cadastro": responsavel_cadastro,
            "nome": nome,
            "sobrenome": sobrenome,
            "logradouro": logradouro,
            "numero": numero,
            "bairro": bairro,
            "cidade": cidade,
            "estado": estado,
            "cep": cep,
            "regiao": regiao,
            "telefone": telefone,
            "email": email,
            "cpf": cpf,
            "latitude": latitude,
            "longitude": longitude,
            "observacoes": observacoes,
            "tipo_obra": tipo_obra,
            "padrao_obra": padrao_obra,
            "tipo_cliente": tipo_cliente,
            "potencial_obra": potencial_obra,
            "metragem_m2": metragem_m2,
            "data_inicio": data_inicio,
            "data_termino_prevista": data_termino_prevista,
            "favorito": favorito,
            "status": status,
        })

    flash("Obra atualizada com sucesso!", "success")
    return redirect(url_for('lista_obras'))


from flask import (
    render_template, request, redirect, url_for, flash, jsonify
)
from sqlalchemy import text as sa_text
from sqlalchemy.exc import IntegrityError
from datetime import datetime
import json

@app.route('/editar_obra', methods=['GET'])
@requer_permissao('obras', 'alterar')
@dono_da_obra
def editar_obra():
    obra_id = (request.args.get('obra_id') or '').strip()
    if not obra_id:
        flash('ID da obra não informado.', 'error')
        return redirect(url_for('lista_obras'))

    with engine.begin() as conn:
        row = conn.execute(sa_text("""
            SELECT *
            FROM projects
            WHERE id = :id
        """), {"id": obra_id}).mappings().first()

    if not row:
        flash('Obra não encontrada.', 'error')
        return redirect(url_for('lista_obras'))

    # Se quiser pré-preencher os JSONs no hidden:
    profissionais_json = row.get('profissionais_json') or '[]'
    vendedores_json    = row.get('vendedores_json') or '[]'
    etapas_json        = row.get('etapas_json') or '[]'
    visitas_json       = row.get('visitas_json') or '[]'

    return render_template(
        'editar_obra.html',
        obra=row,
        profissionais_json=profissionais_json,
        vendedores_json=vendedores_json,
        etapas_json=etapas_json,
        visitas_json=visitas_json
    )

from sqlalchemy import text as sa_text
from datetime import date

def _cols_obras(conn):
    rows = conn.execute(sa_text("""
        SELECT COLUMN_NAME
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'projects'
    """)).fetchall()
    return {r[0] for r in rows}

def _to_date_safe(val):
    """
    Aceita 'YYYY-MM-DD' (string) ou date, retorna date ou None.
    Também evita datas com ano < 1000 (MySQL costuma dar problema).
    """
    if not val:
        return None
    if isinstance(val, date):
        return val if val.year >= 1000 else None
    s = str(val).strip()
    if not s:
        return None
    try:
        y, m, d = [int(x) for x in s.split('-')]
        if y < 1000:
            return None
        return date(y, m, d)
    except Exception:
        return None

from datetime import date

def _to_date_safe(val):
    if not val:
        return None
    if isinstance(val, date):
        return val if val.year >= 1000 else None
    s = str(val).strip()
    try:
        y, m, d = [int(x) for x in s.split('-')]
        if y < 1000: return None
        return date(y, m, d)
    except Exception:
        return None

@app.route('/editar_obra', methods=['POST','PUT','PATCH'])
@requer_permissao('obras', 'alterar')
@dono_da_obra
def editar_obra_post():
    # aceita obra_id tanto no form quanto na query; prioriza obra_id
    obra_id = (request.form.get('obra_id') or request.form.get('id') or request.args.get('obra_id') or '').strip()

    app.logger.info("[EDITAR_OBRA] método: %s", request.method)
    app.logger.info("[EDITAR_OBRA] obra_id recebido: %r", obra_id)
    app.logger.info("[EDITAR_OBRA] keys form: %s", list(request.form.keys()))

    if not obra_id:
        flash('ID da obra não informado.', 'error')
        return redirect(url_for('lista_obras'))

    f = request.form

    desired = {
        'numero_obra': (f.get('numeroObra') or '').strip(),
        'endereco_obra': " ".join((f.get('endereco_obra') or '').split()),
        'nome'       : (f.get('nome') or '').strip(),
        'sobrenome'  : (f.get('sobrenome') or '').strip(),
        'logradouro' : (f.get('logradouro') or '').strip(),
        'numero'     : (f.get('numero') or '').strip(),
        'bairro'     : (f.get('bairro') or '').strip(),
        'cidade'     : (f.get('cidade') or '').strip(),
        'estado'     : (f.get('estado') or '').strip(),
        'cep'        : (f.get('cep') or '').strip(),
        'regiao'     : (f.get('regiao') or '').strip() if (f.get('regiao') or '').strip() in REGIOES else None,
        'telefone'   : (f.get('telefone') or '').strip(),
        'email'      : (f.get('email') or '').strip(),
        'cpf'        : (f.get('cpf') or '').strip(),
        'latitude'   : (lambda x: None if x in (None,'') else x)(f.get('latitude')),
        'longitude'  : (lambda x: None if x in (None,'') else x)(f.get('longitude')),
        'observacoes': (f.get('observacoes') or '').strip(),

        'tipo_obra'  : (f.get('tipoObra') or '').strip(),
        'padrao_obra': (f.get('padraoObra') or '').strip(),
        'tipo_cliente': (f.get('tipoCliente') or '').strip(),
        'potencial_obra': (f.get('potencialObra') or '').strip(),
        'metragem_m2': (lambda v: int(v) if v not in (None,'') and str(v).isdigit() else None)(f.get('metragem')),
        'data_inicio': _to_date_safe(f.get('dataInicio')),
        'data_termino_prevista': _to_date_safe(f.get('dataTermino')),

        'favorito': 1 if (f.get('favorito') or '0') in ('1','true','True','on') else 0,

        # opcionais em JSON; se sua tabela não tiver essas colunas, serão ignoradas (ver filtro abaixo)
        'profissionais_json': f.get('profissionais_json') or '[]',
        'vendedores_json'   : f.get('vendedores_json') or '[]',
        'etapas_json'       : f.get('etapas_json') or '[]',
        'visitas_json'      : f.get('visitas_json') or '[]',
    }

    with engine.begin() as conn:
        cols = {r[0] for r in conn.execute(sa_text("""
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'projects'
        """)).fetchall()}
        app.logger.info("[EDITAR_OBRA] colunas da tabela obras: %s", cols)

        filtered_items = [(k, v) for k, v in desired.items() if k in cols]
        if not filtered_items:
            flash('Nenhuma coluna válida para atualizar. Verifique o schema.', 'error')
            return redirect(url_for('editar_obra', obra_id=obra_id))

        set_frag = ", ".join([f"{k} = :{k}" for k, _ in filtered_items])
        params = {k: v for k, v in filtered_items}
        params['id'] = obra_id

        sql = sa_text(f"UPDATE projects SET {set_frag} WHERE id = :id")
        app.logger.info("[EDITAR_OBRA] SQL: %s", sql.text)
        app.logger.info("[EDITAR_OBRA] PARAMS: %s", params)

        res = conn.execute(sql, params)
        app.logger.info("[EDITAR_OBRA] rowcount: %s", res.rowcount)

        if res.rowcount == 0:
            exists = conn.execute(sa_text("SELECT 1 FROM projects WHERE id=:i"), {"i": obra_id}).fetchone()
            if not exists:
                flash('Obra não encontrada para atualização.', 'error')
                return redirect(url_for('lista_obras'))
            flash('Nenhuma alteração detectada (valores idênticos).', 'warning')
        else:
            flash('Obra atualizada com sucesso.', 'success')

    return redirect(url_for('editar_obra', obra_id=obra_id))

def _proximo_numero_obra():
    with engine.begin() as conn:
        return conn.execute(sa_text("SELECT COALESCE(MAX(numero_obra), 0) + 1 FROM projects")).scalar()

@app.route('/api/obras/cliente/telefone/<tel>', methods=['GET'])
@requer_permissao('obras', 'inserir')
def buscar_cliente_por_telefone(tel):
    """Dados do cliente da obra mais recente com este telefone (entre as obras que o usuário pode ver)."""
    digitos = re.sub(r"\D", "", tel or "")
    if len(digitos) not in (10, 11):
        return jsonify(encontrado=False)
    dono_sql, params = _filtro_dono("o")
    with engine.begin() as conn:
        c = conn.execute(sa_text(f"""
            SELECT o.numero_obra, o.cliente_pf_pj, o.nome, o.sobrenome, o.cpf, o.cnpj, o.email,
                   o.logradouro, o.numero, o.bairro, o.cidade, o.estado, o.cep, o.regiao,
                   (SELECT COUNT(*) FROM projects o2 WHERE REGEXP_REPLACE(COALESCE(o2.telefone, ''), '[^0-9]', '') = :t
                      AND {dono_sql.replace('o.', 'o2.')}) AS obras
            FROM projects o
            WHERE REGEXP_REPLACE(COALESCE(o.telefone, ''), '[^0-9]', '') = :t AND {dono_sql}
            ORDER BY o.id DESC LIMIT 1
        """), {"t": digitos, **params}).mappings().first()
    if not c:
        return jsonify(encontrado=False)
    return jsonify(encontrado=True, **{k: (v if v is not None else "") for k, v in dict(c).items()})

@app.route('/cadastro_obras', methods=['GET', 'POST'])
@app.route('/cadastro_obras/', methods=['GET', 'POST'])
@requer_permissao('obras', 'inserir')
def cadastro_obras():
    if request.method == 'GET':
        return render_template('cadastro_obras.html', proximo_numero=_proximo_numero_obra())

    form = request.form

    # Campos principais (o número da obra é gerado pelo sistema na hora de salvar)
    responsavel_cadastro = (form.get("responsavelCadastro") or "").strip()
    endereco_obra        = " ".join((form.get("endereco_obra") or "").split())
    if not endereco_obra:
        flash("Informe o endereço da obra.", "error")
        return redirect(url_for('cadastro_obras'))

    nome       = (form.get("nome") or "").strip()
    if not nome:
        flash("Informe o nome do cliente.", "error")
        return redirect(url_for('cadastro_obras'))
    sobrenome  = (form.get("sobrenome") or "").strip()
    logradouro = (form.get("logradouro") or "").strip()
    numero     = (form.get("numero") or "").strip()
    bairro     = (form.get("bairro") or "").strip()
    cidade     = (form.get("cidade") or "").strip()
    estado     = (form.get("estado") or "").strip()
    cep        = (form.get("cep") or "").strip()
    regiao     = (form.get("regiao") or "").strip()
    regiao     = regiao if regiao in REGIOES else None
    telefone   = (form.get("telefone") or "").strip()
    email      = (form.get("email") or "").strip() or None

    # PF / PJ — NOVO (usar a nova coluna cliente_pf_pj)
    cliente_pf_pj = (form.get("cliente_pf_pj") or "").strip()  # 'cliente_pf' | 'cliente_pj'
    if cliente_pf_pj not in ("cliente_pf", "cliente_pj"):
        flash("Selecione se o cliente é PF ou PJ.", "error")
        return redirect(url_for('cadastro_obras'))

    # CPF/CNPJ opcionais (apenas um conforme tipo)
    import re
    digits = lambda s: re.sub(r"\D+", "", s or "")
    cpf  = digits(form.get("cpf")) or None
    cnpj = digits(form.get("cnpj")) or None
    if cliente_pf_pj == "cliente_pf":
        cnpj = None
    else:
        cpf = None
        sobrenome = ""  # empresa não tem sobrenome

    # Coordenadas opcionais
    latitude   = form.get("latitude")
    longitude  = form.get("longitude")
    latitude   = float(latitude) if latitude not in (None, "",) else None
    longitude  = float(longitude) if longitude not in (None, "",) else None

    tipo_obra      = form.get("tipoObra")
    padrao_obra    = form.get("padraoObra")
    potencial_obra = form.get("potencialObra")
    metragem       = form.get("metragem")
    data_inicio    = form.get("dataInicio") or None
    data_termino   = form.get("dataTermino") or None  # opcional (pode vir vazio)

    observacoes    = (form.get("observacoes") or "").strip() or None

    favorito_str   = form.get("favorito")
    favorito       = 1 if (favorito_str in ("1", "true", "on")) else 0

    # Blocos dinâmicos
    profissionais_json = form.get("profissionais_json", "[]")
    vendedores_json    = form.get("vendedores_json", "[]")

    import json, traceback
    try:
        profissionais = json.loads(profissionais_json)
        vendedores    = json.loads(vendedores_json)
    except json.JSONDecodeError:
        flash("JSON inválido em profissionais/vendedores.", "error")
        return redirect(url_for('cadastro_obras'))

    # Conversões
    metragem = int(metragem) if (metragem and str(metragem).isdigit()) else 0

    # data de início vem do aparelho; se não vier (ou vier inválida), usa a data de hoje
    data_inicio_dt  = _to_date_safe(data_inicio) or date.today()
    data_termino_dt = _to_date_safe(data_termino)  # pode ser None

    # ---------------- TRANSAÇÃO ----------------
    with engine.begin() as conn:
        # número sequencial: trava a tabela de obras enquanto calcula o próximo
        numero_obra_int = conn.execute(sa_text(
            "SELECT COALESCE(MAX(numero_obra), 0) + 1 FROM projects FOR UPDATE"
        )).scalar()
        obra_id = conn.execute(sa_text("""
            INSERT INTO projects
            (numero_obra, nome_obra, endereco_obra, responsavel_cadastro, nome, sobrenome, logradouro, numero, bairro,
             cidade, estado, cep, regiao, telefone, email, cpf, cnpj, latitude, longitude, observacoes,
             tipo_obra, padrao_obra, cliente_pf_pj, potencial_obra, metragem_m2, data_inicio, data_termino_prevista,
             favorito, status, created_by, proxima_visita)
            VALUES
            (:numero_obra, NULL, :endereco_obra, :responsavel_cadastro, :nome, :sobrenome, :logradouro, :numero, :bairro,
             :cidade, :estado, :cep, :regiao, :telefone, :email, :cpf, :cnpj, :latitude, :longitude, :observacoes,
             :tipo_obra, :padrao_obra, :cliente_pf_pj, :potencial_obra, :metragem, :data_inicio, :data_termino,
             :favorito, NULL, :created_by, :proxima_visita)
        """), {
            "created_by": int(current_user.id),
            "numero_obra": numero_obra_int,
            "endereco_obra": endereco_obra,
            "responsavel_cadastro": responsavel_cadastro,
            "nome": nome, "sobrenome": sobrenome,
            "logradouro": logradouro, "numero": numero, "bairro": bairro,
            "cidade": cidade, "estado": estado, "cep": cep, "regiao": regiao,
            "telefone": telefone, "email": email,
            "cpf": cpf, "cnpj": cnpj,
            "latitude": latitude, "longitude": longitude,
            "observacoes": observacoes,
            "tipo_obra": tipo_obra, "padrao_obra": padrao_obra,
            "cliente_pf_pj": cliente_pf_pj,  # <<< nova coluna
            "potencial_obra": potencial_obra,
            "metragem": metragem, "data_inicio": data_inicio_dt, "data_termino": data_termino_dt,
            "favorito": favorito,
            "proxima_visita": data_inicio_dt + timedelta(days=DIAS_ENTRE_VISITAS),
        }).lastrowid

        # Profissionais
        for p in (profissionais or []):
            conn.execute(sa_text("""
                INSERT INTO project_professionals
                (obra_id, nome, cargo, telefone, email, observacoes, vinculo, parceiro)
                VALUES (:obra_id, :nome, :cargo, :telefone, :email, :obs, :vinculo, :parceiro)
            """), {
                "obra_id": obra_id,
                "nome": (p.get("nome") or "").strip(),
                "cargo": p.get("cargo"),
                "telefone": p.get("telefone"),
                "email": p.get("email"),
                "obs": p.get("observacoes"),
                "vinculo": p.get("vinculo"),
                "parceiro": 1 if (p.get("parceiro") in (1, "1", True, "true", "on")) else 0
            })

        # Vendedores (entrada livre)
        try:
            from slugify import slugify as _slugify
        except Exception:
            def _slugify(txt):
                return (txt or "").strip().lower().replace(" ", "_")

        for v in (vendedores or []):
            empresa_slug  = (v.get("empresa_slug")  or "").strip()
            empresa_nome  = (v.get("empresa_nome")  or "").strip()
            vendedor_id   = v.get("vendedor_id")
            vendedor_nome = (v.get("vendedor_nome") or None)

            if not empresa_slug and empresa_nome:
                empresa_slug = _slugify(empresa_nome)
            if not (empresa_slug or empresa_nome):
                continue

            emp = conn.execute(sa_text("SELECT id FROM companies WHERE slug=:s"), {"s": empresa_slug}).fetchone()
            if not emp:
                emp_id = conn.execute(sa_text(
                    "INSERT INTO companies (slug, nome) VALUES (:s, :n)"
                ), {"s": empresa_slug, "n": empresa_nome or empresa_slug.replace("_", " ").title()}
                ).lastrowid
            else:
                emp_id = emp[0]

            vend_id = None
            if vendedor_id:
                chk = conn.execute(sa_text(
                    "SELECT id FROM sales_reps WHERE id=:vid AND empresa_id=:eid"
                ), {"vid": vendedor_id, "eid": emp_id}).fetchone()
                vend_id = chk[0] if chk else None

            conn.execute(sa_text("""
                INSERT INTO project_sales_reps (obra_id, empresa_id, vendedor_id, vendedor_nome)
                VALUES (:obra_id, :empresa_id, :vendedor_id, :vendedor_nome)
                ON DUPLICATE KEY UPDATE vendedor_nome=VALUES(vendedor_nome)
            """), {
                "obra_id": obra_id,
                "empresa_id": emp_id,
                "vendedor_id": vend_id,
                "vendedor_nome": vendedor_nome
            })

    flash("Obra cadastrada com sucesso!", "success")
    return redirect(url_for('lista_obras'))


# =============================================================

# =============================================================
# =============================================================
# ===================== RELATÓRIO DE OBRAS =====================

from sqlalchemy import text as sa_text
from datetime import date, timedelta

#=========================================================================================#
# PAINEL DE INDICADORES (BI) — tudo respeita o dono dos dados e os filtros da tela
#=========================================================================================#
ETAPAS_NOMES = {
    "projeto": "Elaboração de Projeto", "preliminares": "Serviços Preliminares", "fundacao": "Fundação",
    "estrutura": "Estrutura", "alvenaria": "Alvenaria", "vedacoes": "Vedações", "cobertura": "Cobertura",
    "impermeabilizacao": "Impermeabilização", "instalacoes_hidraulicas": "Instalações Hidráulicas",
    "instalacoes_eletricas": "Instalações Elétricas", "instalacoes_gas": "Instalações de Gás",
    "revestimentos_internos": "Revestimentos Internos", "revestimentos_externos": "Revestimentos Externos",
    "forros": "Forros", "esquadrias": "Esquadrias", "vidros": "Vidros", "pintura": "Pintura", "pisos": "Pisos",
    "bancadas": "Bancadas", "loucas": "Louças e Metais", "climatizacao": "Climatização",
    "paisagismo": "Paisagismo", "limpeza": "Limpeza Final",
}
POTENCIAIS = ["Alto Potencial", "Médio Potencial", "Baixo Potencial", "Perdido"]
PADROES = {"muito_alto": "Muito alto", "alto": "Alto", "medio": "Médio", "baixo": "Baixo"}
REGIOES = {"norte": "Norte", "sul": "Sul", "leste": "Leste", "oeste": "Oeste", "centro": "Centro"}
TIPOS_OBRA = ["Residencial", "Comercial", "Industrial", "Reforma", "Ampliação", "Outro"]
STATUS_NOMES = {"INICIANDO": "Iniciando", "ANDAMENTO": "Em andamento", "CONCLUIDA": "Concluída",
                "PARADA": "Parada", "CANCELADA": "Cancelada"}
DIAS_SEM_VISITA = 30      # obra ativa sem visita há mais que isso pede atenção
DIAS_OPORTUNIDADE = 60    # janela de etapas previstas

def _bi_filtros():
    """WHERE comum a todo o painel (dono + filtros da tela) sobre a tabela obras `o`."""
    dono_sql, params = _filtro_dono("o")
    where = [dono_sql]
    regiao = (request.args.get("regiao") or "").strip()
    padrao = (request.args.get("padrao") or "").strip()
    tipo = (request.args.get("tipo") or "").strip()
    usuario = request.args.get("usuario", type=int)
    if regiao in REGIOES:
        where.append("o.regiao = :regiao"); params["regiao"] = regiao
    if padrao in PADROES:
        where.append("o.padrao_obra = :padrao"); params["padrao"] = padrao
    if tipo in TIPOS_OBRA:
        where.append("o.tipo_obra = :tipo"); params["tipo"] = tipo
    if usuario and _ve_tudo():
        where.append("o.created_by = :usuario"); params["usuario"] = usuario
    return " AND ".join(where), params

def _primeiro_dia_meses_atras(d, n):
    m = d.month - n
    y = d.year
    while m <= 0:
        m += 12; y -= 1
    return date(y, m, 1)

@app.route('/api/relatorios/painel', methods=['GET'])
@requer_permissao('relatorios', 'ver')
def relatorio_painel_api():
    where, params = _bi_filtros()
    hoje = date.today()
    ativa = "UPPER(COALESCE(o.status, 'INICIANDO')) IN ('INICIANDO', 'ANDAMENTO')"

    with engine.begin() as conn:
        q = lambda sql, extra=None: conn.execute(sa_text(sql), {**params, **(extra or {})}).mappings().all()

        # uma linha por obra, já com a última visita e a próxima etapa
        obras = q(f"""
            SELECT o.id, o.numero_obra, o.nome_obra, o.endereco_obra,
                   TRIM(CONCAT(COALESCE(o.nome, ''), ' ', COALESCE(o.sobrenome, ''))) AS cliente,
                   o.telefone, o.cidade, o.regiao, o.tipo_obra, o.padrao_obra, o.potencial_obra,
                   COALESCE(o.metragem_m2, 0) AS m2, UPPER(COALESCE(o.status, 'INICIANDO')) AS status,
                   o.data_inicio, o.data_termino_prevista, o.created_at, o.created_by,
                   u.name AS cadastrado_por,
                   ({ativa}) AS ativa,
                   (SELECT MAX(v.data_visita) FROM project_visits v WHERE v.obra_id = o.id) AS ultima_visita,
                   (SELECT COUNT(*) FROM project_visits v WHERE v.obra_id = o.id) AS visitas,
                   (SELECT MIN(e.data_prevista) FROM project_stages e
                     WHERE e.obra_id = o.id AND e.data_prevista >= CURDATE()) AS proxima_etapa
            FROM projects o
            LEFT JOIN users u ON u.id = o.created_by
            WHERE {where}
            ORDER BY o.id DESC
        """)

        visitas_mes = q(f"""
            SELECT DATE_FORMAT(v.data_visita, '%Y-%m') AS mes, COUNT(*) AS qtd
            FROM project_visits v JOIN projects o ON o.id = v.obra_id
            WHERE {where} AND v.data_visita >= :ini AND v.data_visita <= CURDATE()
            GROUP BY mes
        """, {"ini": _primeiro_dia_meses_atras(hoje, 11)})

        visitas_janela = q(f"""
            SELECT
              SUM(v.data_visita > CURDATE() - INTERVAL 30 DAY AND v.data_visita <= CURDATE()) AS atual,
              SUM(v.data_visita > CURDATE() - INTERVAL 60 DAY AND v.data_visita <= CURDATE() - INTERVAL 30 DAY) AS anterior
            FROM project_visits v JOIN projects o ON o.id = v.obra_id
            WHERE {where}
        """)[0]

        oportunidades = q(f"""
            SELECT e.data_prevista, e.tipo_etapa, o.id AS obra_id, o.numero_obra,
                   TRIM(CONCAT(COALESCE(o.nome, ''), ' ', COALESCE(o.sobrenome, ''))) AS cliente,
                   o.telefone, o.cidade, o.potencial_obra, COALESCE(o.metragem_m2, 0) AS m2
            FROM project_stages e JOIN projects o ON o.id = e.obra_id
            WHERE {where} AND {ativa}
              AND e.data_prevista BETWEEN CURDATE() AND CURDATE() + INTERVAL {DIAS_OPORTUNIDADE} DAY
            ORDER BY e.data_prevista, o.numero_obra
        """)

        por_usuario = []
        if _ve_tudo():
            por_usuario = q(f"""
                SELECT u.id, COALESCE(u.name, u.username) AS nome,
                       COUNT(o.id) AS obras,
                       SUM({ativa}) AS ativas,
                       SUM(CASE WHEN {ativa} THEN COALESCE(o.metragem_m2, 0) ELSE 0 END) AS m2_ativo,
                       SUM(o.potencial_obra = 'Perdido') AS perdidas,
                       (SELECT COUNT(*) FROM project_visits v JOIN projects o2 ON o2.id = v.obra_id
                         WHERE o2.created_by = u.id AND v.data_visita > CURDATE() - INTERVAL 90 DAY) AS visitas_90d
                FROM projects o JOIN users u ON u.id = o.created_by
                WHERE {where}
                GROUP BY u.id, u.name, u.username
                ORDER BY m2_ativo DESC, obras DESC
            """)

    # ---------- indicadores ----------
    def dias_desde(d):
        return (hoje - d).days if d else None

    ativas = [o for o in obras if o["ativa"]]
    area_ativa = sum(int(o["m2"] or 0) for o in ativas)
    alto_ativas = [o for o in ativas if o["potencial_obra"] == "Alto Potencial"]
    sem_visita = [o for o in ativas
                  if o["ultima_visita"] is None or dias_desde(o["ultima_visita"]) > DIAS_SEM_VISITA]
    perdidas = [o for o in obras if o["potencial_obra"] == "Perdido"]
    novas_30 = sum(1 for o in obras if o["created_at"] and (hoje - o["created_at"].date()).days < 30)
    novas_prev = sum(1 for o in obras if o["created_at"] and 30 <= (hoje - o["created_at"].date()).days < 60)

    kpis = {
        "area_ativa": area_ativa,
        "obras_ativas": len(ativas),
        "obras_total": len(obras),
        "alto_ativas": len(alto_ativas),
        "area_alto": sum(int(o["m2"] or 0) for o in alto_ativas),
        "sem_visita": len(sem_visita),
        "area_sem_visita": sum(int(o["m2"] or 0) for o in sem_visita),
        "visitas_30": int(visitas_janela["atual"] or 0),
        "visitas_30_ant": int(visitas_janela["anterior"] or 0),
        "novas_30": novas_30, "novas_30_ant": novas_prev,
        "perdidas": len(perdidas),
        "pct_perdidas": round(100 * len(perdidas) / len(obras)) if obras else 0,
        "oportunidades": len(oportunidades),
    }

    # ---------- distribuições ----------
    def agrupa(chave, ordem, nomes=None, so_ativas=False):
        base = ativas if so_ativas else obras
        out = []
        for k in ordem:
            grupo = [o for o in base if (o[chave] or "") == k]
            out.append({"chave": k, "nome": (nomes or {}).get(k, k), "obras": len(grupo),
                        "m2": sum(int(o["m2"] or 0) for o in grupo)})
        return out

    potencial = agrupa("potencial_obra", POTENCIAIS)
    status = agrupa("status", list(STATUS_NOMES), STATUS_NOMES)
    regiao = agrupa("regiao", list(REGIOES), REGIOES, so_ativas=True)

    cidades = {}
    for o in ativas:
        c = (o["cidade"] or "Sem cidade").strip().title()
        g = cidades.setdefault(c, {"nome": c, "obras": 0, "m2": 0})
        g["obras"] += 1; g["m2"] += int(o["m2"] or 0)
    cidades = sorted(cidades.values(), key=lambda g: (-g["m2"], -g["obras"], g["nome"]))[:8]

    matriz = [{"padrao": PADROES[p], "valores": [
                  sum(1 for o in ativas if o["padrao_obra"] == p and o["potencial_obra"] == pot)
                  for pot in POTENCIAIS[:3]]}
              for p in PADROES]

    vm = {r["mes"]: int(r["qtd"]) for r in visitas_mes}
    meses = [_primeiro_dia_meses_atras(hoje, n).strftime("%Y-%m") for n in range(11, -1, -1)]
    visitas_serie = [{"mes": m, "qtd": vm.get(m, 0)} for m in meses]

    etapas_prox = {}
    for e in oportunidades:
        n = ETAPAS_NOMES.get(e["tipo_etapa"], e["tipo_etapa"])
        etapas_prox[n] = etapas_prox.get(n, 0) + 1
    etapas_prox = [{"nome": k, "obras": v} for k, v in sorted(etapas_prox.items(), key=lambda kv: (-kv[1], kv[0]))]

    # obras que pedem atenção: ativas sem visita recente, maior potencial e maior área primeiro
    peso = {"Alto Potencial": 0, "Médio Potencial": 1, "Baixo Potencial": 2}
    atencao = sorted(sem_visita, key=lambda o: (peso.get(o["potencial_obra"], 3), -(o["m2"] or 0)))[:15]

    def ds(v):
        return v.strftime("%Y-%m-%d") if v else None

    def obra_json(o):
        return {
            "id": o["id"], "numero": o["numero_obra"], "endereco_obra": o["endereco_obra"] or o["nome_obra"] or "",
            "cliente": o["cliente"] or "", "telefone": o["telefone"] or "", "cidade": (o["cidade"] or "").title(),
            "regiao": REGIOES.get(o["regiao"], ""), "tipo": o["tipo_obra"] or "",
            "padrao": PADROES.get(o["padrao_obra"], ""), "potencial": o["potencial_obra"] or "",
            "m2": int(o["m2"] or 0), "status": STATUS_NOMES.get(o["status"], o["status"]),
            "inicio": ds(o["data_inicio"]), "termino": ds(o["data_termino_prevista"]),
            "ultima_visita": ds(o["ultima_visita"]), "dias_sem_visita": dias_desde(o["ultima_visita"]),
            "visitas": int(o["visitas"] or 0), "proxima_etapa": ds(o["proxima_etapa"]),
            "cadastrado_por": o["cadastrado_por"] or "",
        }

    return jsonify({
        "hoje": ds(hoje), "dias_sem_visita": DIAS_SEM_VISITA, "dias_oportunidade": DIAS_OPORTUNIDADE,
        "ve_tudo": _ve_tudo(),
        "kpis": kpis, "potencial": potencial, "status": status, "regiao": regiao, "cidades": cidades,
        "matriz": {"linhas": matriz, "colunas": POTENCIAIS[:3]},
        "visitas_mes": visitas_serie, "etapas_proximas": etapas_prox,
        "oportunidades": [{
            "data": ds(e["data_prevista"]), "etapa": ETAPAS_NOMES.get(e["tipo_etapa"], e["tipo_etapa"]),
            "obra_id": e["obra_id"], "numero": e["numero_obra"], "cliente": e["cliente"] or "",
            "telefone": e["telefone"] or "", "cidade": (e["cidade"] or "").title(),
            "potencial": e["potencial_obra"] or "", "m2": int(e["m2"] or 0),
        } for e in oportunidades],
        "atencao": [obra_json(o) for o in atencao],
        "por_usuario": [{"id": r["id"], "nome": r["nome"], "obras": int(r["obras"] or 0),
                         "ativas": int(r["ativas"] or 0), "m2_ativo": int(r["m2_ativo"] or 0),
                         "perdidas": int(r["perdidas"] or 0), "visitas_90d": int(r["visitas_90d"] or 0)}
                        for r in por_usuario],
        "obras": [obra_json(o) for o in obras],
    })

@app.route('/relatorios/obras', methods=['GET'])
@requer_permissao('relatorios', 'ver')
def relatorio_obras_page():
    usuarios = []
    if _ve_tudo():
        with engine.begin() as conn:
            usuarios = conn.execute(sa_text("""
                SELECT DISTINCT u.id, COALESCE(u.name, u.username) AS nome
                FROM users u JOIN projects o ON o.created_by = u.id ORDER BY nome
            """)).mappings().all()
    return render_template('relatorio_bi.html', regioes=REGIOES, padroes=PADROES, tipos=TIPOS_OBRA,
                           usuarios=usuarios)

STATUS_LIST = ["INICIANDO", "ANDAMENTO", "CONCLUIDA", "PARADA", "CANCELADA"]

def _norm_status_in(s: str) -> str:
    """Normaliza valor vindo do filtro para uma das 5 chaves (ou 'ALL')."""
    if not s: return "ALL"
    x = s.strip().upper()
    if x in STATUS_LIST or x == "ALL":
        return x
    # sinônimos
    if x in ("EM_ANDAMENTO", "ANDAMENTO"):
        return "ANDAMENTO"
    return x  # deixa passar (não filtra) se for algo inesperado

@app.route('/api/relatorios/obras', methods=['GET'])
@requer_permissao('relatorios', 'ver')
def relatorio_obras_api():
    period = (request.args.get('period') or '30').strip().lower()
    status_raw = (request.args.get('status') or 'ALL')
    status = _norm_status_in(status_raw)
    region_raw = (request.args.get('region') or 'all')
    region = region_raw.strip().upper()
    start_qs = (request.args.get('start') or '').strip()
    end_qs   = (request.args.get('end') or '').strip()

    where = []
    params = {}

    # período (baseado em data_inicio)
    if period == 'custom' and start_qs and end_qs:
        where.append("o.data_inicio BETWEEN :start AND :end")
        params['start'] = start_qs
        params['end']   = end_qs
    else:
        # calcula dt_start em Python para evitar parametrizar INTERVAL
        try:
            days = int(period)
        except Exception:
            days = 30
        dt_start = (date.today() - timedelta(days=days-1)).isoformat()
        where.append("o.data_inicio >= :start")
        params['start'] = dt_start

    # status (case-insensitive no banco)
    if status != "ALL" and status in STATUS_LIST:
        where.append("UPPER(COALESCE(o.status, '')) = :status")
        params['status'] = status

    # região (case-insensitive)
    if region != 'ALL':
        where.append("UPPER(COALESCE(o.regiao, '')) = :regiao")
        params['regiao'] = region

    dono_sql, dono_params = _filtro_dono("o")
    where.append(dono_sql)
    params.update(dono_params)

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    with engine.begin() as conn:
        # Linhas da tabela
        rows_sql = sa_text(f"""
            SELECT
              o.id,
              o.numero_obra,
              CONCAT(COALESCE(o.nome,''), ' ', COALESCE(o.sobrenome,'')) AS cliente,
              o.logradouro, o.numero, o.bairro, o.cidade, o.estado, o.cep,
              UPPER(COALESCE(o.regiao,'')) AS regiao,
              UPPER(COALESCE(o.status,'INICIANDO')) AS status,
              o.data_inicio,
              o.data_termino_prevista
            FROM projects o
            {where_sql}
            ORDER BY (o.data_inicio IS NULL), o.data_inicio DESC, o.id DESC
        """)
        rows = [dict(r) for r in conn.execute(rows_sql, params).mappings().all()]

    # Contagens por status e região
    status_counts = {s: 0 for s in STATUS_LIST}
    region_counts = {}

    for r in rows:
        st = (r.get("status") or "INICIANDO").upper()
        if st not in status_counts:
            st = "INICIANDO"
        status_counts[st] += 1

        reg = (r.get("regiao") or "").upper()
        region_counts[reg] = region_counts.get(reg, 0) + 1

    stats = {
        "total": len(rows),
        "iniciando": status_counts["INICIANDO"],
        "andamento": status_counts["ANDAMENTO"],
        "concluida": status_counts["CONCLUIDA"],
        "parada": status_counts["PARADA"],
        "cancelada": status_counts["CANCELADA"],
    }

    # Helpers de data para JSON
    def dstr(d):
        if d is None: return None
        try:
            return d.strftime('%Y-%m-%d')
        except Exception:
            return str(d)

    payload = {
        "stats": stats,
        "status_counts": status_counts,
        "status_breakdown": [{"status": k, "qtd": v} for k, v in status_counts.items()],
        "region_breakdown": [{"regiao": k, "qtd": v} for k, v in region_counts.items()],
        "rows": [
            {
                "numero_obra": r["numero_obra"],
                "cliente": (r.get("cliente") or "").strip(),
                "logradouro": r.get("logradouro") or "",
                "numero": r.get("numero") or "",
                "bairro": r.get("bairro") or "",
                "cidade": r.get("cidade") or "",
                "estado": r.get("estado") or "",
                "cep": r.get("cep") or "",
                "regiao": r.get("regiao") or "",
                "status": r.get("status") or "INICIANDO",
                "data_inicio": dstr(r.get("data_inicio")),
                "data_termino_prevista": dstr(r.get("data_termino_prevista")),
            }
            for r in rows
        ],
    }
    return jsonify(payload), 200
# =============================================================
# =============================================================
# =============================================================
# LISTAGEM — ARQUITETOS
@app.route('/usuarios/arquitetos', methods=['GET'])
@requer_permissao('usuarios', 'ver')
def lista_arquitetos():
    with engine.begin() as conn:
        rows = conn.execute(sa_text("""
            SELECT
              u.id,
              u.name AS nome,
              u.telefone,
              u.email,
              u.cidade,
              u.data_nascimento,
              TIMESTAMPDIFF(YEAR, u.data_nascimento, CURDATE()) AS idade,
              a.razao_social
            FROM users u
            LEFT JOIN architects a ON a.user_id = u.id
            WHERE u.tipo_usuario = 'arquiteto'
            ORDER BY u.name ASC, u.id DESC
        """)).mappings().all()
    return render_template('usuarios_arquitetos.html', usuarios=rows)

# LISTAGEM — FUNCIONÁRIOS
@app.route('/usuarios/funcionarios', methods=['GET'])
@requer_permissao('usuarios', 'ver')
def lista_funcionarios():
    with engine.begin() as conn:
        rows = conn.execute(sa_text("""
            SELECT
              u.id,
              u.name AS nome,
              u.telefone,
              u.email,
              u.cidade,
              u.data_nascimento,
              TIMESTAMPDIFF(YEAR, u.data_nascimento, CURDATE()) AS idade
            FROM users u
            WHERE u.tipo_usuario = 'funcionario'
            ORDER BY u.name ASC, u.id DESC
        """)).mappings().all()
    return render_template('usuarios_funcionarios.html', usuarios=rows)

import json

# A pesquisa de Arquitetura foi eliminada (o formulário mostrava as perguntas erradas,
# as de Profissional, e nunca salvou nada). O endereço antigo manda para a pesquisa que
# ficou, para quem tiver o link salvo não cair em página quebrada.
@app.route('/pesquisa/arquitetura', methods=['GET', 'POST'])
@requer_permissao('pesquisas', {'GET': 'ver', 'POST': 'inserir'})
def pesquisa_arquitetura():
    return redirect(url_for('pesquisa_funcionario'))


import json

@app.route('/pesquisa/profissional', methods=['GET','POST'])
@requer_permissao('pesquisas', {'GET': 'ver', 'POST': 'inserir'})
def pesquisa_funcionario():
    if request.method == 'GET':
        return render_template('pesquisa_funcionario.html')

    f = request.form

    def jlist(name):
        return json.dumps(request.form.getlist(name) or [], ensure_ascii=False)

    def n(v):
        v = (v or '').strip()
        return v if v else None

    # Identificação
    nome   = n(f.get('nome'))
    cargo  = n(f.get('cargo'))
    idade  = n(f.get('idade'))
    telefone = n(f.get('telefone'))

    # Endereço
    cep   = n(f.get('cep'))
    rua   = n(f.get('rua'))
    numero= n(f.get('numero'))
    bairro= n(f.get('bairro'))
    cidade= n(f.get('cidade'))
    estado= n(f.get('estado'))
    complemento = n(f.get('complemento'))

    # Específicos por cargo
    lojas_eletrica_json = jlist('lojas_eletrica')
    outras_lojas_eletrica = n(f.get('outras_lojas_eletrica'))

    # Lazer
    esportes_json = jlist('esportes')
    outros_esportes = n(f.get('outros_esportes'))

    internet_json = jlist('internet')
    outros_internet = n(f.get('outros_internet'))

    tem_instagram = n(f.get('tem_instagram'))
    instagram = n(f.get('instagram')) if tem_instagram == 'sim' else None

    # Perfil profissional
    experiencia = n(f.get('experiencia'))   # 1_3|3_5|5_8|8_mais
    obras_simultaneas = n(f.get('obras_simultaneas'))  # 1|2|3|4_mais
    tamanho_equipe = n(f.get('tamanho_equipe'))        # 1|2_4|5_10|10_mais

    # Dores / Tintas / Desejos / Processo / Lojas preferidas
    dores_json = jlist('dores')
    outras_dores = n(f.get('outras_dores'))

    tintas_json = jlist('tintas') if cargo == 'pintor' else json.dumps([], ensure_ascii=False)
    outras_tintas = n(f.get('outras_tintas')) if cargo == 'pintor' else None

    desejos_loja_json = jlist('desejos_loja')
    outros_desejos = n(f.get('outros_desejos'))

    processo_compra = n(f.get('processo_compra'))  # decide|influencia|decide_influencia|apenas_usa

    lojas_preferidas_json = jlist('lojas_preferidas')
    outras_lojas = n(f.get('outras_lojas'))

    # Futuro
    expectativas_loja_json = jlist('expectativas_loja')
    outras_expectativas = n(f.get('outras_expectativas'))
    expectativas = n(f.get('expectativas'))

    with engine.begin() as conn:
        conn.execute(sa_text("""
            INSERT INTO employee_survey_responses (
              user_id, nome, cargo, idade, telefone,
              cep, rua, numero, bairro, cidade, estado, complemento,
              lojas_eletrica, outras_lojas_eletrica,
              esportes, outros_esportes,
              internet, outros_internet,
              tem_instagram, instagram,
              experiencia, obras_simultaneas, tamanho_equipe,
              dores, outras_dores,
              tintas, outras_tintas,
              desejos_loja, outros_desejos,
              processo_compra,
              lojas_preferidas, outras_lojas,
              expectativas_loja, outras_expectativas,
              expectativas
            ) VALUES (
              :user_id, :nome, :cargo, :idade, :telefone,
              :cep, :rua, :numero, :bairro, :cidade, :estado, :complemento,
              :lojas_eletrica, :outras_lojas_eletrica,
              :esportes, :outros_esportes,
              :internet, :outros_internet,
              :tem_instagram, :instagram,
              :experiencia, :obras_simultaneas, :tamanho_equipe,
              :dores, :outras_dores,
              :tintas, :outras_tintas,
              :desejos_loja, :outros_desejos,
              :processo_compra,
              :lojas_preferidas, :outras_lojas,
              :expectativas_loja, :outras_expectativas,
              :expectativas
            )
        """), {
            "user_id": int(current_user.id),
            "nome": nome, "cargo": cargo, "idade": idade, "telefone": telefone,
            "cep": cep, "rua": rua, "numero": numero, "bairro": bairro, "cidade": cidade, "estado": estado, "complemento": complemento,
            "lojas_eletrica": lojas_eletrica_json, "outras_lojas_eletrica": outras_lojas_eletrica,
            "esportes": esportes_json, "outros_esportes": outros_esportes,
            "internet": internet_json, "outros_internet": outros_internet,
            "tem_instagram": tem_instagram, "instagram": instagram,
            "experiencia": experiencia, "obras_simultaneas": obras_simultaneas, "tamanho_equipe": tamanho_equipe,
            "dores": dores_json, "outras_dores": outras_dores,
            "tintas": tintas_json, "outras_tintas": outras_tintas,
            "desejos_loja": desejos_loja_json, "outros_desejos": outros_desejos,
            "processo_compra": processo_compra,
            "lojas_preferidas": lojas_preferidas_json, "outras_lojas": outras_lojas,
            "expectativas_loja": expectativas_loja_json, "outras_expectativas": outras_expectativas,
            "expectativas": expectativas
        })

    flash('Entrevista enviada com sucesso. Obrigado!', 'success')
    return redirect(url_for('pesquisa_funcionario'))


# --- em seu app Flask ---

from flask import jsonify, request
from flask_login import login_required

STATUSES = ['INICIANDO','ANDAMENTO','CONCLUIDA','PARADA','CANCELADA']

@app.route('/api/obras/<int:obra_id>/status/advance', methods=['POST'])
@requer_permissao('obras', 'alterar')
@dono_da_obra
def advance_status_obra(obra_id):
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            # pega status atual
            cur.execute("SELECT status FROM projects WHERE id=%s", (obra_id,))
            row = cur.fetchone()
            if not row:
                return jsonify(error="Obra não encontrada"), 404

            cur_status = (row.get('status') or 'INICIANDO').upper()
            if cur_status in STATUSES:
                nxt = STATUSES[(STATUSES.index(cur_status)+1) % len(STATUSES)]
            else:
                nxt = STATUSES[0]

            cur.execute(
                "UPDATE projects SET status=%s, updated_at=NOW() WHERE id=%s",
                (nxt, obra_id)
            )
            conn.commit()

        return jsonify(ok=True, status=nxt)
    except Exception as e:
        # log opcional
        import traceback; traceback.print_exc()
        try:
            conn.rollback()
        except:
            pass
        return jsonify(error="Falha ao atualizar status"), 500
    finally:
        try:
            conn.close()
        except:
            pass


@app.route('/api/obras/<int:obra_id>/status', methods=['POST'])
@requer_permissao('obras', 'alterar')
@dono_da_obra
def set_status_obra(obra_id):
    data = request.get_json(silent=True) or {}
    desired = (data.get('status') or '').upper().strip()
    if desired not in STATUSES:
        return jsonify(error="Status inválido"), 400

    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("UPDATE projects SET status=%s, updated_at=NOW() WHERE id=%s", (desired, obra_id))
            conn.commit()
        return jsonify(ok=True, status=desired)
    except Exception:
        import traceback; traceback.print_exc()
        try: conn.rollback()
        except: pass
        return jsonify(error="Falha ao atualizar status"), 500
    finally:
        try: conn.close()
        except: pass

def delete_obra(obra_id):
    with engine.begin() as conn:
        conn.execute(sa_text("DELETE FROM visit_photos WHERE visita_id IN (SELECT id FROM project_visits WHERE obra_id=:oid)"), {"oid": obra_id})
        conn.execute(sa_text("DELETE FROM project_visits WHERE obra_id=:oid"), {"oid": obra_id})
        conn.execute(sa_text("DELETE FROM project_stages WHERE obra_id=:oid"), {"oid": obra_id})
        try: conn.execute(sa_text("DELETE FROM project_professionals WHERE obra_id=:oid"), {"oid": obra_id})
        except: pass
        try: conn.execute(sa_text("DELETE FROM project_sales_reps WHERE obra_id=:oid"), {"oid": obra_id})
        except: pass
        conn.execute(sa_text("DELETE FROM projects WHERE id=:oid"), {"oid": obra_id})
    return {"ok": True}


@app.route('/api/obras/<int:obra_id>/delete', methods=['POST'])
@requer_permissao('obras', 'excluir')
@dono_da_obra
def api_delete_obra(obra_id):
    try:
        stats = delete_obra(obra_id)
        return jsonify(ok=True, stats=stats)
    except Exception as e:
        traceback.print_exc()
        return jsonify(ok=False, error=str(e)), 500



#=========================================================================================#
# PROFISSIONAIS — cadastro simples: nome, profissão e telefone
#=========================================================================================#
PROFISSOES = [
    "Armador", "Arquiteto", "Azulejista", "Carpinteiro", "Eletricista", "Encanador",
    "Engenheiro Civil", "Gesseiro", "Mestre de Obras", "Pedreiro", "Pintor", "Serralheiro",
]

def _garantir_tabela_profissionais():
    try:
        with engine.begin() as conn:
            conn.execute(sa_text("""
                CREATE TABLE IF NOT EXISTS professionals (
                  id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                  nome VARCHAR(150) NOT NULL,
                  profissao VARCHAR(60) NOT NULL,
                  telefone VARCHAR(11) NOT NULL,
                  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                  UNIQUE KEY uq_prof_telefone (telefone),
                  KEY idx_prof_profissao (profissao)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """))
            # versões antigas guardavam o telefone formatado e sem índice único
            tem_unico = conn.execute(sa_text("""
                SELECT COUNT(*) FROM information_schema.STATISTICS
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'professionals' AND INDEX_NAME = 'uq_prof_telefone'
            """)).scalar()
            if not tem_unico:
                conn.execute(sa_text("""
                    UPDATE professionals SET telefone = REGEXP_REPLACE(COALESCE(telefone, ''), '[^0-9]', '')
                """))
                conn.execute(sa_text("ALTER TABLE professionals MODIFY telefone VARCHAR(11) NOT NULL"))
                conn.execute(sa_text("ALTER TABLE professionals ADD UNIQUE KEY uq_prof_telefone (telefone)"))
                print("[profissionais] telefone virou identificador único")
    except Exception:
        traceback.print_exc()

def _so_digitos(tel):
    return re.sub(r"\D", "", tel or "")

@app.template_filter("fone")
def _formatar_fone(tel):
    d = _so_digitos(tel)
    if len(d) == 11:
        return f"({d[:2]}) {d[2:7]}-{d[7:]}"
    if len(d) == 10:
        return f"({d[:2]}) {d[2:6]}-{d[6:]}"
    return tel or ""

def _profissional_por_telefone(digitos, exceto_id=None):
    """Procura em TODOS os profissionais (o telefone é único no sistema inteiro)."""
    with engine.begin() as conn:
        return conn.execute(sa_text("""
            SELECT id, nome, profissao, telefone, created_by FROM professionals WHERE telefone = :t AND id <> :ex
        """), {"t": digitos, "ex": exceto_id or 0}).mappings().first()

def _profissional_do_usuario(prof_id):
    dono_sql, dono_params = _filtro_dono("p")
    with engine.begin() as conn:
        return conn.execute(sa_text(f"""
            SELECT p.id, p.nome, p.profissao, p.telefone FROM professionals p WHERE p.id = :id AND {dono_sql}
        """), {"id": prof_id, **dono_params}).mappings().first()

_garantir_tabela_profissionais()

def _garantir_coluna_dono():
    try:
        with engine.begin() as conn:
            admin_id = conn.execute(sa_text(
                "SELECT MIN(id) FROM users WHERE perfil = 'admin' AND status = 'aprovado'"
            )).scalar()
            for tabela in ("projects", "professionals"):
                existe = conn.execute(sa_text("""
                    SELECT COUNT(*) FROM information_schema.COLUMNS
                    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t AND COLUMN_NAME = 'created_by'
                """), {"t": tabela}).scalar()
                if existe:
                    continue
                conn.execute(sa_text(f"ALTER TABLE {tabela} ADD COLUMN created_by INT UNSIGNED NULL, ADD KEY idx_{tabela}_dono (created_by)"))
                if admin_id:
                    conn.execute(sa_text(f"UPDATE {tabela} SET created_by = :a WHERE created_by IS NULL"), {"a": admin_id})
                print(f"[dono] {tabela}.created_by criado; registros antigos ficaram com o usuário {admin_id}")
    except Exception:
        traceback.print_exc()

_garantir_coluna_dono()

def _garantir_endereco_obra():
    try:
        with engine.begin() as conn:
            existe = conn.execute(sa_text("""
                SELECT COUNT(*) FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'projects' AND COLUMN_NAME = 'endereco_obra'
            """)).scalar()
            if not existe:
                conn.execute(sa_text("ALTER TABLE projects ADD COLUMN endereco_obra VARCHAR(255) NULL AFTER nome_obra"))
                print("[obras] coluna endereco_obra criada")
    except Exception:
        traceback.print_exc()

_garantir_endereco_obra()

def _regiao_opcional():
    """Região deixou de ser obrigatória no cadastro: a coluna passa a aceitar vazio."""
    try:
        with engine.begin() as conn:
            nula = conn.execute(sa_text("""
                SELECT IS_NULLABLE FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'projects' AND COLUMN_NAME = 'regiao'
            """)).scalar()
            if nula == "NO":
                conn.execute(sa_text("ALTER TABLE projects MODIFY regiao ENUM('norte','sul','leste','oeste','centro') NULL"))
                print("[obras] região agora é opcional")
    except Exception:
        traceback.print_exc()

_regiao_opcional()

def _tipos_obra_completos():
    """O formulário oferece Reforma, Ampliação e Outro; a coluna só aceitava os 3 primeiros tipos."""
    try:
        with engine.begin() as conn:
            tipo = conn.execute(sa_text("""
                SELECT COLUMN_TYPE FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'projects' AND COLUMN_NAME = 'tipo_obra'
            """)).scalar() or ""
            if "Reforma" not in tipo:
                conn.execute(sa_text(
                    "ALTER TABLE projects MODIFY tipo_obra ENUM('Residencial','Comercial','Industrial','Reforma','Ampliação','Outro') NULL"
                ))
                print("[obras] tipo_obra aceita Reforma, Ampliação e Outro")
    except Exception:
        traceback.print_exc()

_tipos_obra_completos()

#=========================================================================================#
# ROTINA DE VISITA — estágio da obra, contato, concorrente e a próxima visita (7 em 7 dias)
#=========================================================================================#
DIAS_ENTRE_VISITAS = 7

ESTAGIOS_VISITA = [
    ("inicial", "Inicial"),
    ("alvenaria", "Alvenaria"),
    ("cobertura", "Cobertura"),
    ("instalacoes", "Instalações"),
    ("revestimento", "Revestimento"),
    ("acabamento", "Acabamento"),
    ("pintura", "Pintura"),
    ("concluida", "Concluída"),
]
ESTAGIOS_NOMES = dict(ESTAGIOS_VISITA)
# cores do emblema de cada estágio: progressão clara -> escura (quanto mais perto da entrega, mais escuro)
_ESTAGIO_RAMPA = ["#cde9ba", "#b3dc98", "#93c96f", "#78b84c", "#5fa83a", "#468f24", "#3a8519", "#24600e"]
ESTAGIO_CORES = {
    chave: {"bg": _ESTAGIO_RAMPA[i], "fg": "#1b1f1a" if i < 5 else "#ffffff"}
    for i, (chave, _nome) in enumerate(ESTAGIOS_VISITA)
}

def _garantir_rotina_visita():
    """Cria as colunas da rotina de visita e calcula a 1ª 'próxima visita' de quem já existia."""
    try:
        with engine.begin() as conn:
            cols_obras = {r[0] for r in conn.execute(sa_text("""
                SELECT COLUMN_NAME FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'projects'
            """))}
            if "proxima_visita" not in cols_obras:
                conn.execute(sa_text(
                    "ALTER TABLE projects ADD COLUMN proxima_visita DATE NULL, ADD INDEX idx_obras_proxima_visita (proxima_visita)"
                ))
                print("[obras] coluna proxima_visita criada")

            cols_vis = {r[0] for r in conn.execute(sa_text("""
                SELECT COLUMN_NAME FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'project_visits'
            """))}
            if "estagio_obra" not in cols_vis:
                conn.execute(sa_text(
                    "ALTER TABLE project_visits ADD COLUMN estagio_obra "
                    "ENUM('inicial','alvenaria','cobertura','instalacoes','revestimento','acabamento','pintura','concluida') "
                    "NULL AFTER status_obra"
                ))
            if "contato_nome" not in cols_vis:
                conn.execute(sa_text("ALTER TABLE project_visits ADD COLUMN contato_nome VARCHAR(150) NULL AFTER responsavel"))
            if "concorrente" not in cols_vis:
                conn.execute(sa_text("ALTER TABLE project_visits ADD COLUMN concorrente VARCHAR(150) NULL AFTER contato_nome"))
            # status_obra (iniciada/em_andamento/parada) deu lugar ao estágio; fica opcional para não quebrar o que já existe
            obrigatorio = conn.execute(sa_text("""
                SELECT IS_NULLABLE FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'project_visits' AND COLUMN_NAME = 'status_obra'
            """)).scalar()
            if obrigatorio == "NO":
                conn.execute(sa_text("ALTER TABLE project_visits MODIFY status_obra ENUM('iniciada','em_andamento','parada') NULL"))
            # observações deixou de ser obrigatória na tela
            obs_obrigatoria = conn.execute(sa_text("""
                SELECT IS_NULLABLE FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'project_visits' AND COLUMN_NAME = 'observacoes'
            """)).scalar()
            if obs_obrigatoria == "NO":
                conn.execute(sa_text("ALTER TABLE project_visits MODIFY observacoes TEXT NULL"))

            # quem já tinha obra cadastrada ganha uma 1ª data de próxima visita: última visita (ou início da obra) + 7 dias
            conn.execute(sa_text(f"""
                UPDATE projects o
                LEFT JOIN (SELECT obra_id, MAX(data_visita) AS ultima FROM project_visits GROUP BY obra_id) v
                       ON v.obra_id = o.id
                SET o.proxima_visita = DATE_ADD(COALESCE(v.ultima, o.data_inicio, DATE(o.created_at)), INTERVAL {DIAS_ENTRE_VISITAS} DAY)
                WHERE o.proxima_visita IS NULL
            """))
    except Exception:
        traceback.print_exc()

_garantir_rotina_visita()

def _obras_pendentes_visita():
    """Obras ativas (do usuário logado; todas, se ele for administrador) com a visita atrasada."""
    dono_sql, params = _filtro_dono("o")
    with engine.begin() as conn:
        return conn.execute(sa_text(f"""
            SELECT o.id, o.numero_obra, o.endereco_obra,
                   TRIM(CONCAT(COALESCE(o.nome, ''), ' ', COALESCE(o.sobrenome, ''))) AS cliente,
                   o.telefone, o.cidade, o.potencial_obra, o.proxima_visita,
                   DATEDIFF(CURDATE(), o.proxima_visita) AS dias_atraso,
                   (SELECT MAX(v.data_visita) FROM project_visits v WHERE v.obra_id = o.id) AS ultima_visita,
                   u.name AS cadastrado_por
            FROM projects o
            LEFT JOIN users u ON u.id = o.created_by
            WHERE {dono_sql}
              AND o.proxima_visita IS NOT NULL AND o.proxima_visita < CURDATE()
              AND UPPER(COALESCE(o.status, 'INICIANDO')) IN ('INICIANDO', 'ANDAMENTO')
            ORDER BY o.proxima_visita ASC
        """), params).mappings().all()

@app.context_processor
def _injetar_notificacoes():
    def notificacoes_pendentes():
        if not (current_user.is_authenticated and current_user.pode('obras', 'ver')):
            return 0
        return len(_obras_pendentes_visita())
    return {"notificacoes_pendentes": notificacoes_pendentes}

@app.route('/notificacoes')
@requer_permissao('obras', 'ver')
def notificacoes():
    return render_template('notificacoes.html', pendentes=_obras_pendentes_visita(),
                           dias_entre_visitas=DIAS_ENTRE_VISITAS)


def _validar_profissional(form, prof_id=None):
    dados = {
        "nome": " ".join((form.get("nome") or "").split()),
        "profissao": (form.get("profissao") or "").strip(),
        "telefone": _so_digitos(form.get("telefone")),
    }
    erros = {}
    if not dados["nome"]:
        erros["nome"] = "Informe o nome."
    if dados["profissao"] not in PROFISSOES:
        erros["profissao"] = "Escolha a profissão."
    if not dados["telefone"]:
        erros["telefone"] = "Informe o telefone."
    elif len(dados["telefone"]) not in (10, 11):
        erros["telefone"] = "Telefone com DDD: 10 ou 11 números."
    else:
        existente = _profissional_por_telefone(dados["telefone"], exceto_id=prof_id)
        if existente:
            erros["telefone"] = (f'Este telefone já está cadastrado para {existente["nome"]} '
                                 f'({existente["profissao"]}).')
    return dados, erros

def _render_profissionais(form=None, erros=None, editando=None, status=200):
    filtro = (request.args.get("profissao") or "").strip()
    dono_sql, params = _filtro_dono("p")
    sql = f"SELECT p.id, p.nome, p.profissao, p.telefone FROM professionals p WHERE {dono_sql}"
    if filtro in PROFISSOES:
        sql += " AND p.profissao = :prof"
        params["prof"] = filtro
    with engine.begin() as conn:
        rows = conn.execute(sa_text(sql + " ORDER BY p.nome, p.id"), params).mappings().all()
    return render_template(
        "profissionais.html", profissionais=rows, profissoes=PROFISSOES, filtro=filtro,
        form=form or {}, erros=erros or {}, editando=editando,
    ), status

@app.route('/profissionais', methods=['GET'])
@requer_permissao('pessoas', 'ver')
def lista_profissionais():
    editar_id = request.args.get("editar", type=int)
    if editar_id and current_user.pode("pessoas", "alterar"):
        p = _profissional_do_usuario(editar_id)
        if p:
            return _render_profissionais(form=dict(p), editando=editar_id)
    return _render_profissionais()

@app.route('/profissionais', methods=['POST'])
@requer_permissao('pessoas', 'inserir')
def novo_profissional():
    dados, erros = _validar_profissional(request.form)
    if erros:
        return _render_profissionais(form=dados, erros=erros, status=400)
    try:
        with engine.begin() as conn:
            conn.execute(sa_text("""
                INSERT INTO professionals (nome, profissao, telefone, created_by)
                VALUES (:nome, :profissao, :telefone, :dono)
            """), {**dados, "dono": int(current_user.id)})
    except IntegrityError:
        # outro usuário cadastrou o mesmo telefone ao mesmo tempo
        return _render_profissionais(form=dados, erros={"telefone": "Este telefone já está cadastrado."}, status=400)
    flash(f'{dados["nome"]} cadastrado como {dados["profissao"]}.', 'success')
    return redirect(url_for('lista_profissionais'))

@app.route('/profissionais/<int:prof_id>/editar', methods=['POST'])
@requer_permissao('pessoas', 'alterar')
def editar_profissional(prof_id):
    p = _profissional_do_usuario(prof_id)
    atual = p["telefone"] if p else None
    if atual is None:
        flash('Profissional não encontrado.', 'error')
        return redirect(url_for('lista_profissionais'))
    form = request.form.to_dict()
    form["telefone"] = atual  # o telefone identifica o profissional e não pode ser trocado
    dados, erros = _validar_profissional(form, prof_id=prof_id)
    if erros:
        return _render_profissionais(form=dados, erros=erros, editando=prof_id, status=400)
    with engine.begin() as conn:
        r = conn.execute(sa_text("""
            UPDATE professionals SET nome = :nome, profissao = :profissao WHERE id = :id
        """), {**dados, "id": prof_id})
    if r.rowcount == 0:
        flash('Profissional não encontrado.', 'error')
    else:
        flash(f'Cadastro de {dados["nome"]} atualizado.', 'success')
    return redirect(url_for('lista_profissionais'))

@app.route('/api/profissionais/telefone/<tel>', methods=['GET'])
@requer_permissao('pessoas', 'ver')
def buscar_profissional_por_telefone(tel):
    digitos = _so_digitos(tel)
    p = _profissional_por_telefone(digitos) if len(digitos) in (10, 11) else None
    if not p:
        return jsonify(encontrado=False)
    meu = _ve_tudo() or p["created_by"] == int(current_user.id)
    return jsonify(encontrado=True, id=p["id"], nome=p["nome"], profissao=p["profissao"],
                   telefone=_formatar_fone(p["telefone"]),
                   pode_editar=bool(meu and current_user.pode("pessoas", "alterar")))


#=========================================================================================#
# USUÁRIOS DO SISTEMA — cadastro, níveis de acesso e permissões
#=========================================================================================#
def _usuario_por_id(user_id):
    with engine.begin() as conn:
        return conn.execute(sa_text("""
            SELECT id, username, email, name, telefone, status, perfil, permissoes, created_at
            FROM users WHERE id = :id
        """), {"id": user_id}).mappings().first()

def _total_admins_ativos(exceto_id=None):
    with engine.begin() as conn:
        return conn.execute(sa_text("""
            SELECT COUNT(*) FROM users
            WHERE perfil = 'admin' AND status = 'aprovado' AND id <> :ex
        """), {"ex": exceto_id or 0}).scalar()

def _permissoes_do_form(form):
    """Lê os checkboxes 'perm_<modulo>_<acao>'. 'Inserir/Alterar/Excluir' já incluem 'Ver'."""
    perm = {}
    for m, _, acoes in MODULOS:
        marcadas = [a for a in acoes if form.get(f"perm_{m}_{a}")]
        if marcadas and "ver" in acoes and "ver" not in marcadas:
            marcadas.insert(0, "ver")
        if marcadas:
            perm[m] = marcadas
    return perm

def _render_form_usuario(usuario, permissoes, erros=None, novo=True):
    return render_template(
        'usuarios_sistema_form.html',
        usuario=usuario, permissoes=permissoes, erros=erros or {}, novo=novo,
        modulos=MODULOS, acoes=ACOES, perfis=PERFIS, status_opcoes=STATUS_USUARIO,
        perfis_json=json.dumps({k: v["permissoes"] for k, v in PERFIS.items()}),
    )

def _validar_form_usuario(form, novo, user_id=None):
    dados = {
        "name": (form.get("name") or "").strip(),
        "username": (form.get("username") or "").strip(),
        "email": (form.get("email") or "").strip().lower(),
        "telefone": (form.get("telefone") or "").strip(),
        "status": (form.get("status") or "aprovado").strip(),
        "perfil": (form.get("perfil") or "personalizado").strip(),
    }
    senha = form.get("password") or ""
    confirma = form.get("password_confirm") or ""
    erros = {}
    if not dados["name"]:
        erros["name"] = "Informe o nome."
    if not dados["username"]:
        erros["username"] = "Informe o nome de usuário."
    elif not re.fullmatch(r"[A-Za-z0-9._-]{3,100}", dados["username"]):
        erros["username"] = "Use de 3 a 100 letras, números, ponto, hífen ou sublinhado, sem espaços."
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", dados["email"]):
        erros["email"] = "Informe um e-mail válido."
    if dados["status"] not in STATUS_USUARIO:
        erros["status"] = "Situação inválida."
    if dados["perfil"] not in PERFIS:
        erros["perfil"] = "Nível de acesso inválido."
    if novo or senha:
        if len(senha) < 6:
            erros["password"] = "A senha precisa ter pelo menos 6 caracteres."
        elif senha != confirma:
            erros["password_confirm"] = "As senhas não conferem."

    if "username" not in erros or "email" not in erros:
        with engine.begin() as conn:
            existentes = conn.execute(sa_text("""
                SELECT username, email FROM users
                WHERE (username = :u OR email = :e) AND id <> :id
            """), {"u": dados["username"], "e": dados["email"], "id": user_id or 0}).mappings().all()
        for r in existentes:
            if r["username"] == dados["username"]:
                erros["username"] = "Esse nome de usuário já está em uso."
            if (r["email"] or "").lower() == dados["email"]:
                erros["email"] = "Esse e-mail já está cadastrado."

    if dados["perfil"] == "admin":
        permissoes = None
    elif dados["perfil"] == "personalizado":
        permissoes = _permissoes_do_form(form)
    else:
        permissoes = PERFIS[dados["perfil"]]["permissoes"]
    return dados, senha, permissoes, erros


@app.route('/usuarios', methods=['GET'])
@requer_permissao('usuarios', 'ver')
def lista_usuarios():
    with engine.begin() as conn:
        rows = conn.execute(sa_text("""
            SELECT id, username, email, name, telefone, status, perfil, permissoes, created_at
            FROM users
            ORDER BY FIELD(perfil, 'admin', 'gerente', 'operador', 'consulta', 'personalizado'), name, id
        """)).mappings().all()
    usuarios = []
    for r in rows:
        u = dict(r)
        perm = _permissoes_efetivas(u["perfil"], u["permissoes"])
        u["resumo"] = "Acesso total" if perm is None else (
            ", ".join(n for m, n, _ in MODULOS if m in perm) or "Nenhuma tela liberada")
        usuarios.append(u)
    return render_template('usuarios_sistema.html', usuarios=usuarios,
                           perfis=PERFIS, status_opcoes=STATUS_USUARIO)


@app.route('/usuarios/novo', methods=['GET', 'POST'])
@requer_permissao('usuarios', 'inserir')
def novo_usuario():
    if request.method == 'GET':
        vazio = {"status": "aprovado", "perfil": "operador"}
        return _render_form_usuario(vazio, PERFIS["operador"]["permissoes"], novo=True)

    dados, senha, permissoes, erros = _validar_form_usuario(request.form, novo=True)
    if erros:
        return _render_form_usuario(dados, permissoes, erros, novo=True), 400

    hashed = bcrypt.hashpw(senha.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    with engine.begin() as conn:
        conn.execute(sa_text("""
            INSERT INTO users (username, password, email, name, telefone, status, categoria,
                               perfil, permissoes, profile_picture, member_status, created_at)
            VALUES (:username, :password, :email, :name, :telefone, :status, 'user_padrao',
                    :perfil, :permissoes, 'PLACEHOLDER-IMAGE.png', 'ativo', NOW())
        """), {**dados, "password": hashed, "telefone": dados["telefone"] or None,
               "permissoes": None if permissoes is None else json.dumps(permissoes)})
    flash(f'Usuário "{dados["username"]}" cadastrado.', 'success')
    return redirect(url_for('lista_usuarios'))


@app.route('/usuarios/<int:user_id>/editar', methods=['GET', 'POST'])
@requer_permissao('usuarios', 'alterar')
def editar_usuario(user_id):
    atual = _usuario_por_id(user_id)
    if not atual:
        flash('Usuário não encontrado.', 'error')
        return redirect(url_for('lista_usuarios'))

    if request.method == 'GET':
        perm = _permissoes_efetivas(atual["perfil"], atual["permissoes"])
        return _render_form_usuario(dict(atual), perm, novo=False)

    dados, senha, permissoes, erros = _validar_form_usuario(request.form, novo=False, user_id=user_id)
    dados["id"] = user_id
    # não deixa o sistema ficar sem nenhum administrador ativo
    deixa_de_ser_admin = atual["perfil"] == "admin" and (dados["perfil"] != "admin" or dados["status"] != "aprovado")
    if deixa_de_ser_admin and _total_admins_ativos(exceto_id=user_id) == 0:
        erros["perfil"] = "Este é o único administrador ativo. Cadastre outro administrador antes de mudar este."
    if erros:
        return _render_form_usuario(dados, permissoes, erros, novo=False), 400

    params = {**dados, "telefone": dados["telefone"] or None,
              "permissoes": None if permissoes is None else json.dumps(permissoes)}
    sets = "username=:username, email=:email, name=:name, telefone=:telefone, status=:status, perfil=:perfil, permissoes=:permissoes"
    if senha:
        sets += ", password=:password"
        params["password"] = bcrypt.hashpw(senha.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    with engine.begin() as conn:
        conn.execute(sa_text(f"UPDATE users SET {sets}, updated_at=NOW() WHERE id=:id"), params)
    flash(f'Usuário "{dados["username"]}" atualizado.', 'success')
    return redirect(url_for('lista_usuarios'))


@app.route('/usuarios/<int:user_id>/excluir', methods=['POST'])
@requer_permissao('usuarios', 'excluir')
def excluir_usuario(user_id):
    atual = _usuario_por_id(user_id)
    if not atual:
        flash('Usuário não encontrado.', 'error')
    elif str(user_id) == current_user.id:
        flash('Você não pode excluir o seu próprio usuário.', 'error')
    elif atual["perfil"] == "admin" and _total_admins_ativos(exceto_id=user_id) == 0:
        flash('Este é o único administrador ativo e não pode ser excluído.', 'error')
    else:
        try:
            with engine.begin() as conn:
                conn.execute(sa_text("DELETE FROM users WHERE id = :id"), {"id": user_id})
            flash(f'Usuário "{atual["username"]}" excluído.', 'success')
        except IntegrityError:
            traceback.print_exc()
            flash('Não foi possível excluir: há registros ligados a este usuário. Bloqueie o acesso dele em vez de excluir.', 'error')
    return redirect(url_for('lista_usuarios'))


if __name__ == '__main__':
    host = os.environ.get("FLASK_HOST", "0.0.0.0")
    port = int(os.environ.get("FLASK_PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host=host, port=port, debug=debug)
# =============================================================