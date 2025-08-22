"""Prompt template management for GPT interactions."""

from __future__ import annotations
from typing import Dict, Any, Optional
from enum import Enum
from dataclasses import dataclass

import structlog


logger = structlog.get_logger()


class PromptType(str, Enum):
    """Types of prompts for different processing needs."""
    ENERGY_PROCESSING = "energy_processing"
    MOOD_PROCESSING = "mood_processing"
    WINS_PROCESSING = "wins_processing"
    LEARNINGS_PROCESSING = "learnings_processing"
    ACTIONS_PROCESSING = "actions_processing"
    MITS_PROCESSING = "mits_processing"
    EXPERIMENT_PROCESSING = "experiment_processing"
    TODO_GENERATION = "todo_generation"


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

Извлеки из ответа пользователя ВСЕ положительные события, достижения, победы и хорошие моменты дня.
Это может быть:
- Завершенные задачи и проекты
- Хорошие привычки (сон, еда, спорт, прогулки)  
- Время с семьей и друзьями
- Новые знания и навыки
- Личные достижения любого размера
- Просто хорошие моменты дня

ВАЖНО: Обрабатывай неформальную разговорную речь. Пользователь может сказать "поспал", "позавтракал", "погулял с сыном" - это все считается победами!

Структурируй каждую победу как отдельный понятный пункт.

Верни ТОЛЬКО JSON массив строк:
[
  "Хорошо поспал",
  "Отлично позавтракал", 
  "Погулял с сыном"
]

Если побед действительно нет, верни пустой массив [].""",
            user_prompt_template="Извлеки ВСЕ победы и положительные моменты дня из этого ответа:\n\n{user_input}",
            description="Extract wins from user response",
            max_tokens=300,
            temperature=0.2
        )
        
        # Learnings processing
        self.templates[PromptType.LEARNINGS_PROCESSING] = PromptTemplate(
            name="learnings_processing", 
            system_prompt="""Ты ассистент для структурирования уроков дня в ежедневных ретроспективах.

Извлеки из ответа пользователя ВСЕ уроки, инсайты, новые знания и навыки.
Это может быть:
- Новые знания и навыки
- Понимания о себе или других
- Жизненные уроки
- Инсайты о работе или отношениях
- Даже простые навыки ("научился спать", "научился играться с сыном")

ВАЖНО: Обрабатывай неформальную разговорную речь. "Научился спать", "научился завтракать" - это тоже обучение!

Структурируй каждый урок как отдельный понятный пункт.

Верни ТОЛЬКО JSON массив строк:
[
  "Важность качественного сна",
  "Как проводить время с семьей",
  "Новый способ решения задач"
]

Если уроков действительно нет, верни пустой массив [].""",
            user_prompt_template="Извлеки ВСЕ уроки и новые знания из этого ответа:\n\n{user_input}",
            description="Extract learnings from user response",
            max_tokens=300,
            temperature=0.2
        )
        
        # Next actions processing
        self.templates[PromptType.ACTIONS_PROCESSING] = PromptTemplate(
            name="actions_processing",
            system_prompt="""Ты ассистент для структурирования планов на завтра в ежедневных ретроспективах.

Извлеки из ответа пользователя ВСЕ действия, планы и задачи на завтра или будущее.
Это может быть:
- Рабочие задачи и проекты
- Личные дела и планы
- Встречи и мероприятия
- Обычные дела ("работа", "всякая всячина")
- Семейные планы
- Спорт и хобби

ВАЖНО: Обрабатывай неформальную разговорную речь. "У меня работа", "всякая всячина" - тоже планы!

Структурируй каждое действие как отдельный понятный пункт.

Верни ТОЛЬКО JSON массив строк:
[
  "Идти на работу",
  "Заниматься текущими делами",
  "Встреча с командой"
]

Если планов действительно нет, верни пустой массив [].""",
            user_prompt_template="Извлеки ВСЕ планы и действия на завтра из этого ответа:\n\n{user_input}",
            description="Extract next actions from user response",
            max_tokens=300,
            temperature=0.2
        )
        
        # MITs (Most Important Tasks) processing
        self.templates[PromptType.MITS_PROCESSING] = PromptTemplate(
            name="mits_processing",
            system_prompt="""Ты ассистент для определения главных задач завтра в ежедневных ретроспективах.

Извлеки из ответа пользователя 1-3 самые важные задачи на завтра (MITs).
Это могут быть:
- Ключевые рабочие задачи
- Важные личные дела  
- Приоритетные проекты
- Важные встречи или события
- Спорт и здоровье (если упомянуто как важное)

ВАЖНО: Обрабатывай неформальную разговорную речь. "Кроссфит", "работа" - если упомянуто как важное, включай!

Верни ТОЛЬКО JSON массив строк (максимум 3 элемента):
[
  "Заняться кроссфитом",
  "Выполнить рабочие задачи",
  "Важные личные дела"
]

Если важных задач действительно нет, верни пустой массив [].""",
            user_prompt_template="Определи 1-3 САМЫЕ ВАЖНЫЕ задачи завтра из этого ответа:\n\n{user_input}",
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
        
        # Todo generation from retro
        self.templates[PromptType.TODO_GENERATION] = PromptTemplate(
            name="todo_generation",
            system_prompt="""Ты ассистент для создания списка дел на основе завершенной ретроспективы.

Проанализируй секции "Next Actions" и "Tomorrow's MITs" из ретроспективы и создай структурированный список дел.

ВАЖНО:
- Обрабатывай неформальную разговорную речь
- Преобразуй общие фразы в конкретные задачи
- "Работа" -> "Заниматься рабочими делами"
- "Всякая всячина" -> "Выполнить текущие дела"
- "Кроссфит" -> "Заняться кроссфитом"

Создай ДВА отдельных списка:
1. Из секции "Next Actions" - все запланированные дела
2. Из секции "Tomorrow's MITs" - самые важные задачи (максимум 3)

Верни ТОЛЬКО JSON в формате:
{
  "next_actions_todos": [
    "Заниматься рабочими делами",
    "Выполнить текущие дела",
    "Встретиться с командой"
  ],
  "mits_todos": [
    "Заняться кроссфитом", 
    "Завершить важный проект",
    "Провести встречу с клиентом"
  ]
}

Если в какой-то секции нет дел, верни пустой массив [].""",
            user_prompt_template="Создай списки дел из этой ретроспективы:\n\nNext Actions:\n{next_actions_text}\n\nTomorrow's MITs:\n{mits_text}",
            description="Generate todo lists from retro sections",
            max_tokens=400,
            temperature=0.2
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