cat > /opt/app/deploy-construction-crm.sh <<'SCRIPT'
#!/usr/bin/env bash
set -euo pipefail
DOMAIN="example.com"
VPS_IP="203.0.113.10"
EMAIL="${1:-}"
SRC=/opt/app/construction-crm
APP=/opt/construction-crm
DB_NAME=app_db
DB_USER=crm

[ -f "$SRC/app.py" ] || { echo "ERRO: não achei $SRC/app.py"; exit 1; }

echo "==> Parando app antigo"
pkill -f "python.*app.py" 2>/dev/null || true

echo "==> Pacotes"
apt update
apt install -y python3 python3-venv python3-pip nginx mysql-server certbot python3-certbot-nginx rsync

echo "==> Copiando projeto para $APP"
id construction-crm &>/dev/null || useradd --system --home "$APP" --shell /usr/sbin/nologin construction-crm
mkdir -p "$APP"
rsync -a --exclude venv --exclude nohup.out --exclude .env "$SRC"/ "$APP"/
mkdir -p "$APP/static/uploads/visitas"

cat > "$APP/requirements.txt" <<EOF
Flask
Flask-Login
Flask-Mail
itsdangerous
SQLAlchemy
PyMySQL
cryptography
bcrypt
pandas
Pillow
python-slugify
gunicorn
EOF

echo "==> Ambiente Python"
python3 -m venv "$APP/venv"
"$APP/venv/bin/pip" install --upgrade pip
"$APP/venv/bin/pip" install -r "$APP/requirements.txt"

echo "==> Banco de dados"
systemctl enable --now mysql
if [ ! -f "$APP/.env" ]; then
    DB_PASS="$(openssl rand -hex 16)"
    mysql -e "CREATE DATABASE IF NOT EXISTS \`$DB_NAME\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
    mysql -e "CREATE USER IF NOT EXISTS '$DB_USER'@'localhost' IDENTIFIED BY '$DB_PASS';"
    mysql -e "ALTER USER '$DB_USER'@'localhost' IDENTIFIED BY '$DB_PASS';"
    mysql -e "GRANT ALL PRIVILEGES ON \`$DB_NAME\`.* TO '$DB_USER'@'localhost'; FLUSH PRIVILEGES;"
    cat > "$APP/.env" <<EOF
FLASK_SECRET_KEY=$(openssl rand -hex 32)
FLASK_DEBUG=0
DB_USER=$DB_USER
DB_PASS=$DB_PASS
DB_HOST=localhost
DB_PORT=3306
DB_NAME=$DB_NAME
EOF
    chmod 600 "$APP/.env"
fi
TABLES=$(mysql -N -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='$DB_NAME';")
if [ "$TABLES" = "0" ] && [ -f "$APP/database/schema.sql" ]; then
    echo "    importando database/schema.sql"
    mysql "$DB_NAME" < "$APP/database/schema.sql"
else
    echo "    banco já tem $TABLES tabelas, import ignorado"
fi

chown -R construction-crm:www-data "$APP"
chmod -R g+rX "$APP"
chmod -R g+w "$APP/static/uploads"

echo "==> Serviço Gunicorn"
cat > /etc/systemd/system/construction-crm.service <<EOF
[Unit]
Description=Empresa Exemplo (Flask via Gunicorn)
After=network.target mysql.service

[Service]
User=construction-crm
Group=www-data
WorkingDirectory=$APP
EnvironmentFile=$APP/.env
ExecStart=$APP/venv/bin/gunicorn --workers 3 --bind 127.0.0.1:8000 --timeout 120 --access-logfile - app:app
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable construction-crm
systemctl restart construction-crm
sleep 3
if ! curl -fsS -o /dev/null http://127.0.0.1:8000/login; then
    echo "ERRO: o app não respondeu. Últimas linhas do log:"
    journalctl -u construction-crm -n 40 --no-pager
    exit 1
fi
echo "    app respondendo em 127.0.0.1:8000"

echo "==> Nginx"
cat > /etc/nginx/sites-available/construction-crm <<'EOF'
server {
    listen 80 default_server;
    server_name example.com www.example.com _;

    client_max_body_size 25M;

    location /static/ {
        alias /opt/construction-crm/static/;
        expires 7d;
        access_log off;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }
}
EOF
ln -sf /etc/nginx/sites-available/construction-crm /etc/nginx/sites-enabled/construction-crm
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx

if command -v ufw &>/dev/null && ufw status | grep -q active; then
    ufw allow OpenSSH; ufw allow 'Nginx Full'
fi

echo "==> HTTPS"
RESOLVED=$(getent ahostsv4 "$DOMAIN" | awk 'NR==1{print $1}')
if [ "$RESOLVED" = "$VPS_IP" ]; then
    if [ -n "$EMAIL" ]; then MAIL_OPT=(-m "$EMAIL"); else MAIL_OPT=(--register-unsafely-without-email); fi
    certbot --nginx -d "$DOMAIN" -d "www.$DOMAIN" "${MAIL_OPT[@]}" --agree-tos --redirect --non-interactive
    echo "PRONTO: https://$DOMAIN"
else
    echo "Site no ar em: http://$VPS_IP"
    echo "HTTPS pulado: $DOMAIN aponta para '$RESOLVED' (precisa ser $VPS_IP)."
    echo "Arrume o DNS no Cloudflare e rode de novo: bash /opt/app/deploy-construction-crm.sh"
fi
SCRIPT
bash /opt/app/deploy-construction-crm.sh
