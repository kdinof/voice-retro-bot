# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Telegram Bot for Daily Retrospectives** that uses voice transcription to guide users through structured daily reflection sessions. The project is **fully implemented** with a simplified, cost-effective architecture that preserves authentic user voice.

## Technology Stack

- **Language**: Python 3.9+
- **Bot Framework**: python-telegram-bot==20.8
- **Web Framework**: FastAPI + uvicorn for webhook handling
- **AI Services**: OpenAI Whisper API (speech-to-text only)
- **Database**: SQLite with async support (aiosqlite)
- **Audio Processing**: FFmpeg for OGG to MP3 conversion
- **Hosting**: Production server with systemd service (polling mode)

## Core Architecture

The bot implements a simplified voice-first conversational flow:

1. **Voice Processing Pipeline**: OGG download → FFmpeg conversion → Whisper transcription → Direct storage
2. **State Machine**: Multi-step conversation flow with progress tracking
3. **Document Generation**: Raw text storage with markdown templates
4. **Authentic Voice Preservation**: No AI processing, preserves user's natural language

## Key Requirements

### System Dependencies
- **FFmpeg**: Required for audio conversion from Telegram's OGG format to MP3
- **Python 3.13+**: For async/await patterns and modern Python features

### Environment Variables
- `BOT_TOKEN`: Telegram bot token (configured in .env)
- `OPENAI_API_KEY`: OpenAI API key for Whisper transcription
- `TELEGRAM_WEBHOOK_URL`: Production webhook URL for Telegram integration

## Development Commands

```bash
# Local development setup
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt

# Install system dependencies
# macOS: brew install ffmpeg
# Ubuntu: sudo apt-get install ffmpeg

# Run the bot locally (polling mode)
python local_bot.py

# Run the bot in production (webhook mode)
python main.py

# Testing (planned)
python -m pytest tests/
python -m pytest tests/integration/
```

## Implementation Architecture

### Voice Processing Flow
1. **Download**: Receive OGG voice message from Telegram
2. **Convert**: Async OGG → MP3 conversion with FFmpeg subprocess
3. **Transcribe**: Send MP3 to Whisper API for Russian language transcription
4. **Store**: Save raw transcription directly to database (preserves authentic voice)
5. **Cleanup**: Delete temporary files with proper error handling

### Data Models
```python
User: telegram_id, username, created_at, timezone
Retro: user_id, date, energy_level, mood, wins_text, learnings_text, next_actions_text, mits_text, experiment_text
ConversationState: user_id, current_step, retro_id, updated_at
```

### Performance Targets
- Bot response time: < 2 seconds
- Voice transcription: < 5 seconds
- Support for 100 concurrent users
- Audio processing timeout: 30 seconds max

## Error Handling Strategy

- **Voice processing failures**: User-friendly messages with fallback to text input
- **API timeouts**: Retry logic with exponential backoff
- **File cleanup**: Automatic temporary file deletion in all scenarios
- **Progress indication**: Real-time updates during voice processing

## Security Considerations

- **Audio files**: Immediate deletion after transcription
- **Temporary files**: Automatic cleanup with try/finally blocks
- **Webhook verification**: Telegram signature validation
- **Data retention**: 90-day limit with /deletedata command

## Implementation Status

✅ **Completed**: All phases implemented with simplified architecture
- Core voice processing pipeline (Whisper only)
- Multi-step conversation state management
- Raw text storage with authentic voice preservation
- Markdown document generation
- Production deployment configuration

## Key Files

### Production Deployment
- `local_bot.py`: Production bot with polling mode
- `deploy.sh`: Simplified deployment script
- `voice-retro.service`: Systemd service configuration
- `.env.production`: Production environment variables
- `DEPLOYMENT.md`: Complete deployment guide

### Core Application
- `services/voice_processor.py`: FFmpeg and Whisper integration
- `services/conversation_manager.py`: State machine for retro flow
- `models/`: Database models and data access layer
- `requirements.txt`: Python dependencies
- `config.py`: Configuration and environment management

## Russian Language Support

The bot is specifically designed for Russian language users with:
- Whisper API optimized for Russian transcription
- GPT prompts that preserve Russian language in responses
- User interface messages in Russian
- Cultural context for daily retrospective practices