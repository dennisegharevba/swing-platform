#!/usr/bin/env bash
# =============================================================================
# VPS Setup Script — COT Intelligence Platform
# Tested on: Ubuntu 22.04 LTS / Ubuntu 24.04 LTS
# Run as root or with sudo
# =============================================================================
set -euo pipefail

PLATFORM_DIR="/opt/swing-platform"
SERVICE_USER="swing"
REPO_URL="${1:-https://github.com/YOUR_USER/swing-platform.git}"

echo "============================================================"
echo "  COT Intelligence Platform — VPS Setup"
echo "============================================================"

# ── System update ─────────────────────────────────────────────────────────────
apt-get update -y
apt-get upgrade -y
apt-get install -y \
    git curl wget unzip \
    python3.12 python3.12-dev python3-pip python3-venv \
    postgresql postgresql-contrib \
    redis-server \
    nginx certbot python3-certbot-nginx \
    ufw fail2ban \
    build-essential libpq-dev

# ── Docker ────────────────────────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
fi

if ! command -v docker-compose &>/dev/null; then
    curl -SL "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" \
        -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
fi

# ── Service user ──────────────────────────────────────────────────────────────
if ! id "$SERVICE_USER" &>/dev/null; then
    useradd -m -s /bin/bash "$SERVICE_USER"
    usermod -aG docker "$SERVICE_USER"
    echo "Created user: $SERVICE_USER"
fi

# ── Clone / update repo ───────────────────────────────────────────────────────
if [ -d "$PLATFORM_DIR/.git" ]; then
    echo "Updating existing repo..."
    cd "$PLATFORM_DIR"
    git pull origin main
else
    echo "Cloning repo..."
    git clone "$REPO_URL" "$PLATFORM_DIR"
    chown -R "$SERVICE_USER:$SERVICE_USER" "$PLATFORM_DIR"
fi

cd "$PLATFORM_DIR"

# ── Environment file ──────────────────────────────────────────────────────────
if [ ! -f "$PLATFORM_DIR/.env" ]; then
    cp "$PLATFORM_DIR/.env.example" "$PLATFORM_DIR/.env"
    echo ""
    echo "⚠️  .env file created from template."
    echo "    Edit $PLATFORM_DIR/.env with your API keys before starting."
    echo ""
fi

# ── Firewall ──────────────────────────────────────────────────────────────────
ufw --force enable
ufw allow ssh
ufw allow 80/tcp
ufw allow 443/tcp
ufw deny 5432/tcp   # Block external PostgreSQL
ufw deny 6379/tcp   # Block external Redis
echo "Firewall configured."

# ── Fail2ban ──────────────────────────────────────────────────────────────────
systemctl enable fail2ban
systemctl start fail2ban

# ── Streamlit config ──────────────────────────────────────────────────────────
mkdir -p "$PLATFORM_DIR/.streamlit"
cp "$PLATFORM_DIR/config/streamlit_config.toml" "$PLATFORM_DIR/.streamlit/config.toml"

# ── Systemd service — dashboard ───────────────────────────────────────────────
cat > /etc/systemd/system/cot-platform.service << EOF
[Unit]
Description=COT Intelligence Platform (Docker Compose)
Requires=docker.service
After=docker.service network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$PLATFORM_DIR
ExecStart=/usr/local/bin/docker-compose -f docker/docker-compose.yml up -d
ExecStop=/usr/local/bin/docker-compose -f docker/docker-compose.yml down
TimeoutStartSec=300
User=$SERVICE_USER

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable cot-platform.service

# ── Log rotation ──────────────────────────────────────────────────────────────
cat > /etc/logrotate.d/cot-platform << EOF
$PLATFORM_DIR/data/logs/*.log {
    daily
    rotate 30
    compress
    missingok
    notifempty
    create 0644 $SERVICE_USER $SERVICE_USER
}
EOF

# ── Init database (SQLite default) ───────────────────────────────────────────
mkdir -p "$PLATFORM_DIR/data"
chown -R "$SERVICE_USER:$SERVICE_USER" "$PLATFORM_DIR/data"

echo ""
echo "============================================================"
echo "  Setup complete!"
echo "============================================================"
echo ""
echo "Next steps:"
echo "  1. Edit your environment file:"
echo "     nano $PLATFORM_DIR/.env"
echo ""
echo "  2. Start the platform:"
echo "     cd $PLATFORM_DIR && docker-compose -f docker/docker-compose.yml up -d"
echo ""
echo "  3. View logs:"
echo "     docker-compose -f $PLATFORM_DIR/docker/docker-compose.yml logs -f"
echo ""
echo "  4. Access dashboard:"
echo "     http://YOUR_SERVER_IP"
echo ""
echo "  5. (Optional) Configure SSL:"
echo "     certbot --nginx -d yourdomain.com"
echo ""
