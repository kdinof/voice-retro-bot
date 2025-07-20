#!/bin/bash

# Voice Retro Bot Deployment Script
# Usage: bash deploy.sh
# Run this script on your server at 142.93.209.251

set -e  # Exit on any error

# Configuration
SERVER_IP="142.93.209.251"
REPO_URL="https://github.com/yourusername/voice-retro.git"  # Update this with your repo
APP_DIR="/opt/voice-retro"
SERVICE_NAME="voice-retro"
NGINX_SITE="voice-retro"

echo "🚀 Starting Voice Retro Bot deployment on $SERVER_IP"

# Function to print colored output
print_step() {
    echo -e "\n🔷 $1"
}

print_success() {
    echo -e "✅ $1"
}

print_error() {
    echo -e "❌ $1"
}

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   print_error "This script should not be run as root. Run as a regular user with sudo privileges."
   exit 1
fi

print_step "Step 1: Update system packages"
sudo apt update && sudo apt upgrade -y
print_success "System packages updated"

print_step "Step 2: Install system dependencies"
sudo apt install -y python3 python3-pip python3-venv git nginx ffmpeg curl

# Check FFmpeg installation
if command -v ffmpeg &> /dev/null; then
    print_success "FFmpeg installed: $(ffmpeg -version | head -n1)"
else
    print_error "FFmpeg installation failed"
    exit 1
fi

print_step "Step 3: Create application user and directory"
if ! id "voice-retro" &>/dev/null; then
    sudo adduser --system --group --home $APP_DIR voice-retro
    print_success "Created voice-retro user"
else
    print_success "voice-retro user already exists"
fi

sudo mkdir -p $APP_DIR
sudo chown voice-retro:voice-retro $APP_DIR

print_step "Step 4: Clone/update repository"
if [ -d "$APP_DIR/.git" ]; then
    print_success "Repository exists, pulling latest changes"
    sudo -u voice-retro git -C $APP_DIR pull
else
    print_success "Cloning repository"
    sudo -u voice-retro git clone $REPO_URL $APP_DIR
fi

print_step "Step 5: Set up Python virtual environment"
sudo -u voice-retro python3 -m venv $APP_DIR/venv
sudo -u voice-retro $APP_DIR/venv/bin/pip install --upgrade pip
sudo -u voice-retro $APP_DIR/venv/bin/pip install -r $APP_DIR/requirements.txt
print_success "Python dependencies installed"

print_step "Step 6: Configure environment variables"
if [ ! -f "$APP_DIR/.env" ]; then
    sudo cp $APP_DIR/.env.production $APP_DIR/.env
    sudo chown voice-retro:voice-retro $APP_DIR/.env
    sudo chmod 600 $APP_DIR/.env
    print_success "Environment file created from template"
    echo "⚠️  IMPORTANT: Edit $APP_DIR/.env and set your webhook secret!"
else
    print_success "Environment file already exists"
fi

print_step "Step 7: Set up systemd service"
sudo cp $APP_DIR/voice-retro.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable $SERVICE_NAME
print_success "Systemd service configured"

print_step "Step 8: Configure Nginx"
# Add rate limiting to nginx.conf if not present
if ! grep -q "limit_req_zone" /etc/nginx/nginx.conf; then
    sudo sed -i '/http {/a\\tlimit_req_zone $binary_remote_addr zone=webhook_limit:10m rate=5r/s;' /etc/nginx/nginx.conf
    print_success "Added rate limiting to nginx.conf"
fi

sudo cp $APP_DIR/nginx-voice-retro.conf /etc/nginx/sites-available/$NGINX_SITE
sudo ln -sf /etc/nginx/sites-available/$NGINX_SITE /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default  # Remove default site
sudo nginx -t
print_success "Nginx configuration applied"

print_step "Step 9: Configure firewall"
sudo ufw allow ssh
sudo ufw allow 'Nginx Full'
sudo ufw --force enable
print_success "Firewall configured"

print_step "Step 10: Create temp directory and set permissions"
sudo -u voice-retro mkdir -p $APP_DIR/temp
sudo chmod 755 $APP_DIR/temp
print_success "Temp directory created"

print_step "Step 11: Test configuration"
echo "Testing Python application..."
sudo -u voice-retro $APP_DIR/venv/bin/python -c "
import sys
sys.path.insert(0, '$APP_DIR')
from config import settings
print('✅ Configuration loaded successfully')
print(f'Bot token: {settings.bot_token[:10]}...')
print(f'Webhook URL: {settings.telegram_webhook_url}')
"

print_step "Step 12: Start services"
sudo systemctl restart nginx
sudo systemctl start $SERVICE_NAME

# Wait a moment for services to start
sleep 3

# Check service status
if sudo systemctl is-active --quiet $SERVICE_NAME; then
    print_success "Voice Retro Bot service is running"
else
    print_error "Service failed to start. Check logs with: sudo journalctl -u $SERVICE_NAME -f"
    exit 1
fi

if sudo systemctl is-active --quiet nginx; then
    print_success "Nginx is running"
else
    print_error "Nginx failed to start. Check logs with: sudo journalctl -u nginx -f"
    exit 1
fi

print_step "Step 13: Test webhook endpoint"
echo "Testing webhook endpoint..."
WEBHOOK_TEST=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/api/webhooks/telegram || echo "000")
if [ "$WEBHOOK_TEST" = "405" ] || [ "$WEBHOOK_TEST" = "200" ]; then
    print_success "Webhook endpoint is accessible (HTTP $WEBHOOK_TEST)"
else
    print_error "Webhook endpoint test failed (HTTP $WEBHOOK_TEST)"
fi

echo "
🎉 Deployment completed successfully!

📋 Next steps:
1. Edit environment file: sudo nano $APP_DIR/.env
   - Set TELEGRAM_WEBHOOK_SECRET to a secure random string
   
2. Set up Telegram webhook:
   curl -X POST \"https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook\" \\
     -H \"Content-Type: application/json\" \\
     -d '{\"url\": \"http://$SERVER_IP/api/webhooks/telegram\", \"secret_token\": \"YOUR_WEBHOOK_SECRET\"}'

3. Test the bot by sending /start to @voice_retro_bot

📊 Service management commands:
- View logs: sudo journalctl -u $SERVICE_NAME -f
- Restart service: sudo systemctl restart $SERVICE_NAME
- Service status: sudo systemctl status $SERVICE_NAME

🔧 File locations:
- Application: $APP_DIR
- Logs: /var/log/nginx/voice-retro.*
- Service: /etc/systemd/system/$SERVICE_NAME.service
- Nginx config: /etc/nginx/sites-available/$NGINX_SITE
"