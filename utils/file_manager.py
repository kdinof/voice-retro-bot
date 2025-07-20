"""Temporary file management utilities."""

from __future__ import annotations
import asyncio
import os
import tempfile
import time
import uuid
from pathlib import Path
from typing import Optional, AsyncContextManager
from contextlib import asynccontextmanager

import structlog
from config import settings


logger = structlog.get_logger()


class TempFileManager:
    """Manages temporary files with automatic cleanup."""
    
    def __init__(self):
        self.temp_dir = Path(settings.temp_files_dir)
        self.temp_dir.mkdir(exist_ok=True)
        self.max_file_size = settings.max_file_size_mb * 1024 * 1024  # Convert to bytes
    
    def generate_temp_path(self, suffix: str = "", prefix: str = "voice_retro_") -> Path:
        """Generate unique temporary file path."""
        unique_id = str(uuid.uuid4())[:8]
        filename = f"{prefix}{unique_id}{suffix}"
        return self.temp_dir / filename
    
    def validate_file_size(self, file_path: str | Path) -> bool:
        """Validate file size against limits."""
        file_path = Path(file_path)
        
        if not file_path.exists():
            return False
        
        file_size = file_path.stat().st_size
        
        if file_size > self.max_file_size:
            logger.warning(
                "File size exceeds limit",
                file_size=file_size,
                max_size=self.max_file_size,
                file=str(file_path)
            )
            return False
        
        return True
    
    async def download_telegram_file(
        self, 
        bot, 
        file_id: str, 
        file_extension: str = ".ogg"
    ) -> Path:
        """
        Download file from Telegram and save to temp directory.
        
        Args:
            bot: Telegram bot instance
            file_id: Telegram file ID
            file_extension: File extension to use
            
        Returns:
            Path to downloaded file
            
        Raises:
            Exception: If download fails
        """
        temp_path = self.generate_temp_path(suffix=file_extension)
        
        try:
            # Get file info from Telegram
            file_info = await bot.get_file(file_id)
            
            # Validate file size
            if file_info.file_size and file_info.file_size > self.max_file_size:
                raise ValueError(f"File too large: {file_info.file_size} bytes")
            
            # Download file
            await file_info.download_to_drive(str(temp_path))
            
            # Validate downloaded file
            if not self.validate_file_size(temp_path):
                temp_path.unlink(missing_ok=True)
                raise ValueError("Downloaded file validation failed")
            
            logger.info(
                "File downloaded from Telegram",
                file_id=file_id,
                file_size=temp_path.stat().st_size,
                temp_path=str(temp_path)
            )
            
            return temp_path
            
        except Exception as e:
            # Clean up on error
            temp_path.unlink(missing_ok=True)
            logger.error("Failed to download Telegram file", file_id=file_id, error=str(e))
            raise
    
    def cleanup_file(self, file_path: str | Path) -> bool:
        """
        Clean up a single file.
        
        Args:
            file_path: Path to file to delete
            
        Returns:
            True if file was deleted, False otherwise
        """
        try:
            file_path = Path(file_path)
            if file_path.exists():
                file_path.unlink()
                logger.debug("Cleaned up file", file=str(file_path))
                return True
        except Exception as e:
            logger.warning("Failed to cleanup file", file=str(file_path), error=str(e))
        
        return False
    
    def cleanup_files(self, *file_paths: str | Path) -> int:
        """
        Clean up multiple files.
        
        Args:
            *file_paths: Paths to files to delete
            
        Returns:
            Number of files successfully deleted
        """
        cleaned_count = 0
        for file_path in file_paths:
            if self.cleanup_file(file_path):
                cleaned_count += 1
        
        logger.info("Cleaned up files", total=len(file_paths), cleaned=cleaned_count)
        return cleaned_count
    
    async def cleanup_old_files(self, max_age_hours: int = 1) -> int:
        """
        Clean up old temporary files.
        
        Args:
            max_age_hours: Maximum age of files to keep in hours
            
        Returns:
            Number of files cleaned up
        """
        
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        cleaned_count = 0
        
        try:
            for file_path in self.temp_dir.glob("*"):
                if file_path.is_file():
                    file_age = current_time - file_path.stat().st_mtime
                    
                    if file_age > max_age_seconds:
                        if self.cleanup_file(file_path):
                            cleaned_count += 1
            
            logger.info("Cleaned up old files", cleaned=cleaned_count, max_age_hours=max_age_hours)
            
        except Exception as e:
            logger.error("Error during old file cleanup", error=str(e))
        
        return cleaned_count
    
    @asynccontextmanager
    async def temp_file_context(
        self, 
        suffix: str = "", 
        prefix: str = "voice_retro_"
    ) -> AsyncContextManager[Path]:
        """
        Context manager for temporary files with automatic cleanup.
        
        Args:
            suffix: File suffix/extension
            prefix: File prefix
            
        Yields:
            Path to temporary file
        """
        temp_path = self.generate_temp_path(suffix=suffix, prefix=prefix)
        
        try:
            logger.debug("Created temp file context", file=str(temp_path))
            yield temp_path
        finally:
            self.cleanup_file(temp_path)
            logger.debug("Cleaned up temp file context", file=str(temp_path))
    
    @asynccontextmanager
    async def telegram_file_context(
        self, 
        bot, 
        file_id: str, 
        file_extension: str = ".ogg"
    ) -> AsyncContextManager[Path]:
        """
        Context manager for Telegram files with automatic cleanup.
        
        Args:
            bot: Telegram bot instance
            file_id: Telegram file ID
            file_extension: File extension
            
        Yields:
            Path to downloaded file
        """
        file_path = None
        
        try:
            file_path = await self.download_telegram_file(bot, file_id, file_extension)
            logger.debug("Created Telegram file context", file=str(file_path))
            yield file_path
        finally:
            if file_path:
                self.cleanup_file(file_path)
                logger.debug("Cleaned up Telegram file context", file=str(file_path))


# Global file manager instance
file_manager = TempFileManager()