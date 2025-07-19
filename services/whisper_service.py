"""OpenAI Whisper API integration for speech-to-text."""

from __future__ import annotations
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any

import structlog
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config import settings


logger = structlog.get_logger()


class WhisperTranscriptionError(Exception):
    """Raised when Whisper transcription fails."""
    pass


class WhisperService:
    """Service for OpenAI Whisper speech-to-text transcription."""
    
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model_whisper
        self.timeout = 30  # API timeout in seconds
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((asyncio.TimeoutError, Exception))
    )
    async def transcribe_audio(
        self,
        audio_file_path: str | Path,
        language: str = "ru",
        prompt: Optional[str] = None,
        response_format: str = "json"
    ) -> Dict[str, Any]:
        """
        Transcribe audio file using OpenAI Whisper.
        
        Args:
            audio_file_path: Path to audio file (MP3, WAV, etc.)
            language: Language code (ISO-639-1), defaults to Russian
            prompt: Optional prompt to guide the model
            response_format: Response format (json, text, srt, verbose_json, vtt)
            
        Returns:
            Transcription result dictionary
            
        Raises:
            WhisperTranscriptionError: If transcription fails
        """
        audio_file_path = Path(audio_file_path)
        
        if not audio_file_path.exists():
            raise WhisperTranscriptionError(f"Audio file not found: {audio_file_path}")
        
        file_size = audio_file_path.stat().st_size
        
        logger.info(
            "Starting Whisper transcription",
            file=str(audio_file_path),
            file_size=file_size,
            language=language,
            model=self.model
        )
        
        try:
            # Open audio file
            with open(audio_file_path, 'rb') as audio_file:
                # Prepare request parameters
                transcription_params = {
                    "model": self.model,
                    "file": audio_file,
                    "language": language,
                    "response_format": response_format
                }
                
                if prompt:
                    transcription_params["prompt"] = prompt
                
                # Call Whisper API with timeout
                response = await asyncio.wait_for(
                    self.client.audio.transcriptions.create(**transcription_params),
                    timeout=self.timeout
                )
                
                # Handle different response formats
                if response_format == "json":
                    result = {
                        "text": response.text,
                        "language": language,
                        "model": self.model,
                        "file_size": file_size
                    }
                elif response_format == "verbose_json":
                    result = {
                        "text": response.text,
                        "language": response.language if hasattr(response, 'language') else language,
                        "duration": response.duration if hasattr(response, 'duration') else None,
                        "segments": response.segments if hasattr(response, 'segments') else [],
                        "model": self.model,
                        "file_size": file_size
                    }
                else:
                    # For text, srt, vtt formats
                    result = {
                        "text": str(response),
                        "language": language,
                        "model": self.model,
                        "file_size": file_size
                    }
                
                logger.info(
                    "Whisper transcription completed",
                    text_length=len(result["text"]),
                    language=result.get("language"),
                    duration=result.get("duration")
                )
                
                return result
                
        except asyncio.TimeoutError:
            logger.error("Whisper transcription timed out", timeout=self.timeout)
            raise WhisperTranscriptionError(f"Transcription timed out after {self.timeout} seconds")
        
        except Exception as e:
            logger.error("Whisper transcription failed", error=str(e), exc_info=True)
            raise WhisperTranscriptionError(f"Transcription failed: {str(e)}")
    
    async def transcribe_with_fallback(
        self,
        audio_file_path: str | Path,
        primary_language: str = "ru",
        fallback_language: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Transcribe audio with language fallback.
        
        Args:
            audio_file_path: Path to audio file
            primary_language: Primary language to try
            fallback_language: Fallback language if primary fails
            
        Returns:
            Transcription result dictionary
        """
        try:
            # Try primary language
            result = await self.transcribe_audio(
                audio_file_path, 
                language=primary_language
            )
            
            # Check if transcription seems successful
            if result["text"].strip():
                return result
            
        except WhisperTranscriptionError as e:
            logger.warning(
                "Primary language transcription failed",
                language=primary_language,
                error=str(e)
            )
        
        # Try fallback language if specified
        if fallback_language:
            logger.info("Trying fallback language", fallback_language=fallback_language)
            
            try:
                result = await self.transcribe_audio(
                    audio_file_path,
                    language=fallback_language
                )
                result["fallback_used"] = True
                return result
                
            except WhisperTranscriptionError as e:
                logger.error(
                    "Fallback language transcription failed",
                    language=fallback_language,
                    error=str(e)
                )
        
        # Try without language specification (auto-detect)
        logger.info("Trying auto-detection")
        
        try:
            result = await self.transcribe_audio(audio_file_path, language="")
            result["auto_detected"] = True
            return result
            
        except WhisperTranscriptionError as e:
            logger.error("Auto-detection transcription failed", error=str(e))
            raise
    
    async def validate_transcription(self, result: Dict[str, Any]) -> bool:
        """
        Validate transcription result quality.
        
        Args:
            result: Transcription result dictionary
            
        Returns:
            True if transcription seems valid, False otherwise
        """
        text = result.get("text", "").strip()
        
        # Basic validation checks
        if not text:
            return False
        
        # Check for minimum length
        if len(text) < 3:
            logger.warning("Transcription too short", text=text)
            return False
        
        # Check for suspicious patterns
        suspicious_patterns = [
            "..." * 3,  # Multiple ellipses
            "[неразборчиво]",
            "[inaudible]",
            "???"
        ]
        
        for pattern in suspicious_patterns:
            if pattern in text.lower():
                logger.warning("Suspicious pattern in transcription", pattern=pattern)
                return False
        
        return True
    
    async def estimate_cost(self, audio_file_path: str | Path) -> float:
        """
        Estimate transcription cost based on file duration.
        
        Args:
            audio_file_path: Path to audio file
            
        Returns:
            Estimated cost in USD
        """
        from utils.audio_converter import audio_converter
        
        # Get audio duration
        duration = await audio_converter.get_audio_duration(audio_file_path)
        
        if duration is None:
            return 0.0
        
        # OpenAI Whisper pricing: $0.006 per minute
        cost_per_minute = 0.006
        duration_minutes = duration / 60
        
        return duration_minutes * cost_per_minute


# Global Whisper service instance
whisper_service = WhisperService()