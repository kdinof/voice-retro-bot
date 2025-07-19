"""Audio conversion utilities using FFmpeg."""

from __future__ import annotations
import asyncio
import os
import tempfile
import uuid
from pathlib import Path
from typing import Optional

import structlog
from config import settings


logger = structlog.get_logger()


class AudioConversionError(Exception):
    """Raised when audio conversion fails."""
    pass


class AudioConverter:
    """Handles audio conversion using FFmpeg."""
    
    def __init__(self):
        self.ffmpeg_path = settings.ffmpeg_path
        self.temp_dir = Path(settings.temp_files_dir)
        self.temp_dir.mkdir(exist_ok=True)
        self.timeout = settings.audio_processing_timeout
    
    async def convert_ogg_to_mp3(
        self, 
        input_path: str | Path, 
        output_path: Optional[str | Path] = None
    ) -> Path:
        """
        Convert OGG file to MP3 using FFmpeg.
        
        Args:
            input_path: Path to input OGG file
            output_path: Optional output path, auto-generated if None
            
        Returns:
            Path to converted MP3 file
            
        Raises:
            AudioConversionError: If conversion fails
        """
        input_path = Path(input_path)
        
        if not input_path.exists():
            raise AudioConversionError(f"Input file not found: {input_path}")
        
        # Generate output path if not provided
        if output_path is None:
            unique_id = str(uuid.uuid4())[:8]
            output_path = self.temp_dir / f"audio_{unique_id}.mp3"
        else:
            output_path = Path(output_path)
        
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Build FFmpeg command
        ffmpeg_cmd = [
            self.ffmpeg_path,
            '-i', str(input_path),      # Input file
            '-f', 'mp3',                # Output format
            '-acodec', 'libmp3lame',    # Audio codec
            '-ab', '192k',              # Bitrate
            '-ar', '44100',             # Sample rate
            '-y',                       # Overwrite output file
            str(output_path)            # Output file
        ]
        
        logger.info(
            "Starting audio conversion",
            input_file=str(input_path),
            output_file=str(output_path),
            command=" ".join(ffmpeg_cmd[:3] + ["..."])  # Log partial command for security
        )
        
        try:
            # Run FFmpeg with timeout
            process = await asyncio.create_subprocess_exec(
                *ffmpeg_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self.timeout
            )
            
            if process.returncode != 0:
                error_msg = stderr.decode('utf-8', errors='ignore')
                logger.error(
                    "FFmpeg conversion failed",
                    return_code=process.returncode,
                    stderr=error_msg
                )
                raise AudioConversionError(f"FFmpeg failed: {error_msg}")
            
            # Verify output file exists and has content
            if not output_path.exists() or output_path.stat().st_size == 0:
                raise AudioConversionError("Output file was not created or is empty")
            
            logger.info(
                "Audio conversion completed",
                input_size=input_path.stat().st_size,
                output_size=output_path.stat().st_size,
                output_file=str(output_path)
            )
            
            return output_path
            
        except asyncio.TimeoutError:
            logger.error("Audio conversion timed out", timeout=self.timeout)
            raise AudioConversionError(f"Conversion timed out after {self.timeout} seconds")
        
        except Exception as e:
            logger.error("Unexpected error during conversion", error=str(e), exc_info=True)
            raise AudioConversionError(f"Conversion failed: {str(e)}")
    
    async def validate_audio_file(self, file_path: str | Path) -> bool:
        """
        Validate audio file using FFmpeg probe.
        
        Args:
            file_path: Path to audio file
            
        Returns:
            True if file is valid audio, False otherwise
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            return False
        
        # Use ffprobe to validate file
        probe_cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            str(file_path)
        ]
        
        try:
            process = await asyncio.create_subprocess_exec(
                *probe_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=10  # Short timeout for validation
            )
            
            return process.returncode == 0
            
        except Exception as e:
            logger.warning("Audio validation failed", file=str(file_path), error=str(e))
            return False
    
    async def get_audio_duration(self, file_path: str | Path) -> Optional[float]:
        """
        Get audio file duration in seconds.
        
        Args:
            file_path: Path to audio file
            
        Returns:
            Duration in seconds, or None if unable to determine
        """
        file_path = Path(file_path)
        
        probe_cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            str(file_path)
        ]
        
        try:
            process = await asyncio.create_subprocess_exec(
                *probe_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                import json
                probe_data = json.loads(stdout.decode())
                duration = probe_data.get('format', {}).get('duration')
                return float(duration) if duration else None
            
        except Exception as e:
            logger.warning("Could not get audio duration", file=str(file_path), error=str(e))
        
        return None
    
    def cleanup_temp_files(self, *file_paths: str | Path) -> None:
        """
        Clean up temporary files.
        
        Args:
            *file_paths: Paths to files to delete
        """
        for file_path in file_paths:
            try:
                file_path = Path(file_path)
                if file_path.exists():
                    file_path.unlink()
                    logger.debug("Cleaned up temp file", file=str(file_path))
            except Exception as e:
                logger.warning("Failed to cleanup temp file", file=str(file_path), error=str(e))


# Global converter instance
audio_converter = AudioConverter()