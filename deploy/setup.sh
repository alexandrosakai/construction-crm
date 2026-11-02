#!/usr/bin/env bash
# Deploy do Empresa Exemplo em Ubuntu/Debian. Rodar como root, de dentro da pasta do projeto:
#   sudo bash deploy/setup.sh user@example.com
set -euo pipefail

DOMAIN="example.com"
EMAIL="${1:?Uso: bash deploy/setup.sh user@example.com}"
APP_DIR="/opt/construction-crm"
SRC_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DB_NAME="app_db"
DB_USER="crm"

echo "==> Pacotes"
apt update
apt install -y python3 python3-venv python3-pip nginx mysql-server certbot python3-certbot-nginx rsync

echo "==> Usuário do sistema e arquivos"
id construction-crm &>/dev/null || useradd --system --home "$APP_DIR" --shell /usr/sbin/nologin construction-crm
mkdir -p "$APP_DIR"
rsync -a --exclude venv --exclude nohup.out --exclude .env "$SRC_DIR"/ "$APP_DIR"/
mkdir -p "$APP_DIR/static/uploads/visitas"

echo "==> Ambiente Python"
python3 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install --upgrade pip
"$APP_DIR/venv/bin/pip" install -r "$APP_DIR/requirements.txt"

echo "==> Banco de dados"
systemctl enable --now mysql
if [ ! -f "$APP_DIR/.env" ]; then
    DB_PASS="$(openssl rand -hex 16)"
    mysql -e "CREATE DATABASE IF NOT EXISTS \`$DB_NAME\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
    mysql -e "CREATE USER IF NOT EXISTS '$DB_USER'@'localhost' IDENTIFIED BY '$DB_PASS';"
    mysql -e "ALTER USER '$DB_USER'@'localhost' IDENTIFIED BY '$DB_PASS';"
    mysql -e "GRANT ALL PRIVILEGES ON \`$DB_NAME\`.* TO '$DB_USER'@'localhost'; FLUSH PRIVILEGES;"
    cat > "$APP_DIR/.env" <<EOF
FLASK_SECRET_KEY=$(openssl rand -hex 32)
FLASK_DEBUG=0
DB_USER=$DB_USER
DB_PASS=$DB_PASS
DB_HOST=localhost
DB_PORT=3306
DB_NAME=$DB_NAME
EOF
    chmod 600 "$APP_DIR/.env"
fi
# Importa o dump só se o banco estiver vazio (não sobrescreve dados existentes)
TABLES=$(mysql -N -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='$DB_NAME';")
if [ "$TABLES" = "0" ] && [ -f "$APP_DIR/database/schema.sql" ]; then
    echo "    importando database/schema.sql"
    mysql "$DB_NAME" < "$APP_DIR/database/schema.sql"
else
    echo "    banco já tem $TABLES tabelas, import ignorado"
fi

chown -R construction-crm:www-data "$APP_DIR"
chmod -R g+rX "$APP_DIR"
chmod -R g+w "$APP_DIR/static/uploads"

echo "==> Serviço (Gunicorn)"
cp "$APP_DIR/deploy/construction-crm.service" /etc/systemd/system/construction-crm.service
systemctl daemon-reload
systemctl enable --now construction-crm
systemctl restart construction-crm

echo "==> Nginx"
cp "$APP_DIR/deploy/nginx-construction-crm.conf" /etc/nginx/sites-available/construction-crm
ln -sf /etc/nginx/sites-available/construction-crm /etc/nginx/sites-enabled/construction-crm
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx

echo "==> Firewall"
if command -v ufw &>/dev/null; then
    ufw allow OpenSSH
    ufw allow 'Nginx Full'
    ufw delete allow 5000 2>/dev/null || true
fi

echo "==> HTTPS (Let's Encrypt)"
certbot --nginx -d "$DOMAIN" -d "www.$DOMAIN" -m "$EMAIL" --agree-tos --redirect --non-interactive

echo
echo "Pronto: https://$DOMAIN"
echo "Logs:  journalctl -u construction-crm -f"
