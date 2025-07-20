# Voice Retro Bot - Production Deployment Guide

## Server Information
- **IP Address**: 142.93.209.251
- **Bot Name**: @voice_retro_bot
- **Architecture**: Simplified voice transcription (no AI processing)

## Deployment Steps

### 1. Upload Code to Server

```bash
# Option A: Clone from GitHub (recommended)
ssh root@142.93.209.251
git clone https://github.com/yourusername/voice-retro.git /opt/voice-retro-source
cd /opt/voice-retro-source

# Option B: Upload via SCP
scp -r /Users/kdinof/Desktop/Cursor\ Projets/voice-retro root@142.93.209.251:/opt/voice-retro-source
```

### 2. Run Deployment Script

```bash
# On the server
cd /opt/voice-retro-source
chmod +x deploy.sh
./deploy.sh
```

### 3. Configure Environment Variables

```bash
# Edit production environment
sudo nano /opt/voice-retro/.env

# Set a secure webhook secret (generate random string)
TELEGRAM_WEBHOOK_SECRET=$(openssl rand -hex 32)
```

### 4. Set Up Telegram Webhook

```bash
# Replace <YOUR_WEBHOOK_SECRET> with the secret from step 3
curl -X POST "https://api.telegram.org/bot7649337954:AAG3M44jWdyUv9c3Hv199op0QuhCveLmt58/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "http://142.93.209.251/api/webhooks/telegram",
    "secret_token": "<YOUR_WEBHOOK_SECRET>",
    "allowed_updates": ["message", "callback_query"]
  }'
```

### 5. Verify Webhook Status

```bash
# Check webhook configuration
curl "https://api.telegram.org/bot7649337954:AAG3M44jWdyUv9c3Hv199op0QuhCveLmt58/getWebhookInfo"
```

**Expected Response:**
```json
{
  "ok": true,
  "result": {
    "url": "http://142.93.209.251/api/webhooks/telegram",
    "has_custom_certificate": false,
    "pending_update_count": 0,
    "last_error_date": 0,
    "max_connections": 40,
    "allowed_updates": ["message", "callback_query"]
  }
}
```

## Testing the Bot

### 1. Service Health Check

```bash
# Check service status
sudo systemctl status voice-retro

# View live logs
sudo journalctl -u voice-retro -f

# Test webhook endpoint
curl -X GET http://142.93.209.251/api/webhooks/telegram
# Should return 405 Method Not Allowed (this is expected)
```

### 2. Bot Functionality Test

1. **Open Telegram** and search for `@voice_retro_bot`
2. **Send `/start`** - should receive welcome message
3. **Send `/retro`** - should start retrospective conversation
4. **Send voice message** - should transcribe and save to database
5. **Complete full retro** - should generate markdown report

### 3. Voice Processing Test

```bash
# Monitor voice processing in logs
sudo journalctl -u voice-retro -f | grep -i "voice\|whisper\|transcrib"
```

## Troubleshooting

### Common Issues

**Service won't start:**
```bash
# Check detailed logs
sudo journalctl -u voice-retro --no-pager -l

# Check environment file
sudo -u voice-retro cat /opt/voice-retro/.env

# Test Python imports
sudo -u voice-retro /opt/voice-retro/venv/bin/python -c "
import sys; sys.path.insert(0, '/opt/voice-retro')
from config import settings
print('Config loaded successfully')
"
```

**Webhook not receiving updates:**
```bash
# Check nginx logs
sudo tail -f /var/log/nginx/voice-retro.access.log
sudo tail -f /var/log/nginx/voice-retro.error.log

# Test webhook endpoint directly
curl -X POST http://142.93.209.251/api/webhooks/telegram \
  -H "Content-Type: application/json" \
  -d '{"test": "message"}'
```

**Voice processing fails:**
```bash
# Check FFmpeg installation
ffmpeg -version

# Check OpenAI API key
sudo -u voice-retro /opt/voice-retro/venv/bin/python -c "
import openai
import os
os.environ['OPENAI_API_KEY'] = 'your-key-here'
client = openai.OpenAI()
print('OpenAI client initialized successfully')
"
```

### Log Locations

- **Application logs**: `sudo journalctl -u voice-retro -f`
- **Nginx access**: `/var/log/nginx/voice-retro.access.log`
- **Nginx errors**: `/var/log/nginx/voice-retro.error.log`
- **System logs**: `/var/log/syslog`

### File Permissions

```bash
# Fix permissions if needed
sudo chown -R voice-retro:voice-retro /opt/voice-retro
sudo chmod 600 /opt/voice-retro/.env
sudo chmod 755 /opt/voice-retro/temp
```

## Maintenance Commands

### Service Management
```bash
# Restart service
sudo systemctl restart voice-retro

# Stop service
sudo systemctl stop voice-retro

# View status
sudo systemctl status voice-retro
```

### Database Management
```bash
# Backup database
sudo cp /opt/voice-retro/voice_retro.db /opt/voice-retro/backups/voice_retro_$(date +%Y%m%d_%H%M%S).db

# Reset database (WARNING: deletes all data)
sudo -u voice-retro rm /opt/voice-retro/voice_retro.db
sudo systemctl restart voice-retro
```

### Updates
```bash
# Pull latest code
cd /opt/voice-retro
sudo -u voice-retro git pull

# Restart service
sudo systemctl restart voice-retro
```

## Security Notes

- **Environment file** (`/opt/voice-retro/.env`) contains sensitive keys
- **Webhook secret** should be a strong random string
- **Database file** should be backed up regularly
- **Log files** may contain user messages (handle according to privacy policy)

## Performance Monitoring

```bash
# Monitor resource usage
htop

# Check disk space
df -h

# Monitor active connections
sudo netstat -tulpn | grep :8000

# Check memory usage
free -h
```

## Success Indicators

✅ **Service running**: `sudo systemctl is-active voice-retro` returns `active`  
✅ **Nginx running**: `sudo systemctl is-active nginx` returns `active`  
✅ **Webhook set**: `getWebhookInfo` shows correct URL  
✅ **Bot responding**: `/start` command works in Telegram  
✅ **Voice processing**: Voice messages are transcribed and saved  
✅ **Logs clean**: No errors in service logs  