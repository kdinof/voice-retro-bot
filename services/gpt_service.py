"""GPT-4o-mini service for text processing and analysis."""

from __future__ import annotations
import asyncio
import json
from typing import Dict, Any, Optional, List

import structlog
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config import settings
from utils.prompt_templates import PromptTemplateManager, PromptType, PromptTemplate


logger = structlog.get_logger()


class GPTProcessingError(Exception):
    """Raised when GPT processing fails."""
    pass


class GPTResponseValidationError(Exception):
    """Raised when GPT response validation fails."""
    pass


class GPTService:
    """Service for GPT-4o-mini text processing and analysis."""
    
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model_gpt
        self.prompt_manager = PromptTemplateManager()
        self.timeout = 30  # API timeout in seconds
        self.max_retries = 3
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((asyncio.TimeoutError, Exception))
    )
    async def process_text(
        self,
        prompt_type: PromptType,
        user_input: str,
        additional_context: Optional[Dict[str, Any]] = None,
        custom_template: Optional[PromptTemplate] = None
    ) -> Dict[str, Any]:
        """
        Process text using GPT with specified prompt template.
        
        Args:
            prompt_type: Type of prompt to use
            user_input: User input text to process
            additional_context: Additional context variables for template
            custom_template: Optional custom template to use
            
        Returns:
            GPT response with metadata
            
        Raises:
            GPTProcessingError: If processing fails
        """
        template = custom_template or self.prompt_manager.get_template(prompt_type)
        
        # Prepare template variables
        template_vars = {"user_input": user_input}
        if additional_context:
            template_vars.update(additional_context)
        
        # Format user prompt
        try:
            user_prompt = template.format_user_prompt(**template_vars)
        except ValueError as e:
            raise GPTProcessingError(f"Template formatting failed: {e}")
        
        logger.info(
            "Processing text with GPT",
            prompt_type=prompt_type,
            input_length=len(user_input),
            model=self.model
        )
        
        try:
            # Call GPT API
            response = await asyncio.wait_for(
                self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": template.system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    max_tokens=template.max_tokens,
                    temperature=template.temperature,
                    top_p=1.0,
                    frequency_penalty=0.0,
                    presence_penalty=0.0
                ),
                timeout=self.timeout
            )
            
            # Extract response content
            content = response.choices[0].message.content
            
            if not content:
                raise GPTProcessingError("Empty response from GPT")
            
            # Calculate usage and cost
            usage = response.usage
            estimated_cost = self._calculate_cost(usage.prompt_tokens, usage.completion_tokens)
            
            result = {
                "content": content.strip(),
                "prompt_type": prompt_type,
                "template_name": template.name,
                "model": self.model,
                "usage": {
                    "prompt_tokens": usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
                    "total_tokens": usage.total_tokens
                },
                "estimated_cost": estimated_cost,
                "temperature": template.temperature
            }
            
            logger.info(
                "GPT processing completed",
                prompt_type=prompt_type,
                response_length=len(content),
                tokens_used=usage.total_tokens,
                cost=estimated_cost
            )
            
            return result
            
        except asyncio.TimeoutError:
            logger.error("GPT processing timed out", timeout=self.timeout)
            raise GPTProcessingError(f"Processing timed out after {self.timeout} seconds")
        
        except Exception as e:
            logger.error("GPT processing failed", error=str(e), exc_info=True)
            raise GPTProcessingError(f"Processing failed: {str(e)}")
    
    
    async def extract_energy_level(self, user_input: str) -> Dict[str, Any]:
        """
        Extract energy level from user response.
        
        Args:
            user_input: User's energy level response
            
        Returns:
            Dictionary with energy_level and explanation
        """
        result = await self.process_text(
            prompt_type=PromptType.ENERGY_PROCESSING,
            user_input=user_input
        )
        
        try:
            parsed = json.loads(result["content"])
            return self._validate_energy_response(parsed)
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("Failed to parse energy response", response=result["content"])
            # Fallback: try to extract number
            return self._fallback_energy_extraction(user_input)
    
    async def extract_mood(self, user_input: str) -> Dict[str, Any]:
        """
        Extract mood from user response.
        
        Args:
            user_input: User's mood response
            
        Returns:
            Dictionary with mood_emoji and mood_explanation
        """
        result = await self.process_text(
            prompt_type=PromptType.MOOD_PROCESSING,
            user_input=user_input
        )
        
        try:
            parsed = json.loads(result["content"])
            return self._validate_mood_response(parsed)
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("Failed to parse mood response", response=result["content"])
            return {"mood_emoji": "😐", "mood_explanation": user_input}
    
    async def extract_list_items(
        self, 
        user_input: str, 
        prompt_type: PromptType
    ) -> List[str]:
        """
        Extract list of items from user response.
        
        Args:
            user_input: User's response
            prompt_type: Type of list to extract (wins, learnings, etc.)
            
        Returns:
            List of extracted items
        """
        result = await self.process_text(
            prompt_type=prompt_type,
            user_input=user_input
        )
        
        logger.info("GPT list extraction result", prompt_type=prompt_type, user_input_length=len(user_input), 
                   response_content=result["content"][:200] + "..." if len(result["content"]) > 200 else result["content"])
        
        try:
            parsed = json.loads(result["content"])
            if isinstance(parsed, list):
                items = [item.strip() for item in parsed if item.strip()]
                logger.info("Successfully parsed list", prompt_type=prompt_type, item_count=len(items))
                return items
            else:
                logger.warning("Expected list response", prompt_type=prompt_type, response=result["content"])
                return []
        except json.JSONDecodeError as e:
            logger.warning("Failed to parse list response", prompt_type=prompt_type, response=result["content"], error=str(e))
            # Fallback: split by lines/bullets
            fallback_items = self._fallback_list_extraction(result["content"])
            logger.info("Using fallback extraction", prompt_type=prompt_type, item_count=len(fallback_items))
            return fallback_items
    
    async def extract_experiment(self, user_input: str) -> Dict[str, Any]:
        """
        Extract experiment information from user response.
        
        Args:
            user_input: User's experiment response
            
        Returns:
            Dictionary with experiment details
        """
        result = await self.process_text(
            prompt_type=PromptType.EXPERIMENT_PROCESSING,
            user_input=user_input
        )
        
        try:
            parsed = json.loads(result["content"])
            return self._validate_experiment_response(parsed)
        except (json.JSONDecodeError, KeyError):
            logger.warning("Failed to parse experiment response", response=result["content"])
            return {"experiment": user_input}
    
    def _calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """Calculate estimated cost for GPT-4o-mini usage."""
        # GPT-4o-mini pricing (as of 2024): $0.00015 per 1K prompt tokens, $0.0006 per 1K completion tokens
        prompt_cost = (prompt_tokens / 1000) * 0.00015
        completion_cost = (completion_tokens / 1000) * 0.0006
        return prompt_cost + completion_cost
    
    def _validate_energy_response(self, parsed: Dict[str, Any]) -> Dict[str, Any]:
        """Validate energy level response format."""
        energy_level = parsed.get("energy_level")
        
        # Validate energy level is 1-5
        if not isinstance(energy_level, int) or not (1 <= energy_level <= 5):
            raise GPTResponseValidationError(f"Invalid energy level: {energy_level}")
        
        return {
            "energy_level": energy_level,
            "explanation": parsed.get("explanation", "")
        }
    
    def _validate_mood_response(self, parsed: Dict[str, Any]) -> Dict[str, Any]:
        """Validate mood response format."""
        mood_emoji = parsed.get("mood_emoji", "😐")
        mood_explanation = parsed.get("mood_explanation", "")
        
        return {
            "mood_emoji": mood_emoji,
            "mood_explanation": mood_explanation
        }
    
    def _validate_experiment_response(self, parsed: Dict[str, Any]) -> Dict[str, Any]:
        """Validate experiment response format."""
        if not parsed:
            return {}
        
        return {
            "experiment": parsed.get("experiment", ""),
            "expected_outcome": parsed.get("expected_outcome", ""),
            "success_criteria": parsed.get("success_criteria", "")
        }
    
    def _fallback_energy_extraction(self, text: str) -> Dict[str, Any]:
        """Fallback method to extract energy level from text."""
        import re
        
        # Look for numbers 1-5
        numbers = re.findall(r'\b[1-5]\b', text)
        
        if numbers:
            energy_level = int(numbers[0])
            return {
                "energy_level": energy_level,
                "explanation": text
            }
        
        # Default to middle value
        return {
            "energy_level": 3,
            "explanation": text
        }
    
    def _fallback_list_extraction(self, text: str) -> List[str]:
        """Fallback method to extract list items from text."""
        import re
        
        # Split by lines and clean up
        lines = text.split('\n')
        items = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Remove bullet points and numbers
            line = re.sub(r'^[-•*\d+\.)\s]+', '', line).strip()
            
            if line:
                items.append(line)
        
        return items
    
    async def batch_process(
        self,
        requests: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Process multiple requests in batch for efficiency.
        
        Args:
            requests: List of request dictionaries with prompt_type and user_input
            
        Returns:
            List of results in same order as requests
        """
        tasks = []
        
        for req in requests:
            task = self.process_text(
                prompt_type=req["prompt_type"],
                user_input=req["user_input"],
                additional_context=req.get("additional_context"),
                custom_template=req.get("custom_template")
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Convert exceptions to error results
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append({
                    "error": str(result),
                    "request_index": i,
                    "success": False
                })
            else:
                result["success"] = True
                processed_results.append(result)
        
        return processed_results
    
    async def generate_daily_todo(
        self,
        next_actions_text: str,
        mits_text: str
    ) -> Dict[str, Any]:
        """
        Generate daily todo lists from retro sections.
        
        Args:
            next_actions_text: Text from Next Actions section
            mits_text: Text from Tomorrow's MITs section
            
        Returns:
            Dictionary with next_actions_todos and mits_todos lists
        """
        result = await self.process_text(
            prompt_type=PromptType.TODO_GENERATION,
            user_input="",  # Not used for this template
            additional_context={
                "next_actions_text": next_actions_text or "",
                "mits_text": mits_text or ""
            }
        )
        
        try:
            parsed = json.loads(result["content"])
            return self._validate_todo_response(parsed)
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("Failed to parse todo response", response=result["content"], error=str(e))
            # Fallback: create empty lists
            return {
                "next_actions_todos": [],
                "mits_todos": [],
                "parse_error": True
            }
    
    def _validate_todo_response(self, parsed: Dict[str, Any]) -> Dict[str, Any]:
        """Validate todo response format."""
        next_actions_todos = parsed.get("next_actions_todos", [])
        mits_todos = parsed.get("mits_todos", [])
        
        # Ensure they are lists
        if not isinstance(next_actions_todos, list):
            next_actions_todos = []
        if not isinstance(mits_todos, list):
            mits_todos = []
        
        # Clean up the lists (remove empty strings, limit MITs to 3)
        next_actions_todos = [item.strip() for item in next_actions_todos if item and item.strip()]
        mits_todos = [item.strip() for item in mits_todos[:3] if item and item.strip()]  # Limit to 3 MITs
        
        return {
            "next_actions_todos": next_actions_todos,
            "mits_todos": mits_todos,
            "parse_error": False
        }
    
    async def get_usage_stats(self) -> Dict[str, Any]:
        """Get usage statistics (placeholder for future implementation)."""
        return {
            "total_requests": 0,
            "total_tokens": 0,
            "total_cost": 0.0,
            "templates_used": {}
        }


# Global GPT service instance
gpt_service = GPTService()