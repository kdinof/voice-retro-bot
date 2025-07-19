"""Webhook endpoints for Telegram bot."""

import hmac
import hashlib
from typing import Dict, Any

import structlog
from fastapi import APIRouter, Request, HTTPException, Depends
from telegram import Update

from config import settings
from services.telegram_service import TelegramService
from services.database_service import DatabaseService


logger = structlog.get_logger()
router = APIRouter()


def verify_telegram_webhook(request: Request) -> bool:
    """Verify Telegram webhook signature."""
    if not settings.telegram_webhook_secret:
        return True  # Skip verification if no secret is set
    
    signature = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    return hmac.compare_digest(signature, settings.telegram_webhook_secret)


async def get_telegram_service(request: Request) -> TelegramService:
    """Dependency to get Telegram service."""
    return request.app.state.telegram_service


async def get_database_service(request: Request) -> DatabaseService:
    """Dependency to get Database service."""
    return request.app.state.database_service


@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    telegram_service: TelegramService = Depends(get_telegram_service)
):
    """Handle incoming Telegram webhooks."""
    # Verify webhook signature
    if not verify_telegram_webhook(request):
        logger.warning("Invalid webhook signature")
        raise HTTPException(status_code=403, detail="Invalid signature")
    
    try:
        # Parse update data
        update_data = await request.json()
        update = Update.de_json(update_data, telegram_service.bot)
        
        if not update:
            logger.warning("Failed to parse update", data=update_data)
            raise HTTPException(status_code=400, detail="Invalid update data")
        
        # Process update asynchronously
        await telegram_service.handle_update(update)
        
        return {"status": "ok"}
        
    except Exception as e:
        logger.error("Error processing webhook", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "voice-retro-bot",
        "version": "1.0.0"
    }


@router.get("/metrics")
async def metrics():
    """Basic metrics endpoint (placeholder for Prometheus integration)."""
    return {
        "uptime": "running",
        "webhooks_processed": 0,  # TODO: Implement actual metrics
        "errors": 0
    }