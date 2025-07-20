"""Voice processing service that orchestrates the entire pipeline."""

from __future__ import annotations
import asyncio
import time
from pathlib import Path
from typing import Optional, Dict, Any

import structlog

from utils.audio_converter import audio_converter, AudioConversionError
from utils.file_manager import file_manager
from services.whisper_service import whisper_service, WhisperTranscriptionError
from utils.progress_tracker import (
    ProgressTracker, 
    TelegramProgressTracker, 
    ProcessingStep
)


logger = structlog.get_logger()


class VoiceProcessingError(Exception):
    """Raised when voice processing fails."""
    pass


class VoiceProcessingResult:
    """Result of voice processing pipeline."""
    
    def __init__(
        self,
        success: bool,
        transcribed_text: str = "",
        original_language: str = "",
        processing_time: float = 0.0,
        file_size: int = 0,
        error_message: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.success = success
        self.transcribed_text = transcribed_text
        self.original_language = original_language
        self.processing_time = processing_time
        self.file_size = file_size
        self.error_message = error_message
        self.metadata = metadata or {}
    
    def __repr__(self) -> str:
        return (
            f"VoiceProcessingResult(success={self.success}, "
            f"text_length={len(self.transcribed_text)}, "
            f"language={self.original_language})"
        )


class VoiceProcessor:
    """Main voice processing service."""
    
    def __init__(self):
        self.max_retries = 2
        self.processing_timeout = 120  # 2 minutes total timeout
    
    async def process_telegram_voice(
        self,
        bot,
        file_id: str,
        chat_id: int,
        progress_message_id: Optional[int] = None,
        language: str = "ru"
    ) -> VoiceProcessingResult:
        """
        Process voice message from Telegram.
        
        Args:
            bot: Telegram bot instance
            file_id: Telegram file ID
            chat_id: Chat ID for progress updates
            progress_message_id: Message ID for progress updates
            language: Expected language code
            
        Returns:
            VoiceProcessingResult with transcription and metadata
        """
        start_time = time.time()
        
        # Create progress tracker only if message_id provided
        if progress_message_id:
            progress = TelegramProgressTracker(
                bot=bot,
                chat_id=chat_id,
                message_id=progress_message_id
            )
        else:
            progress = None
        
        try:
            # Step 1: Download voice file
            if progress:
                await progress.start_step(
                    ProcessingStep.DOWNLOADING,
                    "Загружаю голосовое сообщение..."
                )
            
            async with file_manager.telegram_file_context(
                bot, file_id, ".ogg"
            ) as ogg_file_path:
                
                file_size = ogg_file_path.stat().st_size
                
                if progress:
                    await progress.complete_step(
                        ProcessingStep.DOWNLOADING,
                        f"Файл загружен ({file_size} байт)"
                    )
                
                # Step 2: Validate audio file
                if progress:
                    await progress.start_step(
                        ProcessingStep.VALIDATING,
                        "Проверяю аудиофайл..."
                    )
                
                is_valid = await audio_converter.validate_audio_file(ogg_file_path)
                if not is_valid:
                    raise VoiceProcessingError("Недействительный аудиофайл")
                
                # Get audio duration for metadata
                duration = await audio_converter.get_audio_duration(ogg_file_path)
                
                if progress:
                    await progress.complete_step(
                        ProcessingStep.VALIDATING,
                        f"Аудиофайл корректен ({duration:.1f}с)" if duration else "Аудиофайл корректен"
                    )
                
                # Step 3: Convert to MP3
                if progress:
                    await progress.start_step(
                        ProcessingStep.CONVERTING,
                        "Конвертирую аудио в MP3..."
                    )
                
                async with file_manager.temp_file_context(
                    suffix=".mp3", prefix="converted_"
                ) as mp3_file_path:
                    
                    mp3_path = await audio_converter.convert_ogg_to_mp3(
                        ogg_file_path, mp3_file_path
                    )
                    
                    if progress:
                        await progress.complete_step(
                            ProcessingStep.CONVERTING,
                            "Аудио конвертировано в MP3"
                        )
                    
                    # Step 4: Transcribe with Whisper
                    if progress:
                        await progress.start_step(
                            ProcessingStep.TRANSCRIBING,
                            "Расшифровываю речь с помощью Whisper..."
                        )
                    
                    transcription_result = await whisper_service.transcribe_with_fallback(
                        mp3_path,
                        primary_language=language,
                        fallback_language="en" if language != "en" else None
                    )
                    
                    # Validate transcription quality
                    is_valid_transcription = await whisper_service.validate_transcription(
                        transcription_result
                    )
                    
                    if not is_valid_transcription:
                        logger.warning("Low quality transcription detected")
                    
                    if progress:
                        await progress.complete_step(
                            ProcessingStep.TRANSCRIBING,
                            f"Речь расшифрована ({len(transcription_result['text'])} символов)"
                        )
                    
                    # Step 5: Use raw transcription (no processing needed)
                    final_text = transcription_result["text"]
                    
                    # Step 6: Processing completed
                    processing_time = time.time() - start_time
                    
                    if progress:
                        await progress.complete_step(
                            ProcessingStep.COMPLETED,
                            f"Обработка завершена за {processing_time:.1f}с"
                        )
                    
                    # Create result
                    result = VoiceProcessingResult(
                        success=True,
                        transcribed_text=final_text,
                        original_language=transcription_result.get("language", language),
                        processing_time=processing_time,
                        file_size=file_size,
                        metadata={
                            "duration": duration,
                            "whisper_model": transcription_result.get("model"),
                            "fallback_used": transcription_result.get("fallback_used", False),
                            "auto_detected": transcription_result.get("auto_detected", False),
                            "quality_valid": is_valid_transcription,
                            "raw_transcription": transcription_result["text"],
                            "text_cleaned": False,
                            "gpt_tokens_used": 0,
                            "gpt_cost": 0.0
                        }
                    )
                    
                    logger.info(
                        "Voice processing completed successfully",
                        file_id=file_id,
                        text_length=len(result.transcribed_text),
                        processing_time=processing_time,
                        language=result.original_language
                    )
                    
                    return result
        
        except asyncio.TimeoutError:
            error_msg = "Превышено время обработки"
            if progress:
                await progress.fail_step(error_msg)
            
            return VoiceProcessingResult(
                success=False,
                error_message=error_msg,
                processing_time=time.time() - start_time
            )
        
        except (AudioConversionError, WhisperTranscriptionError, VoiceProcessingError) as e:
            error_msg = f"Ошибка обработки: {str(e)}"
            if progress:
                await progress.fail_step(error_msg)
            
            logger.error("Voice processing failed", error=str(e), file_id=file_id)
            
            return VoiceProcessingResult(
                success=False,
                error_message=error_msg,
                processing_time=time.time() - start_time
            )
        
        except Exception as e:
            error_msg = "Внутренняя ошибка сервера"
            if progress:
                await progress.fail_step(error_msg)
            
            logger.error(
                "Unexpected error during voice processing",
                error=str(e),
                file_id=file_id,
                exc_info=True
            )
            
            return VoiceProcessingResult(
                success=False,
                error_message=error_msg,
                processing_time=time.time() - start_time
            )
    
    async def process_voice_file(
        self,
        file_path: str | Path,
        progress_callback: Optional[ProgressTracker] = None,
        language: str = "ru"
    ) -> VoiceProcessingResult:
        """
        Process voice file directly (for testing or non-Telegram use).
        
        Args:
            file_path: Path to voice file
            progress_callback: Optional progress tracker
            language: Expected language code
            
        Returns:
            VoiceProcessingResult with transcription and metadata
        """
        start_time = time.time()
        
        file_path = Path(file_path)
        
        if not file_path.exists():
            return VoiceProcessingResult(
                success=False,
                error_message=f"File not found: {file_path}"
            )
        
        try:
            file_size = file_path.stat().st_size
            
            # If file is already MP3, use directly, otherwise convert
            if file_path.suffix.lower() == '.mp3':
                mp3_path = file_path
                cleanup_mp3 = False
            else:
                # Convert to MP3
                if progress_callback:
                    await progress_callback.start_step(
                        ProcessingStep.CONVERTING,
                        "Converting audio to MP3..."
                    )
                
                mp3_path = await audio_converter.convert_ogg_to_mp3(file_path)
                cleanup_mp3 = True
            
            try:
                # Transcribe
                if progress_callback:
                    await progress_callback.start_step(
                        ProcessingStep.TRANSCRIBING,
                        "Transcribing speech..."
                    )
                
                transcription_result = await whisper_service.transcribe_with_fallback(
                    mp3_path,
                    primary_language=language
                )
                
                processing_time = time.time() - start_time
                
                if progress_callback:
                    await progress_callback.complete_step(
                        ProcessingStep.COMPLETED,
                        f"Processing completed in {processing_time:.1f}s"
                    )
                
                return VoiceProcessingResult(
                    success=True,
                    transcribed_text=transcription_result["text"],
                    original_language=transcription_result.get("language", language),
                    processing_time=processing_time,
                    file_size=file_size,
                    metadata={
                        "whisper_model": transcription_result.get("model"),
                        "fallback_used": transcription_result.get("fallback_used", False),
                        "auto_detected": transcription_result.get("auto_detected", False)
                    }
                )
            
            finally:
                # Cleanup converted MP3 if we created it
                if cleanup_mp3:
                    file_manager.cleanup_file(mp3_path)
        
        except Exception as e:
            error_msg = f"Processing failed: {str(e)}"
            
            if progress_callback:
                await progress_callback.fail_step(error_msg)
            
            return VoiceProcessingResult(
                success=False,
                error_message=error_msg,
                processing_time=time.time() - start_time
            )
    
    async def estimate_processing_cost(self, file_id: str, bot) -> float:
        """
        Estimate processing cost for a Telegram voice message.
        
        Args:
            file_id: Telegram file ID
            bot: Telegram bot instance
            
        Returns:
            Estimated cost in USD
        """
        try:
            async with file_manager.telegram_file_context(
                bot, file_id, ".ogg"
            ) as ogg_file_path:
                
                # Convert to get accurate duration
                async with file_manager.temp_file_context(
                    suffix=".mp3"
                ) as mp3_file_path:
                    
                    await audio_converter.convert_ogg_to_mp3(ogg_file_path, mp3_file_path)
                    cost = await whisper_service.estimate_cost(mp3_file_path)
                    
                    return cost
        
        except Exception as e:
            logger.error("Failed to estimate processing cost", error=str(e))
            return 0.0


# Global voice processor instance
voice_processor = VoiceProcessor()