"""Telegram bot service for handling updates and interactions."""

import asyncio
from typing import Optional

import structlog
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.error import TelegramError
from tenacity import retry, stop_after_attempt, wait_exponential

from config import settings
from services.voice_processor import voice_processor


logger = structlog.get_logger()


class TelegramService:
    """Service for handling Telegram bot operations."""
    
    def __init__(self):
        self.bot = Bot(token=settings.bot_token)
        self._webhook_configured = False
        self.conversation_manager = None  # Will be set after initialization
    
    async def setup_webhook(self) -> bool:
        """Set up Telegram webhook."""
        try:
            webhook_url = f"{settings.telegram_webhook_url}/api/webhook"
            
            await self.bot.set_webhook(
                url=webhook_url,
                secret_token=settings.telegram_webhook_secret,
                allowed_updates=["message", "callback_query"],
                drop_pending_updates=True
            )
            
            self._webhook_configured = True
            logger.info("Webhook configured successfully", url=webhook_url)
            return True
            
        except TelegramError as e:
            logger.error("Failed to set webhook", error=str(e))
            return False
    
    async def cleanup(self):
        """Cleanup bot resources."""
        try:
            if self._webhook_configured:
                await self.bot.delete_webhook()
                logger.info("Webhook removed")
        except Exception as e:
            logger.error("Error during cleanup", error=str(e))
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def send_message_with_retry(
        self,
        chat_id: int,
        text: str,
        **kwargs
    ) -> Optional[int]:
        """Send message with retry logic."""
        try:
            message = await self.bot.send_message(
                chat_id=chat_id,
                text=text,
                **kwargs
            )
            return message.message_id
        except TelegramError as e:
            logger.error("Failed to send message", chat_id=chat_id, error=str(e))
            raise
    
    async def send_typing_action(self, chat_id: int):
        """Send typing action to indicate bot is processing."""
        try:
            await self.bot.send_chat_action(
                chat_id=chat_id,
                action=ChatAction.TYPING
            )
        except TelegramError:
            pass  # Ignore typing action failures
    
    async def edit_message_text_safe(
        self,
        chat_id: int,
        message_id: int,
        text: str,
        **kwargs
    ) -> bool:
        """Safely edit message text, handling errors gracefully."""
        try:
            await self.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                **kwargs
            )
            return True
        except TelegramError as e:
            logger.warning("Failed to edit message", 
                         chat_id=chat_id, 
                         message_id=message_id, 
                         error=str(e))
            return False
    
    async def handle_update(self, update: Update):
        """Main update handler."""
        try:
            if update.message:
                await self._handle_message(update)
            elif update.callback_query:
                await self._handle_callback_query(update)
        except Exception as e:
            logger.error("Error handling update", 
                        update_id=update.update_id, 
                        error=str(e), 
                        exc_info=True)
    
    async def _handle_message(self, update: Update):
        """Handle incoming messages."""
        message = update.message
        chat_id = message.chat_id
        user_id = message.from_user.id
        
        logger.info("Received message", 
                   user_id=user_id, 
                   chat_id=chat_id,
                   message_type=message.effective_attachment)
        
        # Send typing action
        await self.send_typing_action(chat_id)
        
        # Handle different message types
        if message.text:
            await self._handle_text_message(update)
        elif message.voice:
            await self._handle_voice_message(update)
        else:
            await self.send_message_with_retry(
                chat_id=chat_id,
                text="Привет! Я понимаю только текст и голосовые сообщения. "
                     "Попробуйте отправить /start для начала работы."
            )
    
    async def _handle_text_message(self, update: Update):
        """Handle text messages."""
        message = update.message
        text = message.text.strip()
        chat_id = message.chat_id
        
        if text.startswith('/start'):
            await self._handle_start_command(update)
        elif text.startswith('/retro'):
            await self._handle_retro_command(update)
        elif text.startswith('/help'):
            await self._handle_help_command(update)
        elif text.startswith('/stop'):
            await self._handle_stop_command(update)
        else:
            # Handle conversation flow
            if self.conversation_manager:
                await self.conversation_manager.handle_user_response(
                    user_id=user_id,
                    chat_id=chat_id,
                    message_text=text
                )
            else:
                await self.send_message_with_retry(
                    chat_id=chat_id,
                    text="Для начала ретроспективы отправьте /retro или /start"
                )
    
    async def _handle_voice_message(self, update: Update):
        """Handle voice messages."""
        message = update.message
        chat_id = message.chat_id
        user_id = message.from_user.id
        voice = message.voice
        
        logger.info(
            "Processing voice message",
            user_id=user_id,
            chat_id=chat_id,
            file_id=voice.file_id,
            duration=voice.duration,
            file_size=voice.file_size
        )
        
        # Send initial processing message
        processing_msg = await self.send_message_with_retry(
            chat_id=chat_id,
            text="🎤 Обрабатываю голосовое сообщение..."
        )
        
        try:
            # Process voice message
            result = await voice_processor.process_telegram_voice(
                bot=self.bot,
                file_id=voice.file_id,
                chat_id=chat_id,
                progress_message_id=processing_msg,
                language="ru"
            )
            
            if result.success:
                # Create response message with transcription
                response_text = self._format_transcription_response(result)
                
                # Send transcription result
                await self.send_message_with_retry(
                    chat_id=chat_id,
                    text=response_text,
                    parse_mode="Markdown"
                )
                
                # Integrate with conversation flow
                if self.conversation_manager:
                    # Don't send transcription result, let conversation manager handle it
                    await self.conversation_manager.handle_user_response(
                        user_id=user_id,
                        chat_id=chat_id,
                        voice_file_id=voice.file_id
                    )
                else:
                    # Fallback: just show transcription
                    await self.send_message_with_retry(
                        chat_id=chat_id,
                        text="📝 Текст получен! Для начала ретроспективы используй /retro"
                    )
                
            else:
                # Voice processing failed
                await self.send_message_with_retry(
                    chat_id=chat_id,
                    text=f"❌ {result.error_message}\n\n"
                         "Попробуйте еще раз или отправьте сообщение текстом."
                )
            
        except Exception as e:
            logger.error("Unexpected error processing voice message", error=str(e), exc_info=True)
            
            # Update processing message with error
            await self.edit_message_text_safe(
                chat_id=chat_id,
                message_id=processing_msg,
                text="❌ Произошла ошибка при обработке голосового сообщения. "
                     "Попробуйте еще раз или отправьте текстом."
            )
    
    def _format_transcription_response(self, result) -> str:
        """Format transcription result for user."""
        lines = ["✅ **Голосовое сообщение обработано**", ""]
        
        # Add transcribed text
        lines.append("📝 **Расшифровка:**")
        lines.append(f"_{result.transcribed_text}_")
        lines.append("")
        
        # Add metadata
        metadata_lines = []
        
        if result.original_language:
            lang_name = {"ru": "Русский", "en": "English"}.get(
                result.original_language, result.original_language
            )
            metadata_lines.append(f"🌐 Язык: {lang_name}")
        
        if result.processing_time:
            metadata_lines.append(f"⏱️ Время обработки: {result.processing_time:.1f}с")
        
        if result.metadata.get("duration"):
            metadata_lines.append(f"🎵 Длительность: {result.metadata['duration']:.1f}с")
        
        if result.metadata.get("fallback_used"):
            metadata_lines.append("🔄 Использован резервный язык")
        
        if result.metadata.get("auto_detected"):
            metadata_lines.append("🤖 Автоопределение языка")
        
        if metadata_lines:
            lines.append("ℹ️ **Информация:**")
            lines.extend(metadata_lines)
        
        return "\n".join(lines)
    
    async def _handle_callback_query(self, update: Update):
        """Handle callback queries from inline keyboards."""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        chat_id = query.message.chat_id
        data = query.data
        
        if self.conversation_manager:
            # Handle conversation-related callbacks
            if data == "start_retro":
                await self.conversation_manager.start_retro_conversation(user_id, chat_id)
            elif data == "skip_step":
                await self.conversation_manager.handle_user_response(
                    user_id=user_id,
                    chat_id=chat_id,
                    message_text="пропустить"
                )
            elif data == "complete_retro":
                await self.conversation_manager._complete_retro(user_id, chat_id)
            elif data.startswith("show_retro_"):
                # Handle show retro callback
                await self.send_message_with_retry(
                    chat_id=chat_id,
                    text="📄 Функция просмотра ретроспектив будет добавлена позже."
                )
            else:
                logger.info("Unknown callback query", data=data)
        else:
            logger.info("Callback query received but conversation manager not available", data=data)
    
    async def _handle_start_command(self, update: Update):
        """Handle /start command."""
        chat_id = update.message.chat_id
        user_name = update.message.from_user.first_name or "Друг"
        
        welcome_text = f"""
Привет, {user_name}! 👋

Я помогаю проводить ежедневные ретроспективы с помощью голосовых сообщений.

🎤 **Как это работает:**
• Отправьте /retro для начала ретроспективы
• Я задам вам несколько вопросов
• Отвечайте голосом или текстом
• В конце получите готовый документ

**Команды:**
/retro - Начать ретроспективу
/help - Показать справку

Готовы начать?
        """.strip()
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🚀 Начать ретро", callback_data="start_retro")]
        ])
        
        await self.send_message_with_retry(
            chat_id=chat_id,
            text=welcome_text,
            reply_markup=keyboard
        )
    
    async def _handle_retro_command(self, update: Update):
        """Handle /retro command."""
        chat_id = update.message.chat_id
        user_id = update.message.from_user.id
        
        if self.conversation_manager:
            await self.conversation_manager.start_retro_conversation(user_id, chat_id)
        else:
            await self.send_message_with_retry(
                chat_id=chat_id,
                text="🎯 Ретроспектива временно недоступна. Попробуй позже."
            )
    
    async def _handle_help_command(self, update: Update):
        """Handle /help command."""
        chat_id = update.message.chat_id
        
        help_text = """
📚 **Справка по боту**

**Основные команды:**
/start - Приветствие и инструкции
/retro - Начать новую ретроспективу  
/help - Показать эту справку

**Как проходит ретроспектива:**
1. Уровень энергии (1-5)
2. Настроение + объяснение
3. Победы дня
4. Полученные уроки
5. Планы на завтра
6. Эксперименты

🎤 Используйте голосовые сообщения для удобства!
        """.strip()
        
        await self.send_message_with_retry(
            chat_id=chat_id,
            text=help_text
        )
    
    async def _handle_stop_command(self, update: Update):
        """Handle /stop command."""
        chat_id = update.message.chat_id
        user_id = update.message.from_user.id
        
        if self.conversation_manager:
            await self.conversation_manager.stop_conversation(user_id, chat_id)
        else:
            await self.send_message_with_retry(
                chat_id=chat_id,
                text="ℹ️ Нет активной ретроспективы для остановки."
            )