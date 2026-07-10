#!/usr/bin/env bash
# =============================================================================
# SplitCharts Alerts - setup automático en una VM Ubuntu (Oracle Always Free)
#
# Deja el monitor de alertas corriendo 24/7 como servicio (systemd):
#   - arranca solo si la VM se reinicia
#   - se reinicia solo si se cae
#   - revisa cada 60s (según poll_seconds de alerts_config.json)
#
# Uso en la VM (Ubuntu):
#   git clone https://github.com/pablo828699-lab/splitcharts-alerts.git
#   cd splitcharts-alerts
#   bash setup_vm.sh
# =============================================================================
set -e

echo "=== SplitCharts Alerts :: setup en la VM ==="
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

echo "--> Instalando dependencias del sistema..."
sudo apt-get update -y
sudo apt-get install -y python3-pip python3-venv git

echo "--> Creando entorno de Python e instalando librerías..."
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install requests pandas numpy ta yfinance

echo ""
echo "--> Pegá tus credenciales de Telegram (quedan solo en esta VM):"
read -r -p "    BOT TOKEN: " TOK
read -r -p "    CHAT ID  : " CHAT
cat > creds.env <<EOF
TELEGRAM_BOT_TOKEN=$TOK
TELEGRAM_CHAT_ID=$CHAT
EOF
chmod 600 creds.env

echo "--> Creando el servicio systemd..."
SVC=/etc/systemd/system/splitcharts-alerts.service
sudo bash -c "cat > $SVC" <<EOF
[Unit]
Description=SplitCharts Telegram Alerts
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$DIR
EnvironmentFile=$DIR/creds.env
ExecStart=$DIR/venv/bin/python $DIR/telegram_alerts.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable splitcharts-alerts
sudo systemctl restart splitcharts-alerts
sleep 3

echo ""
echo "=== Estado del servicio ==="
sudo systemctl status splitcharts-alerts --no-pager || true

echo ""
echo "✅ Listo. El monitor corre 24/7 (te llega un 'monitor iniciado' a Telegram)."
echo ""
echo "Comandos útiles:"
echo "   Ver logs en vivo:   sudo journalctl -u splitcharts-alerts -f"
echo "   Reiniciar:          sudo systemctl restart splitcharts-alerts"
echo "   Actualizar reglas:  git pull && sudo systemctl restart splitcharts-alerts"
