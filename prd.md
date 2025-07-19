 Product Requirements Document: Daily Retro Telegram Bot

## 1. Executive Summary
A personal hobby project: Telegram bot that leverages voice message transcription via Whisper API to guide users through structured daily retrospectives, capturing energy levels, mood, wins, learnings, and next actions in a predefined template format for consistent self-reflection and improvement tracking.

## 2. Problem Statement & Success Measures

**Core Problem:** Users struggle to maintain consistent daily reflection habits due to friction in documenting thoughts and the cognitive load of structuring retrospectives.

**Success Metrics:**
There will be no success metrics yet, because the project is for personal use.

## 3. Goals & Non-Goals

**Goals:**
- Minimize friction for daily retrospective capture
- Provide structured guidance through conversational UX
- Generate formatted documents for future reference
- Support voice-first interaction with text fallback
- Process voice messages efficiently with real-time progress updates

**Non-Goals:**
- Team retrospectives or multi-user features
- Analytics dashboards or trend visualization
- Integration with external productivity tools
- Mobile app development
- Multiple transcription type options (only retro format needed)

## 4. Target Personas & JTBD

**Primary Persona: Busy Professional**
- Age 25-40, remote/hybrid worker
- Values self-improvement and reflection
- Time-constrained, prefers quick interactions
- Comfortable with voice messages
- Russian is a native language

**Jobs to be Done:**
1. "Help me reflect on my day without opening another app"
2. "Make daily journaling feel conversational, not like homework"
3. "Create a searchable record of my growth over time"

## 5. User Stories (Must-Have Only)

### Story 1: Bot Onboarding
**As a** new user  
**I want to** start the bot with /start command  
**So that** I receive welcome instructions and begin my first retro  
**Acceptance Criteria:**
- Bot responds within 2 seconds
- Clear explanation of voice message usage
- Option to see example retro
**Priority:** Must Have

### Story 2: Guided Retro Flow
**As a** user  
**I want to** answer prompted questions sequentially  
**So that** I complete all retro sections without thinking about structure  
**Acceptance Criteria:**
- Questions appear one at a time
- Voice messages auto-transcribed with progress indicators
- Real-time transcription status updates shown to user
- Text input also supported
- Progress indicator shown for overall retro completion
**Priority:** Must Have

### Story 3: Voice Transcription
**As a** user  
**I want to** speak my responses naturally in Russian language  
**So that** friction is minimized  
**Acceptance Criteria:**
- Whisper API processes audio within 5 seconds
- 90%+ accuracy for Russian
- Audio conversion from OGG to MP3 handled automatically
- Progress messages during processing ("Processing voice message...", "Converting audio...", "Transcribing...")
- Error handling for failed transcriptions with user-friendly messages
**Priority:** Must Have

### Story 4: Document Generation
**As a** user  
**I want to** receive my completed retro as formatted text  
**So that** I can save/share it externally  
**Acceptance Criteria:**
- Markdown format matching template
- Copy-to-clipboard button
- Option to edit before finalizing
**Priority:** Must Have

## 6. Key Flows & UX Notes

**Main Flow:**
1. User sends /start or /retro command
2. Bot: "How's your energy today? (1-5)" + voice record hint
3. User sends voice/text response
4. If voice: Bot shows "🎤 Processing your voice message..." → "🎤 Converting audio format..." → "🎤 Transcribing..."
5. Bot confirms transcription, asks for mood (with emoji options)
6. User selects mood + explains via voice/text
7. Bot cycles through: Wins → Learnings → Next Actions → Tomorrow's MITs → Experiments
8. Bot generates final document, sends as message
9. User can /edit specific sections or /done to finish

**UX Principles:**
- One question at a time (reduce cognitive load)
- Always show transcribed text for confirmation
- Real-time progress updates during voice processing
- Quick emoji reactions for common responses
- Skip option for any section
- Clean transcription output without AI introductions

## 7. Technical Architecture

**Voice Processing Pipeline:**
1. **Download**: Voice message received as OGG file from Telegram
2. **Convert**: Asynchronous conversion OGG → MP3 using FFmpeg subprocess
3. **Transcribe**: MP3 sent to OpenAI Whisper API
4. **Clean**: GPT-4o-mini processes raw transcription with retro-specific prompt
5. **Store**: Cleaned text saved to conversation state
6. **Cleanup**: Temporary files deleted after processing

**Key Technical Components:**
- Asynchronous audio conversion using `asyncio.create_subprocess_exec`
- Temporary file management with proper cleanup in all scenarios
- Error handling at each pipeline stage with fallback options
- Progress messaging throughout the pipeline

## 8. Feature List & Implementation Details

**Functional Features:**
- Telegram bot webhook handling
- Voice message download/processing with progress updates
- Whisper API integration for Russian transcription
- GPT integration for text cleaning and structuring
- State management per user for multi-step conversations
- Template-based document generation
- Asynchronous audio conversion (OGG to MP3)
- Comprehensive error handling with user-friendly messages

**Audio Processing Specifications:**
- Input: OGG format (Telegram default)
- Conversion: FFmpeg with parameters:
  - Output format: MP3
  - Audio codec: libmp3lame
  - Bitrate: 192k
  - Sample rate: 44100Hz
- Temporary file cleanup after processing or on error

**Prompt Engineering:**
- System prompt: "You are a helpful assistant that structures text in a clear and organized way for daily retrospectives."
- User prompt template must include:
  - Instructions to fix grammar, spelling, punctuation
  - Remove speech artifacts (um, uh, false starts)
  - Maintain original language (Russian)
  - Never add introductory phrases
  - Structure for retro context

## 9. Data Model & External Integrations

**Core Entities:**
```python
User
- telegram_id (primary key)
- username
- created_at
- timezone

Retro
- id
- user_id (foreign key)
- date
- energy_level (1-5)
- mood
- mood_explanation
- wins (array)
- learnings (array)
- next_actions (array)
- mits (array)
- experiment (json)
- completed_at

ConversationState
- user_id (foreign key)
- current_question
- temp_data (json)
- updated_at
```

**External Integrations:**
- Telegram Bot API (webhooks)
- OpenAI Whisper API (model: "whisper-1")
- OpenAI Chat Completions API (model: "gpt-4o-mini")
- PostgreSQL or SQLite (data storage)

## 10. Technical Stack & Dependencies

**Fast Path (Prototype):**
- **Language:** Python 3.13+
- **Bot Framework:** python-telegram-bot==20.8
- **AI/ML:** openai>=1.12.0
- **Audio Processing:** FFmpeg (system dependency)
- **Database:** SQLite (file-based)
- **Hosting:** Digital Ocean Droplet
- **Process Manager:** PM2 or systemd

**Required Python Packages:**
```
python-telegram-bot==20.8
openai>=1.12.0
python-dotenv==1.0.1
asyncio==3.4.3
```

**System Dependencies:**
- FFmpeg (required for audio conversion)

## 11. Error Handling Strategy

**Voice Processing Errors:**
- Audio conversion failure → "❌ Error converting audio. Please try again."
- Transcription failure → Return raw transcription with note
- API timeout → "Processing is taking longer than usual. Please try again."
- File not found → Prompt user to send new voice message

**General Error Handling:**
- All errors logged with full context
- User-friendly error messages (no technical details exposed)
- Automatic cleanup of temporary files in all error scenarios
- Fallback to text input if voice consistently fails

## 12. Privacy, Security & Compliance

- **Data Retention:** User content stored max 90 days unless exported
- **Audio Files:** Delete immediately after transcription (within same request)
- **Temporary Files:** Automatic cleanup with try/finally blocks
- **Encryption:** TLS for API calls; consider at-rest encryption for database
- **GDPR:** Implement /deletedata command for full account removal
- **PII Handling:** No automatic PII detection; rely on user discretion

## 13. Development & Deployment

**Local Development Setup:**
```bash
# Install system dependencies
# macOS: brew install ffmpeg
# Ubuntu: sudo apt-get install ffmpeg

# Python setup
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Environment variables (.env file)
OPENAI_API_KEY=your_key_here
TELEGRAM_BOT_TOKEN=your_token_here

# Run bot
python bot.py
```

**Production Deployment (Digital Ocean VPS):**
- Use PM2 or systemd for process management
- Set up logging to files with rotation
- Configure firewall (UFW)
- Use non-root user for security
- Set up automatic restarts on failure

## 14. Implementation Priority

1. **Phase 1 - Core Voice Pipeline**
   - Basic bot setup with /start command
   - Voice message reception and conversion
   - Whisper transcription integration
   - Simple text response

2. **Phase 2 - Retro Flow**
   - Multi-step conversation state management
   - Question prompts and response collection
   - GPT text cleaning integration
   - Progress indicators

3. **Phase 3 - Polish**
   - Document generation with template
   - Edit functionality
   - Error handling improvements
   - Performance optimizations

## 15. Appendix

**Template Structure Reference:**
- Energy: Numeric scale 1-5
- Mood: Emoji + text explanation
- Sections: Wins, Learnings, Next Actions, MITs, Experiments

**FFmpeg Conversion Command:**
```python
ffmpeg_cmd = [
    'ffmpeg',
    '-i', input_path,      # Input OGG file
    '-f', 'mp3',          # Output format
    '-acodec', 'libmp3lame',  # Audio codec
    '-ab', '192k',        # Bitrate
    '-ar', '44100',       # Sample rate
    '-y',                 # Overwrite output
    output_path
]
```

**Related Documentation:**
- [Telegram Bot API Docs](https://core.telegram.org/bots/api)
- [OpenAI Whisper API](https://platform.openai.com/docs/guides/speech-to-text)
- [python-telegram-bot Documentation](https://docs.python-telegram-bot.org/)

**Glossary:**
- MIT: Most Important Tasks
- Retro: Retrospective (daily reflection session)
- Whisper: OpenAI's speech recognition model
- OGG: Audio format used by Telegram for voice messages