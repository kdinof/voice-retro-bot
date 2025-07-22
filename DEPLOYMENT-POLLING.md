# Voice Retro Bot - Simplified Polling Deployment Guide

## Overview
This guide covers deploying the Voice Retro Bot using **polling mode** instead of webhooks for simplified setup and maintenance.

## Architecture: Polling vs Webhooks

### **Polling Mode (This Deployment)** ✅
- **Simpler setup** - No nginx, no webhooks, no public ports
- **Self-contained** - Bot connects outbound to Telegram
- **Easier maintenance** - Fewer moving parts
- **Works everywhere** - Behind firewalls, NAT, personal servers
- **Perfect for personal use** - Single user, low traffic

### **Webhook Mode** (Not Used)
- More complex setup requiring nginx, SSL, public IP
- Better for high-traffic, enterprise bots
- Instant message delivery vs 1-3 second polling delay

## Server Information
- **IP Address**: 142.93.209.251
- **Bot Name**: @voice_retro_bot
- **Architecture**: Simplified polling with direct Telegram connection

## Quick Deployment

### 1. Upload Code to Server

```bash
# SSH to your server
ssh root@142.93.209.251

# Create project directory
mkdir -p /opt/voice-retro
cd /opt/voice-retro

# Clone from GitHub (replace with your repo URL)
git clone https://github.com/kdinof/voice-retro-bot.git .

# Or upload manually via SCP:
# scp -r /path/to/voice-retro/* root@142.93.209.251:/opt/voice-retro/
```

### 2. Run Simplified Deployment

```bash
# Create a regular user (for security)
adduser deploy
usermod -aG sudo deploy

# Switch to deploy user
su - deploy
cd /opt/voice-retro

# Run the simplified deployment script
chmod +x deploy-polling.sh
./deploy-polling.sh
```

## What the Deployment Script Does

✅ **System Updates** - Updates Ubuntu packages  
✅ **Dependencies** - Installs Python 3, FFmpeg, Git  
✅ **User Creation** - Creates dedicated `voice-retro` system user  
✅ **Python Environment** - Sets up virtual environment with dependencies  
✅ **Service Configuration** - Configures systemd for automatic startup  
✅ **Firewall Setup** - Basic security (outbound connections only)  
✅ **Testing** - Verifies bot connectivity and configuration  

**NOT Included** (vs webhook deployment):
- ❌ Nginx installation/configuration
- ❌ Webhook URL setup
- ❌ SSL certificates
- ❌ Inbound port configuration
- ❌ Reverse proxy setup

## Service Management

### Basic Commands
```bash
# View bot status
sudo systemctl status voice-retro

# Start/stop/restart bot
sudo systemctl start voice-retro
sudo systemctl stop voice-retro
sudo systemctl restart voice-retro

# View live logs
sudo journalctl -u voice-retro -f

# View recent logs
sudo journalctl -u voice-retro --since "1 hour ago"
```

### Configuration Files
- **Service**: `/etc/systemd/system/voice-retro.service`
- **Environment**: `/opt/voice-retro/.env`
- **Application**: `/opt/voice-retro/`
- **Logs**: `sudo journalctl -u voice-retro`

## Testing the Bot

### 1. Check Service Status
```bash
# Should show "active (running)"
sudo systemctl status voice-retro

# Should show recent startup messages
sudo journalctl -u voice-retro --since "5 minutes ago"
```

### 2. Test Bot Functionality
1. **Open Telegram** and search for `@voice_retro_bot`
2. **Send `/start`** - should receive welcome message
3. **Send `/retro`** - should start retrospective conversation
4. **Send voice message** - should transcribe and save to database
5. **Complete retro** - should generate markdown report

### 3. Monitor Voice Processing
```bash
# Watch for voice processing in logs
sudo journalctl -u voice-retro -f | grep -i "voice\|transcrib\|whisper"
```

## Troubleshooting

### Service Won't Start
```bash
# Check detailed error logs
sudo journalctl -u voice-retro --no-pager -l

# Check if environment file exists
ls -la /opt/voice-retro/.env

# Test Python environment
sudo -u voice-retro /opt/voice-retro/venv/bin/python -c "
import sys; sys.path.insert(0, '/opt/voice-retro')
from config import settings
print('✅ Config loads successfully')
"
```

### Bot Not Responding
```bash
# Check network connectivity
curl -s https://api.telegram.org/bot$(grep BOT_TOKEN /opt/voice-retro/.env | cut -d= -f2)/getMe

# Check if bot token is valid
sudo -u voice-retro /opt/voice-retro/venv/bin/python -c "
import sys; sys.path.insert(0, '/opt/voice-retro')
import asyncio
from telegram import Bot
from config import settings

async def test():
    bot = Bot(settings.bot_token)
    try:
        me = await bot.get_me()
        print(f'✅ Bot connected: @{me.username}')
    except Exception as e:
        print(f'❌ Error: {e}')
    finally:
        await bot.close()

asyncio.run(test())
"
```

### Voice Processing Issues
```bash
# Check FFmpeg
ffmpeg -version

# Check OpenAI API key
sudo -u voice-retro /opt/voice-retro/venv/bin/python -c "
import openai
import os
os.environ['OPENAI_API_KEY'] = '$(grep OPENAI_API_KEY /opt/voice-retro/.env | cut -d= -f2)'
try:
    client = openai.OpenAI()
    print('✅ OpenAI client initialized')
except Exception as e:
    print(f'❌ OpenAI error: {e}')
"
```

### Database Issues
```bash
# Check database file
ls -la /opt/voice-retro/voice_retro.db

# Reset database (WARNING: deletes all data)
sudo systemctl stop voice-retro
sudo -u voice-retro rm -f /opt/voice-retro/voice_retro.db
sudo systemctl start voice-retro
```

## Maintenance

### Regular Tasks
```bash
# View disk usage
df -h /opt/voice-retro

# Clean old log files (if needed)
sudo journalctl --vacuum-time=30d

# Update application (if you push new code)
cd /opt/voice-retro
sudo -u voice-retro git pull
sudo systemctl restart voice-retro
```

### Backup Database
```bash
# Create backup
sudo cp /opt/voice-retro/voice_retro.db /opt/voice-retro/backups/voice_retro_$(date +%Y%m%d_%H%M%S).db

# Create backups directory first
sudo -u voice-retro mkdir -p /opt/voice-retro/backups
```

## Security

### What's Secure ✅
- **Dedicated user account** - Bot runs as `voice-retro` user, not root
- **File permissions** - Environment file readable only by bot user
- **Outbound only** - No inbound ports, firewall blocks incoming
- **System isolation** - Bot isolated from other system processes

### Security Notes
- **Environment file** contains API keys - keep permissions restrictive
- **Database file** may contain user messages - backup securely
- **Logs** may contain user data - consider log rotation/cleanup

## Performance

### Resource Usage (Expected)
- **CPU**: Very low (polling is lightweight)
- **Memory**: ~50-100MB for Python + dependencies
- **Network**: ~1-2 API calls/second for polling
- **Storage**: Minimal (SQLite database grows slowly)

### Optimization
- **Polling interval**: Default 1-3 seconds (configurable in code)
- **Log levels**: Reduce to WARNING/ERROR in production if needed
- **Database**: SQLite is fine for personal use, PostgreSQL for scale

## Success Indicators

✅ **Service running**: `sudo systemctl is-active voice-retro` shows `active`  
✅ **Bot responsive**: `/start` command works in Telegram  
✅ **Voice processing**: Voice messages transcribed and saved  
✅ **Logs clean**: No errors in `sudo journalctl -u voice-retro`  
✅ **Polling active**: Logs show periodic polling activity  

## Advantages of This Setup

🎯 **Simplicity** - Single systemd service, no web server complexity  
🔒 **Security** - No inbound ports, works behind firewall  
🛠️ **Maintenance** - Easy to understand, debug, and maintain  
💰 **Cost-effective** - Minimal server resources required  
🚀 **Reliability** - Fewer failure points than webhook setup  

Perfect for personal retrospective bot with 1-10 users! 🎉