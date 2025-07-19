"""Prompt template management for GPT interactions."""

from __future__ import annotations
from typing import Dict, Any, Optional
from enum import Enum
from dataclasses import dataclass

import structlog


logger = structlog.get_logger()


class PromptType(str, Enum):
    """Types of prompts for different processing needs."""
    TEXT_CLEANING = "text_cleaning"
    RETRO_STRUCTURING = "retro_structuring"
    ENERGY_PROCESSING = "energy_processing"
    MOOD_PROCESSING = "mood_processing"
    WINS_PROCESSING = "wins_processing"
    LEARNINGS_PROCESSING = "learnings_processing"
    ACTIONS_PROCESSING = "actions_processing"
    MITS_PROCESSING = "mits_processing"
    EXPERIMENT_PROCESSING = "experiment_processing"


@dataclass
class PromptTemplate:
    """Template for GPT prompts with metadata."""
    name: str
    system_prompt: str
    user_prompt_template: str
    version: str = "1.0"
    description: str = ""
    max_tokens: int = 1000
    temperature: float = 0.3
    
    def format_user_prompt(self, **kwargs) -> str:
        """Format user prompt template with provided variables."""
        try:
            return self.user_prompt_template.format(**kwargs)
        except KeyError as e:
            logger.error("Missing template variable", template=self.name, missing_var=str(e))
            raise ValueError(f"Missing template variable: {e}")


class PromptTemplateManager:
    """Manages prompt templates for different text processing tasks."""
    
    def __init__(self):
        self.templates: Dict[PromptType, PromptTemplate] = {}
        self._initialize_templates()
    
    def _initialize_templates(self):
        """Initialize all prompt templates."""
        
        # Text cleaning template
        self.templates[PromptType.TEXT_CLEANING] = PromptTemplate(
            name="text_cleaning",
            system_prompt="""Ты полезный ассистент, который структурирует и очищает текст для ежедневных ретроспектив.

Твоя задача:
- Исправить грамматику, орфографию и пунктуацию
- Убрать словесные паразиты (эм, ах, ну, значит, etc.)
- Убрать ложные старты и повторы
- Сохранить оригинальный язык (русский)
- НЕ добавлять вступительные фразы
- НЕ добавлять объяснения или комментарии
- Вернуть только очищенный текст""",
            user_prompt_template="Очисти этот текст от расшифровки речи:\n\n{raw_text}",
            description="Clean and structure transcribed speech text",
            max_tokens=500,
            temperature=0.1
        )
        
        # Energy level processing
        self.templates[PromptType.ENERGY_PROCESSING] = PromptTemplate(
            name="energy_processing",
            system_prompt="""Ты ассистент для анализа уровня энергии в ежедневных ретроспективах.

Анализируй ответ пользователя и извлеки:
1. Числовой уровень энергии (1-5)
2. Краткое объяснение (если есть)

Верни ТОЛЬКО JSON в формате:
{
  "energy_level": 4,
  "explanation": "краткое объяснение"
}

Если уровень не указан явно, определи его по тону и содержанию.""",
            user_prompt_template="Проанализируй уровень энергии из этого ответа:\n\n{user_input}",
            description="Extract energy level from user response",
            max_tokens=200,
            temperature=0.2
        )
        
        # Mood processing  
        self.templates[PromptType.MOOD_PROCESSING] = PromptTemplate(
            name="mood_processing",
            system_prompt="""Ты ассистент для анализа настроения в ежедневных ретроспективах.

Анализируй ответ пользователя и извлеки:
1. Эмодзи настроения (один символ)
2. Краткое объяснение настроения

Верни ТОЛЬКО JSON в формате:
{
  "mood_emoji": "😊",
  "mood_explanation": "краткое объяснение настроения"
}

Используй подходящие эмодзи: 😊😌😐😔😤😴🤔💪🎉😎""",
            user_prompt_template="Определи настроение из этого ответа:\n\n{user_input}",
            description="Extract mood from user response",
            max_tokens=200,
            temperature=0.3
        )
        
        # Wins processing
        self.templates[PromptType.WINS_PROCESSING] = PromptTemplate(
            name="wins_processing",
            system_prompt="""Ты ассистент для структурирования побед дня в ежедневных ретроспективах.

Извлеки из ответа пользователя все победы и достижения дня.
Структурируй каждую победу как отдельный пункт.

Верни ТОЛЬКО JSON массив строк:
[
  "Завершил важный проект",
  "Выучил новую технологию",
  "Помог коллеге с задачей"
]

Если побед нет, верни пустой массив [].""",
            user_prompt_template="Извлеки победы дня из этого ответа:\n\n{user_input}",
            description="Extract wins from user response",
            max_tokens=300,
            temperature=0.2
        )
        
        # Learnings processing
        self.templates[PromptType.LEARNINGS_PROCESSING] = PromptTemplate(
            name="learnings_processing", 
            system_prompt="""Ты ассистент для структурирования уроков дня в ежедневных ретроспективах.

Извлеки из ответа пользователя все уроки, инсайты и новые знания.
Структурируй каждый урок как отдельный пункт.

Верни ТОЛЬКО JSON массив строк:
[
  "Важность планирования времени",
  "Новый способ решения задач",
  "Понимание команды"
]

Если уроков нет, верни пустой массив [].""",
            user_prompt_template="Извлеки уроки дня из этого ответа:\n\n{user_input}",
            description="Extract learnings from user response",
            max_tokens=300,
            temperature=0.2
        )
        
        # Next actions processing
        self.templates[PromptType.ACTIONS_PROCESSING] = PromptTemplate(
            name="actions_processing",
            system_prompt="""Ты ассистент для структурирования планов на завтра в ежедневных ретроспективах.

Извлеки из ответа пользователя все действия и планы на завтра.
Структурируй каждое действие как отдельный пункт.

Верни ТОЛЬКО JSON массив строк:
[
  "Закончить документацию",
  "Встреча с командой в 10:00",
  "Изучить новую библиотеку"
]

Если планов нет, верни пустой массив [].""",
            user_prompt_template="Извлеки планы на завтра из этого ответа:\n\n{user_input}",
            description="Extract next actions from user response",
            max_tokens=300,
            temperature=0.2
        )
        
        # MITs (Most Important Tasks) processing
        self.templates[PromptType.MITS_PROCESSING] = PromptTemplate(
            name="mits_processing",
            system_prompt="""Ты ассистент для определения главных задач завтра в ежедневных ретроспективах.

Извлеки из ответа пользователя 1-3 самые важные задачи на завтра (MITs).
Это должны быть приоритетные задачи, которые принесут максимальную пользу.

Верни ТОЛЬКО JSON массив строк (максимум 3 элемента):
[
  "Завершить ключевую функцию продукта",
  "Подготовить презентацию для руководства"
]

Если важных задач нет, верни пустой массив [].""",
            user_prompt_template="Определи 1-3 главные задачи завтра из этого ответа:\n\n{user_input}",
            description="Extract most important tasks from user response",
            max_tokens=200,
            temperature=0.2
        )
        
        # Experiment processing
        self.templates[PromptType.EXPERIMENT_PROCESSING] = PromptTemplate(
            name="experiment_processing",
            system_prompt="""Ты ассистент для структурирования экспериментов в ежедневных ретроспективах.

Извлеки из ответа пользователя информацию об эксперименте:
- Что хочет попробовать
- Ожидаемый результат
- Как будет измерять успех

Верни ТОЛЬКО JSON в формате:
{
  "experiment": "описание эксперимента", 
  "expected_outcome": "ожидаемый результат",
  "success_criteria": "критерии успеха"
}

Если эксперимента нет, верни пустой объект {}.""",
            user_prompt_template="Структурируй эксперимент из этого ответа:\n\n{user_input}",
            description="Extract experiment from user response",
            max_tokens=300,
            temperature=0.3
        )
        
        logger.info("Initialized prompt templates", count=len(self.templates))
    
    def get_template(self, prompt_type: PromptType) -> PromptTemplate:
        """Get prompt template by type."""
        if prompt_type not in self.templates:
            raise ValueError(f"Unknown prompt type: {prompt_type}")
        
        return self.templates[prompt_type]
    
    def get_all_templates(self) -> Dict[PromptType, PromptTemplate]:
        """Get all available templates."""
        return self.templates.copy()
    
    def add_custom_template(self, prompt_type: PromptType, template: PromptTemplate):
        """Add or update a custom template."""
        self.templates[prompt_type] = template
        logger.info("Added custom template", type=prompt_type, name=template.name)
    
    def validate_template_variables(self, prompt_type: PromptType, **kwargs) -> bool:
        """Validate that all required template variables are provided."""
        template = self.get_template(prompt_type)
        
        try:
            template.format_user_prompt(**kwargs)
            return True
        except ValueError:
            return False
    
    def get_template_info(self, prompt_type: PromptType) -> Dict[str, Any]:
        """Get template information and metadata."""
        template = self.get_template(prompt_type)
        
        return {
            "name": template.name,
            "description": template.description,
            "version": template.version,
            "max_tokens": template.max_tokens,
            "temperature": template.temperature,
            "system_prompt_length": len(template.system_prompt),
            "user_template_length": len(template.user_prompt_template)
        }


# Global template manager instance
prompt_manager = PromptTemplateManager()