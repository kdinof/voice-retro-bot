# Voice Retro Bot 🎤

A Telegram bot for voice-enabled daily retrospectives that leverages OpenAI Whisper for speech-to-text transcription and guides users through structured self-reflection sessions.

## 🚀 Features

- **Voice-First Interaction**: Send voice messages in Russian for natural retrospectives
- **Structured Flow**: Guided questions for energy, mood, wins, learnings, and next actions
- **Real-Time Processing**: Progress indicators during voice transcription
- **Markdown Export**: Beautiful formatted retrospective documents
- **State Management**: Multi-step conversation flow with session handling
- **Database Persistence**: SQLite storage with migration support

## 🏗️ Architecture

- **FastAPI**: Async web framework for webhook handling
- **SQLAlchemy**: Database ORM with async support
- **Alembic**: Database migrations
- **OpenAI Whisper**: Speech-to-text transcription
- **OpenAI GPT-4o-mini**: Text cleaning and processing
- **FFmpeg**: Audio format conversion (OGG → MP3)

## 📁 Project Structure

```
voice-retro/
├── api/                    # FastAPI routes and webhooks
├── models/                 # SQLAlchemy database models
├── repositories/           # Data access layer with repository pattern
├── services/              # Business logic services
├── alembic/               # Database migrations
├── utils/                 # Utility functions
├── config.py              # Application configuration
├── main.py                # Application entry point
└── requirements.txt       # Python dependencies
```

## 🛠️ Setup

### Prerequisites

- Python 3.9+
- FFmpeg (for audio processing)
- Telegram Bot Token
- OpenAI API Key

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd voice-retro
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

4. **Run database migrations**
   ```bash
   python -m alembic upgrade head
   ```

5. **Start the bot**
   ```bash
   python main.py
   ```

## 🔧 Configuration

Required environment variables:

```bash
BOT_TOKEN=your_telegram_bot_token
OPENAI_API_KEY=your_openai_api_key
TELEGRAM_WEBHOOK_URL=https://your-domain.com  # Optional for webhooks
```

## 🎯 Usage

1. Start a conversation with your bot on Telegram
2. Send `/start` to see the welcome message
3. Send `/retro` to begin a daily retrospective
4. Follow the guided prompts with voice or text responses
5. Receive your formatted retrospective document

## 📊 Database Schema

- **Users**: Telegram user information and preferences
- **Retros**: Daily retrospective data with JSON fields
- **ConversationStates**: Multi-step conversation flow management

## 🧪 Development

### Running Tests

```bash
python test_setup.py        # Basic configuration test
python test_database.py     # Database operations test
python test_integration.py  # Full integration test
```

### Database Migrations

```bash
# Create new migration
python -m alembic revision --autogenerate -m "Description"

# Apply migrations
python -m alembic upgrade head
```

## 🚦 Project Status

- ✅ **Phase 1**: Bot Foundation & Architecture Setup
- ✅ **Phase 2**: Database Schema & Data Layer  
- 🚧 **Phase 3**: Voice Processing Pipeline (Next)
- ⏳ **Phase 4**: GPT Integration & Text Processing
- ⏳ **Phase 5**: Conversation State Management

## 🤖 Bot Commands

- `/start` - Welcome message and instructions
- `/retro` - Start a new daily retrospective
- `/help` - Show help and usage information

## 🛡️ Security

- Webhook signature verification
- Input validation and sanitization
- Secure file handling with automatic cleanup
- No sensitive data logging

## 📝 Contributing

This is a personal hobby project, but suggestions and improvements are welcome!

## 📄 License

MIT License - feel free to use and modify for your own projects.

---

Built with ❤️ for better daily reflection habits