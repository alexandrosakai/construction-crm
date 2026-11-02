# 🏗️ construction-crm

**CRM web para construtoras e lojas de materiais: cadastre obras, acompanhe etapas e visitas, e entenda sua carteira em um painel.**

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.x-000000?logo=flask&logoColor=white)
![MariaDB](https://img.shields.io/badge/MariaDB-10.11-003545?logo=mariadb&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)

Um sistema completo, em português, para quem vende para obras: registra clientes e projetos, controla o que acontece em cada etapa, guarda o histórico de visitas com fotos e mostra, em relatórios, onde estão as melhores oportunidades.

## ✨ Funcionalidades

- **Cadastro de obras** com cliente pessoa física/jurídica, endereço (autocompletar por CEP), tipo, padrão, potencial, metragem, datas e status
- **Etapas e visitas** de cada obra, com observações e **fotos** anexadas
- **Profissionais e vendedores** vinculados a cada projeto
- **Relatórios e painel (BI)**: obras por região, status, potencial e metragem, com filtros
- **Perfis de acesso** (administrador, gerente, operador, consulta e personalizado) com permissões por módulo
- **Cadastro com aprovação**: novos usuários entram como pendentes até um administrador liberar
- **Pesquisas** com arquitetos e profissionais da obra
- **Notificações** de visitas e etapas próximas
- **Módulos extras**: checklists (PWA), diagnóstico empresarial e metas de vendedores (com avisos por WhatsApp)

## 🧰 Tecnologias

![Flask](https://img.shields.io/badge/Flask-000000?logo=flask&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-D71F00?logo=sqlalchemy&logoColor=white)
![Gunicorn](https://img.shields.io/badge/Gunicorn-499848?logo=gunicorn&logoColor=white)
![pandas](https://img.shields.io/badge/pandas-150458?logo=pandas&logoColor=white)
![nginx](https://img.shields.io/badge/nginx-009639?logo=nginx&logoColor=white)

Python · Flask · Flask-Login · SQLAlchemy + PyMySQL · MariaDB/MySQL · bcrypt · pandas · Gunicorn · nginx · Bootstrap 5, Font Awesome e Chart.js (via CDN)

## 📋 Requisitos

- **Com Docker:** Docker 24+ e Docker Compose v2
- **Sem Docker:** Python 3.10+, MariaDB 10.6+ (ou MySQL 8), nginx (opcional, para produção)
- Os navegadores precisam de internet: o visual usa Bootstrap, Font Awesome e Chart.js por CDN

## 🚀 Instalação

### Com Docker (recomendado)

```bash
git clone https://github.com/alexandrosakai/construction-crm.git
cd construction-crm
cp .env.example .env
# edite o .env: defina FLASK_SECRET_KEY e DB_PASS com valores aleatórios longos
#   openssl rand -hex 32
docker compose up -d --build
```

Acesse `http://127.0.0.1:8000`. O compose sobe o app e um MariaDB já com as tabelas de `database/schema.sql`.

**Primeiro administrador:** crie sua conta em `/register` e promova-a:

```bash
docker compose exec db sh -c 'mariadb -u"$MARIADB_USER" -p"$MARIADB_PASSWORD" "$MARIADB_DATABASE" \
  -e "UPDATE users SET status='"'"'aprovado'"'"', perfil='"'"'admin'"'"' WHERE username='"'"'SEU_USUARIO'"'"'"'
```

### Sem Docker (servidor Ubuntu/Debian)

Instalação automática (pacotes, usuário do sistema, banco com senha aleatória, systemd, nginx e HTTPS):

```bash
# edite DOMAIN em deploy/setup.sh antes (padrão: example.com)
sudo bash deploy/setup.sh voce@example.com
```

Instalação manual:

```bash
python3 -m venv venv && . venv/bin/activate
pip install -r requirements.txt

mysql -u root -p -e "CREATE DATABASE app_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
mysql -u root -p app_db < database/schema.sql

cp .env.example .env      # preencha FLASK_SECRET_KEY, DB_USER, DB_PASS...
set -a; . ./.env; set +a
gunicorn --workers 3 --bind 127.0.0.1:8000 app:app
```

> Em produção rode **uma vez com `--workers 1`** em um banco novo, para as migrações automáticas não concorrerem entre workers. O esquema incluído já vem completo, então isso só importa se você alterar o banco.

## ⚙️ Configuração

Tudo por variáveis de ambiente (`.env.example`):

| Variável | Descrição |
|---|---|
| `FLASK_SECRET_KEY` | segredo das sessões (**obrigatória**) |
| `DB_USER`, `DB_PASS`, `DB_HOST`, `DB_PORT`, `DB_NAME` | conexão com o banco (`DB_PASS` é **obrigatória**, sem valor padrão) |
| `FLASK_DEBUG` | `0` em produção |
| `APP_PORT` | porta local usada pelo Docker (padrão `8000`) |

## 🧭 Como usar

1. Entre com o administrador e libere os usuários pendentes em **Usuários**.
2. Cadastre uma obra em **Cadastro de obras** (o CEP preenche o endereço).
3. Registre **etapas** e **visitas** (com fotos) conforme o projeto avança.
4. Acompanhe a carteira em **Relatórios** e use os filtros por região, status e potencial.

## 📁 Estrutura de pastas

```
construction-crm/
├── app.py                 # aplicação Flask (rotas, regras, migrações)
├── templates/             # páginas HTML (Jinja2)
├── static/                # CSS, JS e uploads
├── database/schema.sql    # esquema do banco (somente estrutura)
├── checklist/             # servidor e telas de checklists (SQLite)
├── diagnostico/           # módulo de diagnóstico empresarial
├── metas_vendedores/      # scripts de metas e avisos de vendedores
├── deploy/                # systemd, nginx e scripts de instalação
├── Dockerfile
└── docker-compose.yml
```

## 🗺️ Roadmap

- [ ] Testes automatizados e integração contínua (GitHub Actions)
- [ ] Migrações de banco versionadas (Alembic)
- [ ] API REST documentada (OpenAPI)
- [ ] Interface traduzida (inglês e espanhol)
- [ ] Exportação de relatórios em PDF/Excel
- [ ] Assistente para criar o primeiro administrador

## 🤝 Como contribuir

1. Faça um fork e crie uma branch: `git checkout -b minha-melhoria`
2. Descreva claramente o problema ou a funcionalidade no commit
3. Abra um Pull Request explicando o que mudou e como testar

Bugs e ideias são bem-vindos nas *Issues*.

## 📄 Licença

Distribuído sob a licença MIT. Veja o arquivo [LICENSE](LICENSE).

> **Antes de publicar na internet:** troque os textos de exemplo (nomes, e-mails, domínios `example.com`), adicione seu logo conforme `static/img/IMAGENS-LEIA-ME.txt` e use HTTPS.
