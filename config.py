"""Configuration management for the Voice Retro Bot."""

import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import validator


class Settings(BaseSettings):
    """Application settings."""
    
    # Telegram Bot Configuration
    bot_token: str
    telegram_webhook_url: Optional[str] = None
    telegram_webhook_secret: Optional[str] = None
    
    # OpenAI Configuration
    openai_api_key: str
    openai_model_whisper: str = "whisper-1"
    openai_model_gpt: str = "gpt-4o-mini"
    
    # Server Configuration
    server_host: str = "0.0.0.0"
    server_port: int = 8000
    debug: bool = False
    
    # Database Configuration
    database_url: str = "sqlite+aiosqlite:///./voice_retro.db"
    
    # File Processing Configuration
    temp_files_dir: str = "./temp"
    max_file_size_mb: int = 25
    audio_processing_timeout: int = 30
    
    # Voice Processing Configuration
    ffmpeg_path: str = "ffmpeg"
    
    @validator('bot_token')
    def validate_bot_token(cls, v):
        if not v:
            raise ValueError('Telegram bot token is required')
        return v
    
    @validator('openai_api_key')
    def validate_openai_key(cls, v):
        if not v:
            raise ValueError('OpenAI API key is required')
        return v
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global settings instance
settings = Settings()