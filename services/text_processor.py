"""Text processing service that orchestrates GPT-based text analysis and cleaning."""

from __future__ import annotations
import time
from typing import Dict, Any, Optional
from enum import Enum

import structlog

from services.gpt_service import gpt_service
from utils.prompt_templates import PromptType
from utils.progress_tracker import ProgressTracker, ProcessingStep


logger = structlog.get_logger()


class TextProcessingError(Exception):
    """Raised when text processing fails."""
    pass


class RetroFieldType(str, Enum):
    """Types of retrospective fields."""
    ENERGY = "energy"
    MOOD = "mood"
    WINS = "wins"
    LEARNINGS = "learnings"
    NEXT_ACTIONS = "next_actions"
    MITS = "mits"
    EXPERIMENT = "experiment"


class TextProcessingResult:
    """Result of text processing operations."""
    
    def __init__(
        self,
        success: bool,
        processed_data: Optional[Dict[str, Any]] = None,
        cleaned_text: str = "",
        original_text: str = "",
        processing_time: float = 0.0,
        tokens_used: int = 0,
        estimated_cost: float = 0.0,
        error_message: str = ""
    ):
        self.success = success
        self.processed_data = processed_data or {}
        self.cleaned_text = cleaned_text
        self.original_text = original_text
        self.processing_time = processing_time
        self.tokens_used = tokens_used
        self.estimated_cost = estimated_cost
        self.error_message = error_message
    
    def __repr__(self) -> str:
        return (
            f"TextProcessingResult(success={self.success}, "
            f"fields={list(self.processed_data.keys())}, "
            f"tokens={self.tokens_used})"
        )


class TextProcessor:
    """Main text processing service using GPT for retro analysis."""
    
    def __init__(self):
        self.field_prompt_mapping = {
            RetroFieldType.ENERGY: PromptType.ENERGY_PROCESSING,
            RetroFieldType.MOOD: PromptType.MOOD_PROCESSING,
            RetroFieldType.WINS: PromptType.WINS_PROCESSING,
            RetroFieldType.LEARNINGS: PromptType.LEARNINGS_PROCESSING,
            RetroFieldType.NEXT_ACTIONS: PromptType.ACTIONS_PROCESSING,
            RetroFieldType.MITS: PromptType.MITS_PROCESSING,
            RetroFieldType.EXPERIMENT: PromptType.EXPERIMENT_PROCESSING
        }
    
    async def process_retro_field(
        self,
        field_type: RetroFieldType,
        user_input: str,
        progress_tracker: Optional[ProgressTracker] = None
    ) -> TextProcessingResult:
        """
        Process a specific retrospective field.
        
        Args:
            field_type: Type of retro field to process
            user_input: User's input text
            progress_tracker: Optional progress tracker
            
        Returns:
            TextProcessingResult with processed data
        """
        start_time = time.time()
        
        if not user_input or not user_input.strip():
            return TextProcessingResult(
                success=False,
                error_message="Empty input text"
            )
        
        try:
            logger.info("Starting retro field processing", field_type=field_type, input_length=len(user_input))
            
            if progress_tracker:
                await progress_tracker.start_step(
                    ProcessingStep.CLEANING,
                    f"Processing {field_type.value}..."
                )
            
            # Process based on field type
            if field_type == RetroFieldType.ENERGY:
                result = await gpt_service.extract_energy_level(user_input)
                processed_data = {"energy_data": result}
                
            elif field_type == RetroFieldType.MOOD:
                result = await gpt_service.extract_mood(user_input)
                processed_data = {"mood_data": result}
                
            elif field_type == RetroFieldType.EXPERIMENT:
                result = await gpt_service.extract_experiment(user_input)
                processed_data = {"experiment_data": result}
                
            elif field_type in [
                RetroFieldType.WINS, 
                RetroFieldType.LEARNINGS, 
                RetroFieldType.NEXT_ACTIONS, 
                RetroFieldType.MITS
            ]:
                prompt_type = self.field_prompt_mapping[field_type]
                result = await gpt_service.extract_list_items(user_input, prompt_type)
                processed_data = {f"{field_type.value}_list": result}
                
            else:
                raise TextProcessingError(f"Unknown field type: {field_type}")
            
            processing_time = time.time() - start_time
            
            if progress_tracker:
                await progress_tracker.complete_step(
                    ProcessingStep.CLEANING,
                    f"{field_type.value.title()} processed"
                )
            
            logger.info(
                "Retro field processed successfully",
                field_type=field_type,
                input_length=len(user_input),
                processing_time=processing_time,
                result_keys=list(processed_data.keys())
            )
            
            return TextProcessingResult(
                success=True,
                processed_data=processed_data,
                original_text=user_input,
                processing_time=processing_time
            )
            
        except Exception as e:
            error_msg = f"Field processing failed: {str(e)}"
            logger.error("Retro field processing error", field_type=field_type, error=str(e))
            
            if progress_tracker:
                await progress_tracker.fail_step(error_msg)
            
            return TextProcessingResult(
                success=False,
                original_text=user_input,
                error_message=error_msg,
                processing_time=time.time() - start_time
            )
    
    async def process_complete_retro(
        self,
        retro_responses: Dict[RetroFieldType, str],
        progress_tracker: Optional[ProgressTracker] = None
    ) -> TextProcessingResult:
        """
        Process all retrospective fields in batch.
        
        Args:
            retro_responses: Dictionary mapping field types to user responses
            progress_tracker: Optional progress tracker
            
        Returns:
            TextProcessingResult with all processed data
        """
        start_time = time.time()
        
        if not retro_responses:
            return TextProcessingResult(
                success=False,
                error_message="No retro responses provided"
            )
        
        try:
            if progress_tracker:
                await progress_tracker.start_step(
                    ProcessingStep.CLEANING,
                    "Processing complete retrospective..."
                )
            
            # Process all fields
            processed_data = {}
            total_tokens = 0
            total_cost = 0.0
            
            for field_type, user_input in retro_responses.items():
                if not user_input or not user_input.strip():
                    continue
                
                field_result = await self.process_retro_field(field_type, user_input)
                
                if field_result.success:
                    processed_data.update(field_result.processed_data)
                    total_tokens += field_result.tokens_used
                    total_cost += field_result.estimated_cost
                else:
                    logger.warning(
                        "Field processing failed",
                        field_type=field_type,
                        error=field_result.error_message
                    )
            
            processing_time = time.time() - start_time
            
            if progress_tracker:
                await progress_tracker.complete_step(
                    ProcessingStep.CLEANING,
                    f"Retrospective processed ({len(processed_data)} fields)"
                )
            
            logger.info(
                "Complete retro processing finished",
                fields_processed=len(processed_data),
                total_tokens=total_tokens,
                total_cost=total_cost,
                processing_time=processing_time
            )
            
            return TextProcessingResult(
                success=True,
                processed_data=processed_data,
                processing_time=processing_time,
                tokens_used=total_tokens,
                estimated_cost=total_cost
            )
            
        except Exception as e:
            error_msg = f"Complete retro processing failed: {str(e)}"
            logger.error("Complete retro processing error", error=str(e))
            
            if progress_tracker:
                await progress_tracker.fail_step(error_msg)
            
            return TextProcessingResult(
                success=False,
                error_message=error_msg,
                processing_time=time.time() - start_time
            )
    
    async def validate_processing_result(
        self,
        result: TextProcessingResult,
        field_type: RetroFieldType
    ) -> bool:
        """
        Validate processing result for specific field type.
        
        Args:
            result: Processing result to validate
            field_type: Expected field type
            
        Returns:
            True if validation passes, False otherwise
        """
        if not result.success or not result.processed_data:
            return False
        
        # Field-specific validation
        if field_type == RetroFieldType.ENERGY:
            energy_data = result.processed_data.get("energy_data", {})
            energy_level = energy_data.get("energy_level")
            return isinstance(energy_level, int) and 1 <= energy_level <= 5
        
        elif field_type == RetroFieldType.MOOD:
            mood_data = result.processed_data.get("mood_data", {})
            return bool(mood_data.get("mood_emoji"))
        
        elif field_type in [
            RetroFieldType.WINS, 
            RetroFieldType.LEARNINGS, 
            RetroFieldType.NEXT_ACTIONS, 
            RetroFieldType.MITS
        ]:
            list_key = f"{field_type.value}_list"
            items = result.processed_data.get(list_key, [])
            return isinstance(items, list)
        
        elif field_type == RetroFieldType.EXPERIMENT:
            experiment_data = result.processed_data.get("experiment_data", {})
            return isinstance(experiment_data, dict)
        
        return True
    
    def get_field_summary(self, result: TextProcessingResult, field_type: RetroFieldType) -> str:
        """
        Get human-readable summary of processing result.
        
        Args:
            result: Processing result
            field_type: Field type that was processed
            
        Returns:
            Summary string
        """
        if not result.success:
            return f"❌ {field_type.value.title()}: {result.error_message}"
        
        if field_type == RetroFieldType.ENERGY:
            energy_data = result.processed_data.get("energy_data", {})
            level = energy_data.get("energy_level", 0)
            return f"⚡ Энергия: {level}/5"
        
        elif field_type == RetroFieldType.MOOD:
            mood_data = result.processed_data.get("mood_data", {})
            emoji = mood_data.get("mood_emoji", "😐")
            return f"😊 Настроение: {emoji}"
        
        elif field_type in [
            RetroFieldType.WINS, 
            RetroFieldType.LEARNINGS, 
            RetroFieldType.NEXT_ACTIONS, 
            RetroFieldType.MITS
        ]:
            list_key = f"{field_type.value}_list"
            items = result.processed_data.get(list_key, [])
            # Escape underscores for markdown
            field_name = field_type.value.replace("_", "\\_").title()
            return f"📝 {field_name}: {len(items)} элементов"
        
        elif field_type == RetroFieldType.EXPERIMENT:
            experiment_data = result.processed_data.get("experiment_data", {})
            has_experiment = bool(experiment_data.get("experiment"))
            return f"🧪 Эксперимент: {'да' if has_experiment else 'нет'}"
        
        # Escape underscores for markdown in general case
        field_name = field_type.value.replace("_", "\\_").title()
        return f"✅ {field_name}: обработано"


# Global text processor instance
text_processor = TextProcessor()