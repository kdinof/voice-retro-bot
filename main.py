"""Main application entry point for Voice Retro Bot."""

import asyncio
import logging
import sys
from contextlib import asynccontextmanager

import structlog
import uvicorn
from fastapi import FastAPI
from telegram import Bot

from config import settings
from api.webhooks import router as webhook_router
from services.telegram_service import TelegramService
from services.database_service import database_service


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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("Starting Voice Retro Bot application")
    
    # Initialize database
    await database_service.initialize()
    app.state.database_service = database_service
    
    # Initialize services
    telegram_service = TelegramService()
    app.state.telegram_service = telegram_service
    
    # Initialize conversation manager after database is ready
    from services.conversation_manager import ConversationManager
    conversation_manager = ConversationManager(database_service, telegram_service)
    telegram_service.conversation_manager = conversation_manager
    
    # Set up webhook if URL is provided
    if settings.telegram_webhook_url:
        await telegram_service.setup_webhook()
        logger.info("Webhook configured", url=settings.telegram_webhook_url)
    
    yield
    
    # Cleanup
    logger.info("Shutting down Voice Retro Bot application")
    if hasattr(app.state, 'telegram_service'):
        await app.state.telegram_service.cleanup()
    if hasattr(app.state, 'database_service'):
        await app.state.database_service.close()


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title="Voice Retro Bot",
        description="Telegram bot for voice-enabled daily retrospectives",
        version="1.0.0",
        lifespan=lifespan
    )
    
    # Include routers
    app.include_router(webhook_router, prefix="/api")
    
    return app


app = create_app()


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=settings.debug,
        log_level="info" if not settings.debug else "debug"
    )