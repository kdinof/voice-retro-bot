#!/usr/bin/env python3
"""Voice Retro Bot - Main application with polling mode."""

import asyncio
import logging
import sys
from typing import Optional

import structlog
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, CallbackQueryHandler, filters

from config import settings
from services.telegram_service import TelegramService
from services.database_service import database_service
from services.conversation_manager import ConversationManager
from services.scheduler_service import SchedulerService


# Configure structured logging
logging.basicConfig(
    format="%(message)s",
    stream=sys.stdout,
    level=logging.INFO if not settings.debug else logging.DEBUG,
)

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


class VoiceRetroBotApplication:
    """Voice Retro Bot main application with polling mode."""
    
    def __init__(self):
        self.telegram_service: Optional[TelegramService] = None
        self.conversation_manager: Optional[ConversationManager] = None
        self.scheduler_service: Optional[SchedulerService] = None
        self.application: Optional[Application] = None
    
    async def initialize(self):
        """Initialize bot services."""
        logger.info("🚀 Initializing Voice Retro Bot (Polling Mode)")
        
        # Initialize database
        await database_service.initialize()
        logger.info("✅ Database initialized")
        
        # Initialize services
        self.telegram_service = TelegramService()
        logger.info("✅ Telegram service initialized")
        
        # Setup bot commands
        await self.telegram_service.setup_bot_commands()
        logger.info("✅ Bot commands configured")
        
        # Initialize conversation manager
        self.conversation_manager = ConversationManager(database_service, self.telegram_service)
        self.telegram_service.conversation_manager = self.conversation_manager
        logger.info("✅ Conversation manager initialized")
        
        # Initialize scheduler service
        self.scheduler_service = SchedulerService(database_service, self.telegram_service)
        logger.info("✅ Scheduler service initialized")
        
        # Create telegram application with polling
        self.application = Application.builder().token(settings.bot_token).build()
        
        # Add handlers
        self.application.add_handler(MessageHandler(filters.ALL, self._handle_message))
        self.application.add_handler(CallbackQueryHandler(self._handle_callback_query))
        
        logger.info("✅ Bot handlers configured")
    
    async def _handle_message(self, update: Update, context):
        """Handle incoming messages."""
        try:
            await self.telegram_service.handle_update(update)
        except Exception as e:
            logger.error("Error handling message", error=str(e), exc_info=True)
    
    async def _handle_callback_query(self, update: Update, context):
        """Handle callback queries."""
        try:
            await self.telegram_service.handle_update(update)
        except Exception as e:
            logger.error("Error handling callback query", error=str(e), exc_info=True)
    
    async def start_polling(self):
        """Start bot with polling."""
        logger.info("🎯 Starting bot with polling...")
        logger.info("📱 Bot: @voice_retro_bot")
        logger.info("🔄 Mode: Polling (Production)")
        logger.info("🗄️ Database: SQLite")
        logger.info("🎤 Voice: FFmpeg + Whisper (simplified)")
        logger.info("")
        logger.info("✅ Bot is ready! Send /start to @voice_retro_bot in Telegram")
        logger.info("Press Ctrl+C to stop")
        
        # Start polling
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling(drop_pending_updates=True)
        
        # Start scheduler service for daily reminders
        if self.scheduler_service:
            await self.scheduler_service.start()
            logger.info("📅 Scheduler service started")
        
        # Keep running
        try:
            await asyncio.Future()  # Run forever
        except KeyboardInterrupt:
            logger.info("🛑 Stopping bot...")
        finally:
            await self.cleanup()
    
    async def cleanup(self):
        """Cleanup resources."""
        logger.info("🧹 Cleaning up...")
        
        # Stop scheduler service first
        if self.scheduler_service:
            await self.scheduler_service.stop()
            logger.info("📅 Scheduler service stopped")
        
        if self.application:
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
        
        if self.telegram_service:
            await self.telegram_service.cleanup()
        
        await database_service.close()
        logger.info("✅ Cleanup complete")


async def main():
    """Main entry point."""
    try:
        # Test configuration (production-safe logging)
        logger.info("🔧 Testing configuration...")
        logger.info(f"Bot token: {settings.bot_token[:10]}..." if settings.bot_token else "❌ Bot token missing")
        logger.info(f"OpenAI key: {settings.openai_api_key[:10]}..." if settings.openai_api_key else "❌ OpenAI key missing")
        
        # Create and start bot
        bot_app = VoiceRetroBotApplication()
        await bot_app.initialize()
        await bot_app.start_polling()
        
    except KeyboardInterrupt:
        logger.info("👋 Bot stopped by user")
    except Exception as e:
        logger.error("💥 Bot crashed", error=str(e), exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())