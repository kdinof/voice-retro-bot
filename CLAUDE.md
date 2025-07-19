# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Telegram Bot for Daily Retrospectives** that uses voice transcription to guide users through structured daily reflection sessions. The project is currently in the **planning phase** with comprehensive documentation but no implementation code yet.

## Technology Stack (Planned)

- **Language**: Python 3.13+
- **Bot Framework**: python-telegram-bot==20.8
- **AI Services**: OpenAI Whisper API (speech-to-text), GPT-4o-mini (text processing)
- **Database**: SQLite (development), PostgreSQL (production consideration)
- **Audio Processing**: FFmpeg for OGG to MP3 conversion
- **Hosting**: Digital Ocean Droplet with PM2/systemd

## Core Architecture

The bot implements a voice-first conversational flow:

1. **Voice Processing Pipeline**: OGG download → FFmpeg conversion → Whisper transcription → GPT text cleaning
2. **State Machine**: Multi-step conversation flow with progress tracking
3. **Document Generation**: Structured retrospective templates in markdown format

## Key Requirements

### System Dependencies
- **FFmpeg**: Required for audio conversion from Telegram's OGG format to MP3
- **Python 3.13+**: For async/await patterns and modern Python features

### Environment Variables
- `BOT_TOKEN`: Telegram bot token (configured in .env)
- `OPENAI_API_KEY`: OpenAI API key for Whisper and GPT services

## Development Commands (When Implemented)

Since no code exists yet, these are the planned commands based on the technical specification:

```bash
# Local development setup
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt

# Install system dependencies
# macOS: brew install ffmpeg
# Ubuntu: sudo apt-get install ffmpeg

# Run the bot
python bot.py

# Testing (planned)
python -m pytest tests/
python -m pytest tests/integration/
```

## Implementation Architecture

### Voice Processing Flow
1. **Download**: Receive OGG voice message from Telegram
2. **Convert**: Async OGG → MP3 conversion with FFmpeg subprocess
3. **Transcribe**: Send MP3 to Whisper API for Russian language transcription
4. **Clean**: Process raw transcription with GPT-4o-mini to fix grammar/structure
5. **Store**: Save to conversation state for multi-step flow
6. **Cleanup**: Delete temporary files with proper error handling

### Data Models (Planned)
```python
User: telegram_id, username, created_at, timezone
Retro: user_id, date, energy_level, mood, wins, learnings, next_actions, mits, experiment
ConversationState: user_id, current_question, temp_data, updated_at
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

## Implementation Phases

1. **Phase 1**: Core voice pipeline with basic bot setup
2. **Phase 2**: Multi-step conversation state management
3. **Phase 3**: Document generation and error handling polish

## Key Files to Create

When implementation begins, the main files will be:
- `bot.py`: Main bot application and webhook handling
- `voice_processor.py`: FFmpeg and Whisper integration
- `conversation_manager.py`: State machine for retro flow
- `models.py`: Database models and data access
- `requirements.txt`: Python dependencies
- `config.py`: Configuration and environment management

## Russian Language Support

The bot is specifically designed for Russian language users with:
- Whisper API optimized for Russian transcription
- GPT prompts that preserve Russian language in responses
- User interface messages in Russian
- Cultural context for daily retrospective practices