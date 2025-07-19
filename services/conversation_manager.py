"""Conversation flow manager for multi-step retrospective conversations."""

from __future__ import annotations
import asyncio
from datetime import datetime, timedelta, date
from typing import Optional, Dict, Any, Tuple

import structlog
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup

from models.conversation_state import ConversationState, RetroStep
from services.database_service import DatabaseService
from services.voice_processor import voice_processor
from services.text_processor import text_processor, RetroFieldType
from services.telegram_service import TelegramService


logger = structlog.get_logger()


class ConversationFlowError(Exception):
    """Raised when conversation flow encounters an error."""
    pass


class ConversationManager:
    """Manages multi-step retrospective conversations."""
    
    def __init__(self, database_service: DatabaseService, telegram_service: TelegramService):
        self.db = database_service
        self.telegram = telegram_service
        
        # Step configuration
        self.step_questions = {
            RetroStep.ENERGY: {
                "question": "🔋 **Как твой уровень энергии сегодня?**\n\nОцени от 1 до 5:\n• 1 - Очень низкий\n• 2 - Низкий\n• 3 - Средний\n• 4 - Высокий\n• 5 - Очень высокий",
                "hint": "💡 Отправь голосовое сообщение или напиши цифру с объяснением",
                "field_type": RetroFieldType.ENERGY
            },
            RetroStep.MOOD: {
                "question": "😊 **Какое у тебя настроение?**\n\nОпиши свое настроение и эмоции сегодня",
                "hint": "💡 Можешь использовать эмодзи и рассказать, что повлияло на настроение",
                "field_type": RetroFieldType.MOOD
            },
            RetroStep.WINS: {
                "question": "🏆 **Какие у тебя победы сегодня?**\n\nРасскажи о своих достижениях, больших и маленьких",
                "hint": "💡 Может быть завершенная задача, новое знание, помощь другим...",
                "field_type": RetroFieldType.WINS
            },
            RetroStep.LEARNINGS: {
                "question": "📚 **Чему ты научился сегодня?**\n\nКакие уроки или инсайты получил?",
                "hint": "💡 Новые знания, понимания, выводы из опыта...",
                "field_type": RetroFieldType.LEARNINGS
            },
            RetroStep.NEXT_ACTIONS: {
                "question": "🎯 **Что планируешь делать завтра?**\n\nКакие у тебя планы и задачи?",
                "hint": "💡 Конкретные действия, встречи, проекты...",
                "field_type": RetroFieldType.NEXT_ACTIONS
            },
            RetroStep.MITS: {
                "question": "⭐ **Какие 1-3 самые важные задачи завтра?**\n\nВыбери приоритетные задачи (MITs - Most Important Tasks)",
                "hint": "💡 Те задачи, которые принесут максимальную пользу",
                "field_type": RetroFieldType.MITS
            },
            RetroStep.EXPERIMENT: {
                "question": "🧪 **Хочешь попробовать что-то новое?**\n\nКакой эксперимент планируешь провести?",
                "hint": "💡 Новый подход, инструмент, привычка... Можешь пропустить",
                "field_type": RetroFieldType.EXPERIMENT,
                "optional": True
            }
        }
        
        # Step progression order
        self.step_order = [
            RetroStep.ENERGY,
            RetroStep.MOOD,
            RetroStep.WINS,
            RetroStep.LEARNINGS,
            RetroStep.NEXT_ACTIONS,
            RetroStep.MITS,
            RetroStep.EXPERIMENT,
            RetroStep.REVIEW,
            RetroStep.COMPLETED
        ]
    
    async def start_retro_conversation(self, user_id: int, chat_id: int) -> bool:
        """
        Start a new retrospective conversation.
        
        Args:
            user_id: Telegram user ID
            chat_id: Chat ID
            
        Returns:
            True if conversation started successfully
        """
        try:
            async for session in self.db.get_session():
                repos = await self.db.get_repositories(session)
                
                # Check if user has an active conversation
                existing_state = await repos.conversations.get_by_user_id(user_id)
                if existing_state and existing_state.is_active:
                    await self.telegram.send_message_with_retry(
                        chat_id=chat_id,
                        text="📝 У тебя уже есть активная ретроспектива!\n\n"
                             "Продолжим с того места, где остановились?"
                    )
                    await self._continue_conversation(user_id, chat_id)
                    return True
                
                # Get or create user
                user = await repos.users.create_or_update_from_telegram(
                    telegram_id=user_id
                )
                
                # Create new retro for today
                today = date.today()
                existing_retro = await repos.retros.get_by_user_and_date(user_id, today)
                
                if existing_retro and existing_retro.is_completed:
                    await self.telegram.send_message_with_retry(
                        chat_id=chat_id,
                        text="✅ Ты уже завершил ретроспективу на сегодня!\n\n"
                             "Хочешь посмотреть результат?",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("📄 Показать ретро", callback_data=f"show_retro_{existing_retro.id}")]
                        ])
                    )
                    return True
                
                if not existing_retro:
                    retro = await repos.retros.create_daily_retro(user_id, today)
                else:
                    retro = existing_retro
                
                # Create conversation state
                await repos.conversations.create_or_update_state(
                    user_id=user_id,
                    step=RetroStep.ENERGY,
                    retro_id=retro.id,
                    timeout_minutes=30
                )
                
                await repos.commit()
                
                # Send welcome message and start first question
                await self.telegram.send_message_with_retry(
                    chat_id=chat_id,
                    text="🎯 **Начинаем ретроспективу!**\n\n"
                         f"Дата: {today.strftime('%d.%m.%Y')}\n"
                         "Прогресс: 1/7 шагов\n\n"
                         "Отвечай голосовыми сообщениями или текстом. "
                         "В любой момент можешь написать /stop для остановки.",
                    parse_mode="Markdown"
                )
                
                # Ask first question
                await self._ask_current_question(user_id, chat_id)
                
                logger.info("Started retro conversation", user_id=user_id, retro_id=retro.id)
                return True
        
        except Exception as e:
            logger.error("Failed to start retro conversation", user_id=user_id, error=str(e))
            await self.telegram.send_message_with_retry(
                chat_id=chat_id,
                text="❌ Произошла ошибка при запуске ретроспективы. Попробуй еще раз позже."
            )
            return False
    
    async def handle_user_response(self, user_id: int, chat_id: int, message_text: str = "", voice_file_id: str = "") -> bool:
        """
        Handle user response in conversation flow.
        
        Args:
            user_id: Telegram user ID
            chat_id: Chat ID
            message_text: Text message from user
            voice_file_id: Voice message file ID
            
        Returns:
            True if response was processed successfully
        """
        try:
            async for session in self.db.get_session():
                repos = await self.db.get_repositories(session)
                
                # Get current conversation state
                state = await repos.conversations.get_by_user_id(user_id)
                if not state or not state.is_active:
                    await self.telegram.send_message_with_retry(
                        chat_id=chat_id,
                        text="❓ У тебя нет активной ретроспективы.\n\n"
                             "Начни новую с помощью /retro"
                    )
                    return False
                
                # Check if conversation expired
                if state.is_expired:
                    await self._handle_expired_conversation(user_id, chat_id)
                    return False
                
                # Get user input (voice or text)
                if voice_file_id:
                    user_input = await self._process_voice_input(voice_file_id, chat_id)
                    if not user_input:
                        return False
                else:
                    user_input = message_text.strip()
                
                if not user_input:
                    await self.telegram.send_message_with_retry(
                        chat_id=chat_id,
                        text="🤔 Не могу обработать пустой ответ. Попробуй еще раз!"
                    )
                    return False
                
                # Process response for current step
                await self._process_step_response(user_id, chat_id, state, user_input)
                
                return True
        
        except Exception as e:
            logger.error("Failed to handle user response", user_id=user_id, error=str(e))
            await self.telegram.send_message_with_retry(
                chat_id=chat_id,
                text="❌ Произошла ошибка при обработке ответа. Попробуй еще раз."
            )
            return False
    
    async def stop_conversation(self, user_id: int, chat_id: int) -> bool:
        """
        Stop current conversation.
        
        Args:
            user_id: Telegram user ID
            chat_id: Chat ID
            
        Returns:
            True if conversation was stopped
        """
        try:
            async for session in self.db.get_session():
                repos = await self.db.get_repositories(session)
                
                state = await repos.conversations.get_by_user_id(user_id)
                if not state or not state.is_active:
                    await self.telegram.send_message_with_retry(
                        chat_id=chat_id,
                        text="ℹ️ У тебя нет активной ретроспективы."
                    )
                    return False
                
                # Reset conversation state
                await repos.conversations.reset_conversation(user_id)
                await repos.commit()
                
                # Get current progress
                progress = self._get_step_progress(state.current_step)
                
                await self.telegram.send_message_with_retry(
                    chat_id=chat_id,
                    text=f"⏸️ **Ретроспектива остановлена**\n\n"
                         f"Прогресс: {progress[0]}/{progress[1]} шагов\n\n"
                         "Ты можешь продолжить позже с помощью /retro",
                    parse_mode="Markdown"
                )
                
                logger.info("Stopped conversation", user_id=user_id, step=state.current_step)
                return True
        
        except Exception as e:
            logger.error("Failed to stop conversation", user_id=user_id, error=str(e))
            return False
    
    async def _continue_conversation(self, user_id: int, chat_id: int):
        """Continue existing conversation."""
        async for session in self.db.get_session():
            repos = await self.db.get_repositories(session)
            
            state = await repos.conversations.get_by_user_id(user_id)
            if state and state.is_active:
                progress = self._get_step_progress(state.current_step)
                
                await self.telegram.send_message_with_retry(
                    chat_id=chat_id,
                    text=f"📝 **Продолжаем ретроспективу**\n\n"
                         f"Прогресс: {progress[0]}/{progress[1]} шагов\n\n"
                         "Отвечаем на следующий вопрос:",
                    parse_mode="Markdown"
                )
                
                await self._ask_current_question(user_id, chat_id)
    
    async def _ask_current_question(self, user_id: int, chat_id: int):
        """Ask current question based on conversation state."""
        async for session in self.db.get_session():
            repos = await self.db.get_repositories(session)
            
            state = await repos.conversations.get_by_user_id(user_id)
            if not state:
                return
            
            if state.current_step == RetroStep.REVIEW:
                await self._show_retro_review(user_id, chat_id)
                return
            
            if state.current_step == RetroStep.COMPLETED:
                await self._complete_retro(user_id, chat_id)
                return
            
            step_config = self.step_questions.get(state.current_step)
            if not step_config:
                logger.error("Unknown step", step=state.current_step)
                return
            
            progress = self._get_step_progress(state.current_step)
            
            # Create skip button for optional questions
            keyboard = None
            if step_config.get("optional"):
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("⏭️ Пропустить", callback_data="skip_step")]
                ])
            
            message_text = (
                f"**Шаг {progress[0]}/{progress[1]}**\n\n"
                f"{step_config['question']}\n\n"
                f"{step_config['hint']}"
            )
            
            await self.telegram.send_message_with_retry(
                chat_id=chat_id,
                text=message_text,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
    
    async def _process_voice_input(self, voice_file_id: str, chat_id: int) -> Optional[str]:
        """Process voice input and return transcribed text."""
        try:
            # Process voice message
            result = await voice_processor.process_telegram_voice(
                bot=self.telegram.bot,
                file_id=voice_file_id,
                chat_id=chat_id,
                language="ru"
            )
            
            if result.success:
                return result.transcribed_text
            else:
                await self.telegram.send_message_with_retry(
                    chat_id=chat_id,
                    text=f"❌ {result.error_message}\n\nПопробуй отправить текстом."
                )
                return None
        
        except Exception as e:
            logger.error("Voice processing failed", error=str(e))
            await self.telegram.send_message_with_retry(
                chat_id=chat_id,
                text="❌ Не удалось обработать голосовое сообщение. Попробуй отправить текстом."
            )
            return None
    
    async def _process_step_response(self, user_id: int, chat_id: int, state: ConversationState, user_input: str):
        """Process user response for current step."""
        async for session in self.db.get_session():
            repos = await self.db.get_repositories(session)
            
            step_config = self.step_questions.get(state.current_step)
            if not step_config:
                return
            
            field_type = step_config["field_type"]
            
            # Process input with GPT
            processing_result = await text_processor.process_retro_field(
                field_type=field_type,
                user_input=user_input
            )
            
            if processing_result.success:
                # Save processed data to retro
                await self._save_field_data(repos, state.current_retro_id, field_type, processing_result.processed_data)
                
                # Show confirmation
                summary = text_processor.get_field_summary(processing_result, field_type)
                await self.telegram.send_message_with_retry(
                    chat_id=chat_id,
                    text=f"✅ {summary}\n\n_Переходим к следующему шагу..._",
                    parse_mode="Markdown"
                )
                
                # Move to next step
                await self._advance_conversation_step(user_id, chat_id, state)
            
            else:
                await self.telegram.send_message_with_retry(
                    chat_id=chat_id,
                    text=f"⚠️ Не удалось обработать ответ: {processing_result.error_message}\n\n"
                         "Попробуй ответить по-другому."
                )
    
    async def _save_field_data(self, repos, retro_id: int, field_type: RetroFieldType, processed_data: Dict[str, Any]):
        """Save processed field data to retro."""
        if field_type == RetroFieldType.ENERGY:
            energy_data = processed_data.get("energy_data", {})
            await repos.retros.update_retro_field(retro_id, "energy_level", energy_data.get("energy_level"))
            if energy_data.get("explanation"):
                await repos.retros.set_temp_data(retro_id, "energy_explanation", energy_data["explanation"])
        
        elif field_type == RetroFieldType.MOOD:
            mood_data = processed_data.get("mood_data", {})
            await repos.retros.update_retro_field(retro_id, "mood", mood_data.get("mood_emoji"))
            await repos.retros.update_retro_field(retro_id, "mood_explanation", mood_data.get("mood_explanation"))
        
        elif field_type == RetroFieldType.WINS:
            wins_list = processed_data.get("wins_list", [])
            await repos.retros.update_retro_field(retro_id, "wins", wins_list)
        
        elif field_type == RetroFieldType.LEARNINGS:
            learnings_list = processed_data.get("learnings_list", [])
            await repos.retros.update_retro_field(retro_id, "learnings", learnings_list)
        
        elif field_type == RetroFieldType.NEXT_ACTIONS:
            actions_list = processed_data.get("next_actions_list", [])
            await repos.retros.update_retro_field(retro_id, "next_actions", actions_list)
        
        elif field_type == RetroFieldType.MITS:
            mits_list = processed_data.get("mits_list", [])
            await repos.retros.update_retro_field(retro_id, "mits", mits_list)
        
        elif field_type == RetroFieldType.EXPERIMENT:
            experiment_data = processed_data.get("experiment_data", {})
            await repos.retros.update_retro_field(retro_id, "experiment", experiment_data)
        
        await repos.commit()
    
    async def _advance_conversation_step(self, user_id: int, chat_id: int, state: ConversationState):
        """Advance to next conversation step."""
        async for session in self.db.get_session():
            repos = await self.db.get_repositories(session)
            
            # Get next step
            next_step = self._get_next_step(state.current_step)
            
            if next_step:
                # Update conversation state
                await repos.conversations.update_step(user_id, next_step)
                await repos.commit()
                
                # Small delay before next question
                await asyncio.sleep(1)
                
                # Ask next question
                await self._ask_current_question(user_id, chat_id)
            else:
                # Conversation complete
                await self._complete_retro(user_id, chat_id)
    
    async def _show_retro_review(self, user_id: int, chat_id: int):
        """Show retro review before completion."""
        async for session in self.db.get_session():
            repos = await self.db.get_repositories(session)
            
            state = await repos.conversations.get_by_user_id(user_id)
            if not state:
                return
            
            retro = await repos.retros.get_by_id(state.current_retro_id)
            if not retro:
                return
            
            # Generate preview
            markdown = retro.to_markdown()
            
            await self.telegram.send_message_with_retry(
                chat_id=chat_id,
                text="📋 **Предварительный просмотр ретроспективы:**",
                parse_mode="Markdown"
            )
            
            # Send markdown (split if too long)
            if len(markdown) > 4000:
                parts = [markdown[i:i+4000] for i in range(0, len(markdown), 4000)]
                for part in parts:
                    await self.telegram.send_message_with_retry(
                        chat_id=chat_id,
                        text=f"```markdown\n{part}\n```",
                        parse_mode="Markdown"
                    )
            else:
                await self.telegram.send_message_with_retry(
                    chat_id=chat_id,
                    text=f"```markdown\n{markdown}\n```",
                    parse_mode="Markdown"
                )
            
            # Ask for confirmation
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Завершить", callback_data="complete_retro")],
                [InlineKeyboardButton("✏️ Редактировать", callback_data="edit_retro")]
            ])
            
            await self.telegram.send_message_with_retry(
                chat_id=chat_id,
                text="Все верно? Можем завершить ретроспективу!",
                reply_markup=keyboard
            )
    
    async def _complete_retro(self, user_id: int, chat_id: int):
        """Complete the retrospective."""
        async for session in self.db.get_session():
            repos = await self.db.get_repositories(session)
            
            state = await repos.conversations.get_by_user_id(user_id)
            if not state:
                return
            
            # Complete retro
            retro = await repos.retros.complete_retro(state.current_retro_id)
            
            # Reset conversation
            await repos.conversations.reset_conversation(user_id)
            await repos.commit()
            
            if retro:
                # Send completion message
                await self.telegram.send_message_with_retry(
                    chat_id=chat_id,
                    text="🎉 **Ретроспектива завершена!**\n\n"
                         f"Дата: {retro.date.strftime('%d.%m.%Y')}\n"
                         f"Заполнено: {retro.completion_percentage:.0f}%\n\n"
                         "Увидимся завтра для новой ретроспективы! 😊",
                    parse_mode="Markdown"
                )
                
                # Send final document
                markdown = retro.to_markdown()
                await self.telegram.send_message_with_retry(
                    chat_id=chat_id,
                    text=f"📄 **Твоя ретроспектива:**\n\n```markdown\n{markdown}\n```",
                    parse_mode="Markdown"
                )
                
                logger.info("Completed retro", user_id=user_id, retro_id=retro.id)
    
    async def _handle_expired_conversation(self, user_id: int, chat_id: int):
        """Handle expired conversation."""
        async for session in self.db.get_session():
            repos = await self.db.get_repositories(session)
            
            await repos.conversations.reset_conversation(user_id)
            await repos.commit()
            
            await self.telegram.send_message_with_retry(
                chat_id=chat_id,
                text="⏰ Время ретроспективы истекло (30 минут бездействия).\n\n"
                     "Начни новую ретроспективу с помощью /retro"
            )
    
    def _get_next_step(self, current_step: RetroStep) -> Optional[RetroStep]:
        """Get next step in conversation flow."""
        try:
            current_index = self.step_order.index(current_step)
            if current_index < len(self.step_order) - 1:
                return self.step_order[current_index + 1]
        except ValueError:
            pass
        return None
    
    def _get_step_progress(self, current_step: RetroStep) -> Tuple[int, int]:
        """Get current step progress."""
        try:
            current_index = self.step_order.index(current_step)
            return (current_index + 1, len(self.step_order) - 2)  # Exclude REVIEW and COMPLETED
        except ValueError:
            return (1, 7)


# Service will be instantiated in telegram service with dependencies