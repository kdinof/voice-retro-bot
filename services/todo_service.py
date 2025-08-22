"""Service for managing daily todo lists generated from retros."""

from __future__ import annotations
import asyncio
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any, List

import structlog

from models.retro import Retro
from models.todo import ToDo
from services.database_service import DatabaseService
from services.gpt_service import gpt_service, GPTProcessingError
from services.telegram_service import TelegramService


logger = structlog.get_logger()


class TodoGenerationError(Exception):
    """Raised when todo generation fails."""
    pass


class TodoService:
    """Service for managing daily todo lists."""
    
    def __init__(self, database_service: DatabaseService, telegram_service: Optional[TelegramService] = None):
        self.db = database_service
        self.telegram = telegram_service
    
    async def generate_todos_from_retro(
        self,
        retro: Retro,
        save_to_db: bool = True
    ) -> Optional[ToDo]:
        """
        Generate todo list from completed retro using GPT.
        
        Args:
            retro: Completed retrospective
            save_to_db: Whether to save to database
            
        Returns:
            Generated Todo object or None if generation failed
        """
        try:
            logger.info("Generating todos from retro", retro_id=retro.id, user_id=retro.user_id)
            
            # Check if retro has necessary sections
            next_actions_text = retro.next_actions_text or ""
            mits_text = retro.mits_text or ""
            
            if not next_actions_text and not mits_text:
                logger.warning("Retro has no next actions or MITs text", retro_id=retro.id)
                return None
            
            # Generate todos using GPT
            todo_result = await gpt_service.generate_daily_todo(
                next_actions_text=next_actions_text,
                mits_text=mits_text
            )
            
            if todo_result.get("parse_error"):
                logger.warning("GPT failed to parse todo response", retro_id=retro.id)
                return None
            
            next_actions_todos = todo_result.get("next_actions_todos", [])
            mits_todos = todo_result.get("mits_todos", [])
            
            # Calculate todo date (next day after retro)
            todo_date = retro.date + timedelta(days=1)
            
            if save_to_db:
                # Save to database
                async for session in self.db.get_session():
                    repos = await self.db.get_repositories(session)
                    
                    todo = await repos.todos.create_or_update_todo(
                        user_id=retro.user_id,
                        todo_date=todo_date,
                        next_actions_todos=next_actions_todos,
                        mits_todos=mits_todos,
                        created_from_retro_id=retro.id
                    )
                    
                    await repos.commit()
                    
                    logger.info(
                        "Todos generated and saved",
                        retro_id=retro.id,
                        todo_id=todo.id,
                        next_actions_count=len(next_actions_todos),
                        mits_count=len(mits_todos)
                    )
                    
                    return todo
            else:
                # Create todo object without saving
                todo = ToDo(
                    user_id=retro.user_id,
                    date=todo_date,
                    next_actions_todos=next_actions_todos,
                    mits_todos=mits_todos,
                    created_from_retro_id=retro.id
                )
                
                logger.info(
                    "Todos generated (not saved)",
                    retro_id=retro.id,
                    next_actions_count=len(next_actions_todos),
                    mits_count=len(mits_todos)
                )
                
                return todo
        
        except GPTProcessingError as e:
            logger.error("GPT processing failed for todo generation", retro_id=retro.id, error=str(e))
            raise TodoGenerationError(f"Failed to generate todos: {str(e)}")
        
        except Exception as e:
            logger.error("Unexpected error during todo generation", retro_id=retro.id, error=str(e))
            raise TodoGenerationError(f"Unexpected error: {str(e)}")
    
    async def send_todo_message(
        self,
        user_id: int,
        chat_id: int,
        todo: ToDo,
        message_type: str = "completion"
    ) -> bool:
        """
        Send todo message to user via Telegram.
        
        Args:
            user_id: User ID
            chat_id: Chat ID for sending message
            todo: Todo object to send
            message_type: Type of message ("completion" or "daily")
            
        Returns:
            True if message sent successfully
        """
        if not self.telegram:
            logger.warning("Telegram service not available")
            return False
        
        try:
            # Generate message text
            message_text = todo.to_telegram_message()
            
            # Add context based on message type
            if message_type == "completion":
                prefix = "🎉 **Ретроспектива завершена!**\n\n"
            elif message_type == "daily":
                prefix = "🌅 **Доброе утро!**\n\n"
            else:
                prefix = ""
            
            full_message = prefix + message_text
            
            # Send message
            success = await self.telegram.send_message_with_retry(
                chat_id=chat_id,
                text=full_message,
                parse_mode="Markdown"
            )
            
            if success:
                logger.info(
                    "Todo message sent successfully",
                    user_id=user_id,
                    todo_id=todo.id,
                    message_type=message_type
                )
            else:
                logger.error(
                    "Failed to send todo message",
                    user_id=user_id,
                    todo_id=todo.id,
                    message_type=message_type
                )
            
            return success
        
        except Exception as e:
            logger.error(
                "Error sending todo message",
                user_id=user_id,
                todo_id=todo.id,
                error=str(e)
            )
            return False
    
    async def get_latest_todo_for_user(self, user_id: int) -> Optional[ToDo]:
        """Get the most recent todo for a user."""
        try:
            async for session in self.db.get_session():
                repos = await self.db.get_repositories(session)
                return await repos.todos.get_latest_todo(user_id)
        
        except Exception as e:
            logger.error("Failed to get latest todo", user_id=user_id, error=str(e))
            return None
    
    async def get_todo_for_date(self, user_id: int, todo_date: date) -> Optional[ToDo]:
        """Get todo for a specific date."""
        try:
            async for session in self.db.get_session():
                repos = await self.db.get_repositories(session)
                return await repos.todos.get_by_user_and_date(user_id, todo_date)
        
        except Exception as e:
            logger.error("Failed to get todo for date", user_id=user_id, date=todo_date, error=str(e))
            return None
    
    async def get_users_with_todos(self) -> List[int]:
        """Get list of user IDs who have todos (for scheduling)."""
        try:
            async for session in self.db.get_session():
                repos = await self.db.get_repositories(session)
                return await repos.todos.get_active_users_for_scheduling()
        
        except Exception as e:
            logger.error("Failed to get users with todos", error=str(e))
            return []
    
    async def send_daily_todos_to_user(self, user_id: int, chat_id: int) -> bool:
        """
        Send daily todo reminder to a specific user.
        
        Args:
            user_id: User ID
            chat_id: Chat ID for sending message
            
        Returns:
            True if message sent successfully
        """
        try:
            # Get today's todo (which should be yesterday's generated todo)
            today = date.today()
            todo = await self.get_todo_for_date(user_id, today)
            
            if not todo:
                # No todo for today, get the latest one
                todo = await self.get_latest_todo_for_user(user_id)
                
                if not todo:
                    logger.info("No todos found for user", user_id=user_id)
                    return True  # Not an error, just no todos
            
            # Send the todo message
            return await self.send_todo_message(
                user_id=user_id,
                chat_id=chat_id,
                todo=todo,
                message_type="daily"
            )
        
        except Exception as e:
            logger.error("Failed to send daily todo", user_id=user_id, error=str(e))
            return False
    
    async def cleanup_old_todos(self, days_to_keep: int = 30) -> int:
        """
        Clean up old todos to save storage.
        
        Args:
            days_to_keep: Number of days to keep todos
            
        Returns:
            Number of todos deleted
        """
        try:
            cutoff_date = date.today() - timedelta(days=days_to_keep)
            
            async for session in self.db.get_session():
                repos = await self.db.get_repositories(session)
                deleted_count = await repos.todos.delete_old_todos(cutoff_date)
                
                logger.info("Cleaned up old todos", deleted_count=deleted_count, cutoff_date=cutoff_date)
                return deleted_count
        
        except Exception as e:
            logger.error("Failed to cleanup old todos", error=str(e))
            return 0
    
    async def get_todo_stats(self, user_id: int) -> Dict[str, Any]:
        """Get todo statistics for a user."""
        try:
            async for session in self.db.get_session():
                repos = await self.db.get_repositories(session)
                return await repos.todos.get_user_todo_stats(user_id)
        
        except Exception as e:
            logger.error("Failed to get todo stats", user_id=user_id, error=str(e))
            return {}