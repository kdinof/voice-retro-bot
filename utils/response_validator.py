"""Response validation utilities for GPT outputs and user inputs."""

from __future__ import annotations
import json
import re
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass

import structlog


logger = structlog.get_logger()


@dataclass
class ValidationResult:
    """Result of validation operation."""
    is_valid: bool
    cleaned_data: Any = None
    error_message: str = ""
    warnings: List[str] = None
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


class ResponseValidator:
    """Validates and cleans GPT responses and user inputs."""
    
    def __init__(self):
        self.emoji_pattern = re.compile(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\U00002600-\U000027BF\U0001F900-\U0001F9FF]')
    
    def validate_json_response(self, response: str, expected_schema: Optional[Dict] = None) -> ValidationResult:
        """
        Validate JSON response from GPT.
        
        Args:
            response: GPT response string
            expected_schema: Optional schema to validate against
            
        Returns:
            ValidationResult with parsed data or error
        """
        try:
            # Clean response - remove markdown code blocks if present
            cleaned_response = self._clean_json_response(response)
            
            # Parse JSON
            parsed_data = json.loads(cleaned_response)
            
            # Schema validation if provided
            if expected_schema:
                validation_errors = self._validate_schema(parsed_data, expected_schema)
                if validation_errors:
                    return ValidationResult(
                        is_valid=False,
                        error_message=f"Schema validation failed: {', '.join(validation_errors)}"
                    )
            
            return ValidationResult(
                is_valid=True,
                cleaned_data=parsed_data
            )
            
        except json.JSONDecodeError as e:
            logger.warning("Invalid JSON response", response=response[:200], error=str(e))
            return ValidationResult(
                is_valid=False,
                error_message=f"Invalid JSON: {str(e)}"
            )
    
    def validate_energy_level(self, data: Union[int, str, Dict]) -> ValidationResult:
        """
        Validate energy level data.
        
        Args:
            data: Energy level data (int, str, or dict)
            
        Returns:
            ValidationResult with validated energy data
        """
        try:
            if isinstance(data, dict):
                energy_level = data.get("energy_level")
                explanation = data.get("explanation", "")
            elif isinstance(data, (int, str)):
                energy_level = int(data)
                explanation = ""
            else:
                return ValidationResult(
                    is_valid=False,
                    error_message="Invalid energy level format"
                )
            
            # Validate range
            if not isinstance(energy_level, int) or not (1 <= energy_level <= 5):
                return ValidationResult(
                    is_valid=False,
                    error_message=f"Energy level must be 1-5, got: {energy_level}"
                )
            
            return ValidationResult(
                is_valid=True,
                cleaned_data={
                    "energy_level": energy_level,
                    "explanation": str(explanation).strip()
                }
            )
            
        except (ValueError, TypeError) as e:
            return ValidationResult(
                is_valid=False,
                error_message=f"Energy level validation failed: {str(e)}"
            )
    
    def validate_mood_data(self, data: Dict) -> ValidationResult:
        """
        Validate mood data.
        
        Args:
            data: Mood data dictionary
            
        Returns:
            ValidationResult with validated mood data
        """
        try:
            mood_emoji = data.get("mood_emoji", "")
            mood_explanation = data.get("mood_explanation", "")
            
            warnings = []
            
            # Validate emoji
            if not mood_emoji:
                mood_emoji = "😐"  # Default neutral emoji
                warnings.append("No mood emoji provided, using default")
            elif not self._is_valid_emoji(mood_emoji):
                warnings.append(f"Invalid emoji format: {mood_emoji}")
            
            # Clean explanation
            mood_explanation = str(mood_explanation).strip()
            if len(mood_explanation) > 500:
                mood_explanation = mood_explanation[:500] + "..."
                warnings.append("Mood explanation truncated to 500 characters")
            
            return ValidationResult(
                is_valid=True,
                cleaned_data={
                    "mood_emoji": mood_emoji,
                    "mood_explanation": mood_explanation
                },
                warnings=warnings
            )
            
        except Exception as e:
            return ValidationResult(
                is_valid=False,
                error_message=f"Mood validation failed: {str(e)}"
            )
    
    def validate_list_items(self, data: Union[List, str], max_items: int = 10) -> ValidationResult:
        """
        Validate list of items (wins, learnings, etc.).
        
        Args:
            data: List data or string
            max_items: Maximum number of items allowed
            
        Returns:
            ValidationResult with validated list
        """
        try:
            if isinstance(data, str):
                # Try to parse as JSON first
                try:
                    data = json.loads(data)
                except json.JSONDecodeError:
                    # Split by lines as fallback
                    data = [line.strip() for line in data.split('\n') if line.strip()]
            
            if not isinstance(data, list):
                return ValidationResult(
                    is_valid=False,
                    error_message="Expected list format"
                )
            
            warnings = []
            cleaned_items = []
            
            for i, item in enumerate(data):
                if i >= max_items:
                    warnings.append(f"Too many items, truncated to {max_items}")
                    break
                
                # Clean item
                cleaned_item = str(item).strip()
                
                # Remove bullet points and numbers
                cleaned_item = re.sub(r'^[-•*\d+\.)\s]+', '', cleaned_item).strip()
                
                if cleaned_item:
                    # Limit item length
                    if len(cleaned_item) > 200:
                        cleaned_item = cleaned_item[:200] + "..."
                        warnings.append(f"Item {i+1} truncated to 200 characters")
                    
                    cleaned_items.append(cleaned_item)
            
            return ValidationResult(
                is_valid=True,
                cleaned_data=cleaned_items,
                warnings=warnings
            )
            
        except Exception as e:
            return ValidationResult(
                is_valid=False,
                error_message=f"List validation failed: {str(e)}"
            )
    
    def validate_experiment_data(self, data: Dict) -> ValidationResult:
        """
        Validate experiment data.
        
        Args:
            data: Experiment data dictionary
            
        Returns:
            ValidationResult with validated experiment data
        """
        try:
            if not data or not isinstance(data, dict):
                return ValidationResult(
                    is_valid=True,
                    cleaned_data={}  # Empty experiment is valid
                )
            
            experiment = str(data.get("experiment", "")).strip()
            expected_outcome = str(data.get("expected_outcome", "")).strip()
            success_criteria = str(data.get("success_criteria", "")).strip()
            
            warnings = []
            
            # Validate field lengths
            if len(experiment) > 500:
                experiment = experiment[:500] + "..."
                warnings.append("Experiment description truncated to 500 characters")
            
            if len(expected_outcome) > 300:
                expected_outcome = expected_outcome[:300] + "..."
                warnings.append("Expected outcome truncated to 300 characters")
            
            if len(success_criteria) > 300:
                success_criteria = success_criteria[:300] + "..."
                warnings.append("Success criteria truncated to 300 characters")
            
            cleaned_data = {}
            if experiment:
                cleaned_data["experiment"] = experiment
            if expected_outcome:
                cleaned_data["expected_outcome"] = expected_outcome
            if success_criteria:
                cleaned_data["success_criteria"] = success_criteria
            
            return ValidationResult(
                is_valid=True,
                cleaned_data=cleaned_data,
                warnings=warnings
            )
            
        except Exception as e:
            return ValidationResult(
                is_valid=False,
                error_message=f"Experiment validation failed: {str(e)}"
            )
    
    def validate_user_input(self, text: str, max_length: int = 2000) -> ValidationResult:
        """
        Validate user input text.
        
        Args:
            text: User input text
            max_length: Maximum allowed length
            
        Returns:
            ValidationResult with validated text
        """
        try:
            if not text or not isinstance(text, str):
                return ValidationResult(
                    is_valid=False,
                    error_message="Empty or invalid input"
                )
            
            # Clean and validate
            cleaned_text = text.strip()
            warnings = []
            
            if not cleaned_text:
                return ValidationResult(
                    is_valid=False,
                    error_message="Input is empty after cleaning"
                )
            
            # Length validation
            if len(cleaned_text) > max_length:
                cleaned_text = cleaned_text[:max_length] + "..."
                warnings.append(f"Input truncated to {max_length} characters")
            
            # Check for suspicious content
            if self._contains_suspicious_content(cleaned_text):
                warnings.append("Input contains potentially suspicious content")
            
            return ValidationResult(
                is_valid=True,
                cleaned_data=cleaned_text,
                warnings=warnings
            )
            
        except Exception as e:
            return ValidationResult(
                is_valid=False,
                error_message=f"Input validation failed: {str(e)}"
            )
    
    def _clean_json_response(self, response: str) -> str:
        """Clean JSON response by removing markdown and extra text."""
        # Remove markdown code blocks
        response = re.sub(r'```json\s*', '', response)
        response = re.sub(r'```\s*', '', response)
        
        # Try to extract JSON object/array
        json_match = re.search(r'[\{\[].*[\}\]]', response, re.DOTALL)
        if json_match:
            return json_match.group(0)
        
        return response.strip()
    
    def _validate_schema(self, data: Any, schema: Dict) -> List[str]:
        """Basic schema validation."""
        errors = []
        
        if not isinstance(data, dict):
            errors.append("Expected object format")
            return errors
        
        # Check required fields
        required_fields = schema.get("required", [])
        for field in required_fields:
            if field not in data:
                errors.append(f"Missing required field: {field}")
        
        # Check field types
        properties = schema.get("properties", {})
        for field, field_schema in properties.items():
            if field in data:
                expected_type = field_schema.get("type")
                if expected_type and not self._check_type(data[field], expected_type):
                    errors.append(f"Invalid type for {field}: expected {expected_type}")
        
        return errors
    
    def _check_type(self, value: Any, expected_type: str) -> bool:
        """Check if value matches expected type."""
        type_mapping = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict
        }
        
        expected_python_type = type_mapping.get(expected_type)
        if expected_python_type:
            return isinstance(value, expected_python_type)
        
        return True
    
    def _is_valid_emoji(self, text: str) -> bool:
        """Check if text contains valid emoji."""
        return bool(self.emoji_pattern.search(text))
    
    def _contains_suspicious_content(self, text: str) -> bool:
        """Check for potentially suspicious content."""
        suspicious_patterns = [
            r'<script',
            r'javascript:',
            r'data:',
            r'eval\(',
            r'exec\(',
            r'system\(',
            r'subprocess\.',
            r'__import__'
        ]
        
        for pattern in suspicious_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        
        return False


# Global validator instance
response_validator = ResponseValidator()