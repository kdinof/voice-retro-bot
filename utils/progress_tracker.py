"""Progress tracking for voice processing pipeline."""

from __future__ import annotations
import asyncio
from enum import Enum
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass
from datetime import datetime

import structlog


logger = structlog.get_logger()


class ProcessingStep(str, Enum):
    """Voice processing pipeline steps."""
    DOWNLOADING = "downloading"
    VALIDATING = "validating"
    CONVERTING = "converting"
    TRANSCRIBING = "transcribing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ProgressState:
    """Progress state information."""
    step: ProcessingStep
    message: str
    progress_percent: float = 0.0
    error: Optional[str] = None
    started_at: datetime = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.started_at is None:
            self.started_at = datetime.utcnow()
        if self.metadata is None:
            self.metadata = {}


class ProgressTracker:
    """Tracks and reports progress for voice processing."""
    
    def __init__(
        self,
        update_callback: Optional[Callable[[ProgressState], Any]] = None,
        throttle_seconds: float = 1.0
    ):
        self.update_callback = update_callback
        self.throttle_seconds = throttle_seconds
        self.current_state: Optional[ProgressState] = None
        self.last_update_time: Optional[datetime] = None
        self._lock = asyncio.Lock()
    
    async def update_progress(
        self,
        step: ProcessingStep,
        message: str,
        progress_percent: float = 0.0,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        force_update: bool = False
    ) -> None:
        """
        Update progress state and trigger callback if needed.
        
        Args:
            step: Current processing step
            message: Human-readable progress message
            progress_percent: Progress percentage (0-100)
            error: Optional error message
            metadata: Optional additional metadata
            force_update: Force update even if throttled
        """
        async with self._lock:
            self.current_state = ProgressState(
                step=step,
                message=message,
                progress_percent=progress_percent,
                error=error,
                metadata=metadata or {}
            )
            
            # Check if we should send update (throttling)
            now = datetime.utcnow()
            should_update = (
                force_update or
                self.last_update_time is None or
                (now - self.last_update_time).total_seconds() >= self.throttle_seconds or
                step in [ProcessingStep.COMPLETED, ProcessingStep.FAILED]
            )
            
            if should_update and self.update_callback:
                try:
                    await self._call_update_callback()
                    self.last_update_time = now
                except Exception as e:
                    logger.error("Progress callback failed", error=str(e))
    
    async def _call_update_callback(self) -> None:
        """Call the update callback with current state."""
        if self.update_callback and self.current_state:
            if asyncio.iscoroutinefunction(self.update_callback):
                await self.update_callback(self.current_state)
            else:
                self.update_callback(self.current_state)
    
    async def start_step(
        self,
        step: ProcessingStep,
        message: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Start a new processing step."""
        logger.info("Starting processing step", step=step, message=message)
        await self.update_progress(
            step=step,
            message=message,
            progress_percent=0.0,
            metadata=metadata,
            force_update=True
        )
    
    async def complete_step(
        self,
        step: ProcessingStep,
        message: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Complete a processing step."""
        logger.info("Completed processing step", step=step, message=message)
        await self.update_progress(
            step=step,
            message=message,
            progress_percent=100.0,
            metadata=metadata,
            force_update=True
        )
    
    async def fail_step(
        self,
        error_message: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Mark current step as failed."""
        logger.error("Processing step failed", error=error_message)
        await self.update_progress(
            step=ProcessingStep.FAILED,
            message="❌ Обработка не удалась",
            error=error_message,
            metadata=metadata,
            force_update=True
        )
    
    def get_current_state(self) -> Optional[ProgressState]:
        """Get current progress state."""
        return self.current_state
    
    def get_emoji_for_step(self, step: ProcessingStep) -> str:
        """Get emoji representation for processing step."""
        emoji_map = {
            ProcessingStep.DOWNLOADING: "⬇️",
            ProcessingStep.VALIDATING: "🔍",
            ProcessingStep.CONVERTING: "🔄",
            ProcessingStep.TRANSCRIBING: "🎤",
            ProcessingStep.COMPLETED: "✅",
            ProcessingStep.FAILED: "❌"
        }
        return emoji_map.get(step, "⚙️")
    
    def get_progress_message(self, step: ProcessingStep, custom_message: str = "") -> str:
        """Get formatted progress message."""
        emoji = self.get_emoji_for_step(step)
        
        default_messages = {
            ProcessingStep.DOWNLOADING: "Загружаю голосовое сообщение...",
            ProcessingStep.VALIDATING: "Проверяю аудиофайл...",
            ProcessingStep.CONVERTING: "Конвертирую аудио...",
            ProcessingStep.TRANSCRIBING: "Расшифровываю речь...",
            ProcessingStep.COMPLETED: "Готово!",
            ProcessingStep.FAILED: "Ошибка обработки"
        }
        
        message = custom_message or default_messages.get(step, "Обрабатываю...")
        return f"{emoji} {message}"


class TelegramProgressTracker(ProgressTracker):
    """Progress tracker that updates Telegram messages."""
    
    def __init__(
        self,
        bot,
        chat_id: int,
        message_id: Optional[int] = None,
        throttle_seconds: float = 2.0
    ):
        self.bot = bot
        self.chat_id = chat_id
        self.message_id = message_id
        
        super().__init__(
            update_callback=self._update_telegram_message,
            throttle_seconds=throttle_seconds
        )
    
    async def _update_telegram_message(self, state: ProgressState) -> None:
        """Update Telegram message with current progress."""
        message_text = self.get_progress_message(state.step, state.message)
        
        # Add progress bar for steps with meaningful progress
        if 0 < state.progress_percent < 100:
            progress_bar = self._create_progress_bar(state.progress_percent)
            message_text += f"\n{progress_bar}"
        
        # Add error information
        if state.error:
            message_text += f"\n\n💬 {state.error}"
        
        try:
            if self.message_id:
                # Edit existing message
                await self.bot.edit_message_text(
                    chat_id=self.chat_id,
                    message_id=self.message_id,
                    text=message_text
                )
            else:
                # Send new message
                message = await self.bot.send_message(
                    chat_id=self.chat_id,
                    text=message_text
                )
                self.message_id = message.message_id
                
        except Exception as e:
            logger.warning(
                "Failed to update Telegram progress message",
                error=str(e),
                chat_id=self.chat_id,
                message_id=self.message_id
            )
    
    def _create_progress_bar(self, percent: float, length: int = 10) -> str:
        """Create a text progress bar."""
        filled = int(length * percent / 100)
        bar = "█" * filled + "░" * (length - filled)
        return f"[{bar}] {percent:.0f}%"
    
    async def send_final_message(self, text: str) -> int:
        """Send final message and return message ID."""
        try:
            message = await self.bot.send_message(
                chat_id=self.chat_id,
                text=text,
                parse_mode="Markdown"
            )
            return message.message_id
        except Exception as e:
            logger.error("Failed to send final message", error=str(e))
            raise