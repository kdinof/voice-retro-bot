#!/bin/bash

# Voice Retro Bot Simplified Deployment Script (Polling Mode)
# Usage: bash deploy-polling.sh
# Run this script on your server at 142.93.209.251

set -e  # Exit on any error

# Configuration
SERVER_IP="142.93.209.251"
APP_DIR="/opt/voice-retro"
SERVICE_NAME="voice-retro"

echo "🚀 Starting Voice Retro Bot deployment (Polling Mode) on $SERVER_IP"

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
sudo apt install -y python3 python3-pip python3-venv git ffmpeg curl

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

print_step "Step 4: Set up Python virtual environment"
sudo -u voice-retro python3 -m venv $APP_DIR/venv
sudo -u voice-retro $APP_DIR/venv/bin/pip install --upgrade pip
sudo -u voice-retro $APP_DIR/venv/bin/pip install -r $APP_DIR/requirements.txt
print_success "Python dependencies installed"

print_step "Step 5: Configure environment variables"
if [ ! -f "$APP_DIR/.env" ]; then
    sudo cp $APP_DIR/.env.production $APP_DIR/.env
    sudo chown voice-retro:voice-retro $APP_DIR/.env
    sudo chmod 600 $APP_DIR/.env
    print_success "Environment file created from template"
else
    print_success "Environment file already exists"
fi

print_step "Step 6: Set up systemd service"
sudo cp $APP_DIR/voice-retro.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable $SERVICE_NAME
print_success "Systemd service configured for polling mode"

print_step "Step 7: Configure basic firewall (outbound only)"
sudo ufw allow ssh
sudo ufw --force enable
print_success "Firewall configured (outbound connections allowed)"

print_step "Step 8: Create temp directory and set permissions"
sudo -u voice-retro mkdir -p $APP_DIR/temp
sudo chmod 755 $APP_DIR/temp
print_success "Temp directory created"

print_step "Step 9: Test configuration"
echo "Testing Python application..."
sudo -u voice-retro $APP_DIR/venv/bin/python -c "
import sys
sys.path.insert(0, '$APP_DIR')
from config import settings
print('✅ Configuration loaded successfully')
print(f'Bot token: {settings.bot_token[:10]}...')
print(f'OpenAI key: {settings.openai_api_key[:10]}...')
"

print_step "Step 10: Start service"
sudo systemctl start $SERVICE_NAME

# Wait a moment for service to start
sleep 3

# Check service status
if sudo systemctl is-active --quiet $SERVICE_NAME; then
    print_success "Voice Retro Bot service is running in polling mode"
else
    print_error "Service failed to start. Check logs with: sudo journalctl -u $SERVICE_NAME -f"
    exit 1
fi

print_step "Step 11: Test bot connectivity"
echo "Testing Telegram API connectivity..."
sudo -u voice-retro $APP_DIR/venv/bin/python -c "
import sys
sys.path.insert(0, '$APP_DIR')
import asyncio
from config import settings
from telegram import Bot

async def test_bot():
    bot = Bot(token=settings.bot_token)
    try:
        me = await bot.get_me()
        print(f'✅ Bot connected: @{me.username}')
        await bot.close()
    except Exception as e:
        print(f'❌ Bot connection failed: {e}')
        
asyncio.run(test_bot())
"

echo "
🎉 Deployment completed successfully!

📋 Bot Information:
- Mode: Polling (no webhooks needed)
- Architecture: Simplified, self-contained
- Bot: @voice_retro_bot
- Service: Running as systemd service

🧪 Test the bot:
1. Open Telegram and search for @voice_retro_bot
2. Send /start to begin
3. Send /retro to start a retrospective
4. Send voice messages to test transcription

📊 Service management commands:
- View logs: sudo journalctl -u $SERVICE_NAME -f
- Restart service: sudo systemctl restart $SERVICE_NAME
- Service status: sudo systemctl status $SERVICE_NAME
- Stop service: sudo systemctl stop $SERVICE_NAME

🔧 File locations:
- Application: $APP_DIR
- Service: /etc/systemd/system/$SERVICE_NAME.service
- Environment: $APP_DIR/.env

📡 Network: Bot uses outbound connections only (port 443 to api.telegram.org)
🔒 Security: No inbound ports needed, runs as dedicated user account

✨ Advantages of polling mode:
- Simpler setup and maintenance
- Works behind firewalls/NAT
- No external dependencies
- Self-contained architecture
- Perfect for personal/small-scale use
"