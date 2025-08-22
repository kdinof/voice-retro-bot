"""Scheduler service for sending daily todo reminders."""

from __future__ import annotations
import asyncio
from datetime import datetime, time, timedelta
from typing import Optional, Set, Dict, Any
import structlog

from services.database_service import DatabaseService
from services.telegram_service import TelegramService
from services.todo_service import TodoService


logger = structlog.get_logger()


class SchedulerService:
    """Service for scheduling daily todo reminders."""
    
    def __init__(
        self,
        database_service: DatabaseService,
        telegram_service: TelegramService
    ):
        self.db = database_service
        self.telegram = telegram_service
        self.todo_service = TodoService(database_service, telegram_service)
        
        # Scheduling configuration
        self.daily_reminder_time = time(8, 0)  # 8:00 AM
        self.timezone_offset = timedelta(hours=3)  # Moscow time (UTC+3)
        
        # Task management
        self._running = False
        self._scheduler_task: Optional[asyncio.Task] = None
        self._daily_task: Optional[asyncio.Task] = None
        
        # Track users to avoid duplicate messages
        self._daily_sent_users: Set[int] = set()
    
    async def start(self):
        """Start the scheduler service."""
        if self._running:
            logger.warning("Scheduler already running")
            return
        
        self._running = True
        logger.info("Starting scheduler service", daily_time=self.daily_reminder_time)
        
        # Start the main scheduler loop
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        
        logger.info("Scheduler service started")
    
    async def stop(self):
        """Stop the scheduler service."""
        if not self._running:
            return
        
        logger.info("Stopping scheduler service")
        self._running = False
        
        # Cancel running tasks
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
        
        if self._daily_task:
            self._daily_task.cancel()
            try:
                await self._daily_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Scheduler service stopped")
    
    async def _scheduler_loop(self):
        """Main scheduler loop that runs continuously."""
        try:
            while self._running:
                now = datetime.now()
                moscow_time = now + self.timezone_offset
                current_time = moscow_time.time()
                
                # Check if it's time for daily reminders (8:00 AM Moscow time)
                if self._should_send_daily_reminder(current_time):
                    if self._daily_task is None or self._daily_task.done():
                        logger.info("Starting daily todo reminder task")
                        self._daily_task = asyncio.create_task(self._send_daily_reminders())
                
                # Check every minute
                await asyncio.sleep(60)
        
        except asyncio.CancelledError:
            logger.info("Scheduler loop cancelled")
            raise
        except Exception as e:
            logger.error("Error in scheduler loop", error=str(e))
            if self._running:
                # Restart after error with delay
                await asyncio.sleep(30)
                if self._running:
                    self._scheduler_task = asyncio.create_task(self._scheduler_loop())
    
    def _should_send_daily_reminder(self, current_time: time) -> bool:
        """Check if it's time to send daily reminders."""
        target_time = self.daily_reminder_time
        
        # Check if current time is within 1 minute of target time
        target_minutes = target_time.hour * 60 + target_time.minute
        current_minutes = current_time.hour * 60 + current_time.minute
        
        return abs(current_minutes - target_minutes) <= 1
    
    async def _send_daily_reminders(self):
        """Send daily todo reminders to all users with todos."""
        try:
            logger.info("Starting daily todo reminder broadcast")
            
            # Reset daily sent users list (new day)
            self._daily_sent_users.clear()
            
            # Get all users who have todos
            user_ids = await self.todo_service.get_users_with_todos()
            
            if not user_ids:
                logger.info("No users with todos found for daily reminders")
                return
            
            logger.info("Sending daily reminders", user_count=len(user_ids))
            
            # Send reminders to all users
            success_count = 0
            error_count = 0
            
            for user_id in user_ids:
                if not self._running:
                    break
                
                if user_id in self._daily_sent_users:
                    continue  # Already sent today
                
                try:
                    # Get user's chat ID (assuming it's the same as user_id for private chats)
                    chat_id = user_id
                    
                    # Send daily todo
                    success = await self.todo_service.send_daily_todos_to_user(user_id, chat_id)
                    
                    if success:
                        success_count += 1
                        self._daily_sent_users.add(user_id)
                        logger.debug("Daily reminder sent", user_id=user_id)
                    else:
                        error_count += 1
                        logger.warning("Failed to send daily reminder", user_id=user_id)
                    
                    # Small delay between messages to avoid rate limiting
                    await asyncio.sleep(0.5)
                
                except Exception as e:
                    error_count += 1
                    logger.error("Error sending daily reminder", user_id=user_id, error=str(e))
            
            logger.info(
                "Daily reminder broadcast completed",
                total_users=len(user_ids),
                success_count=success_count,
                error_count=error_count
            )
        
        except Exception as e:
            logger.error("Error in daily reminder broadcast", error=str(e))
    
    async def send_immediate_todo(self, user_id: int, chat_id: int) -> bool:
        """
        Send immediate todo reminder to a specific user.
        
        Args:
            user_id: User ID
            chat_id: Chat ID
            
        Returns:
            True if sent successfully
        """
        try:
            return await self.todo_service.send_daily_todos_to_user(user_id, chat_id)
        except Exception as e:
            logger.error("Error sending immediate todo", user_id=user_id, error=str(e))
            return False
    
    async def schedule_cleanup_task(self):
        """Schedule cleanup of old todos (run once per day)."""
        try:
            logger.info("Running todo cleanup task")
            deleted_count = await self.todo_service.cleanup_old_todos(days_to_keep=30)
            logger.info("Todo cleanup completed", deleted_count=deleted_count)
        except Exception as e:
            logger.error("Error in cleanup task", error=str(e))
    
    def get_status(self) -> Dict[str, Any]:
        """Get scheduler status information."""
        return {
            "running": self._running,
            "daily_reminder_time": str(self.daily_reminder_time),
            "timezone_offset_hours": self.timezone_offset.total_seconds() / 3600,
            "daily_sent_users_today": len(self._daily_sent_users),
            "scheduler_task_running": self._scheduler_task and not self._scheduler_task.done(),
            "daily_task_running": self._daily_task and not self._daily_task.done()
        }
    
    async def test_daily_reminder(self, user_id: int, chat_id: int) -> bool:
        """
        Test daily reminder for a specific user (for testing purposes).
        
        Args:
            user_id: User ID to test
            chat_id: Chat ID to send test message
            
        Returns:
            True if test successful
        """
        try:
            logger.info("Testing daily reminder", user_id=user_id)
            return await self.todo_service.send_daily_todos_to_user(user_id, chat_id)
        except Exception as e:
            logger.error("Error testing daily reminder", user_id=user_id, error=str(e))
            return False