"""Session management service for conversation timeouts and cleanup."""

from __future__ import annotations
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any

import structlog

from services.database_service import DatabaseService


logger = structlog.get_logger()


class SessionManager:
    """Manages conversation sessions and handles timeouts."""
    
    def __init__(self, database_service: DatabaseService):
        self.db = database_service
        self.cleanup_interval = 300  # 5 minutes
        self.cleanup_task = None
        self.running = False
    
    async def start(self):
        """Start the session manager background tasks."""
        if self.running:
            return
        
        self.running = True
        self.cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("Session manager started")
    
    async def stop(self):
        """Stop the session manager background tasks."""
        self.running = False
        
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Session manager stopped")
    
    async def _cleanup_loop(self):
        """Background loop for cleaning up expired sessions."""
        while self.running:
            try:
                await self.cleanup_expired_sessions()
                await asyncio.sleep(self.cleanup_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in session cleanup loop", error=str(e))
                await asyncio.sleep(60)  # Wait 1 minute before retrying
    
    async def cleanup_expired_sessions(self) -> int:
        """
        Clean up expired conversation sessions.
        
        Returns:
            Number of sessions cleaned up
        """
        try:
            async for session in self.db.get_session():
                repos = await self.db.get_repositories(session)
                
                # Clean up expired conversation states
                cleaned_count = await repos.conversations.cleanup_expired_states()
                
                if cleaned_count > 0:
                    logger.info("Cleaned up expired conversation sessions", count=cleaned_count)
                
                return cleaned_count
        
        except Exception as e:
            logger.error("Failed to cleanup expired sessions", error=str(e))
            return 0
    
    async def get_active_conversations_count(self) -> int:
        """
        Get count of currently active conversations.
        
        Returns:
            Number of active conversations
        """
        try:
            async for session in self.db.get_session():
                repos = await self.db.get_repositories(session)
                return await repos.conversations.get_active_conversations_count()
        
        except Exception as e:
            logger.error("Failed to get active conversations count", error=str(e))
            return 0
    
    async def extend_conversation_timeout(self, user_id: int, minutes: int = 30) -> bool:
        """
        Extend timeout for a conversation.
        
        Args:
            user_id: User ID
            minutes: Minutes to extend timeout
            
        Returns:
            True if timeout was extended
        """
        try:
            async for session in self.db.get_session():
                repos = await self.db.get_repositories(session)
                
                state = await repos.conversations.get_by_user_id(user_id)
                if state and state.is_active:
                    new_expires_at = datetime.utcnow() + timedelta(minutes=minutes)
                    
                    await repos.conversations.update(
                        user_id,
                        expires_at=new_expires_at,
                        updated_at=datetime.utcnow()
                    )
                    await repos.commit()
                    
                    logger.info("Extended conversation timeout", user_id=user_id, minutes=minutes)
                    return True
                
                return False
        
        except Exception as e:
            logger.error("Failed to extend conversation timeout", user_id=user_id, error=str(e))
            return False
    
    async def get_session_stats(self) -> Dict[str, Any]:
        """
        Get session statistics.
        
        Returns:
            Dictionary with session statistics
        """
        try:
            async for session in self.db.get_session():
                repos = await self.db.get_repositories(session)
                
                active_count = await repos.conversations.get_active_conversations_count()
                
                # Get total users count
                total_users = await repos.users.count()
                
                # Get today's retros count
                from datetime import date
                today = date.today()
                
                # Note: This is a simplified query - in a real implementation
                # you'd want to optimize this with proper SQL queries
                stats = {
                    "active_conversations": active_count,
                    "total_users": total_users,
                    "session_manager_running": self.running,
                    "cleanup_interval_seconds": self.cleanup_interval,
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                return stats
        
        except Exception as e:
            logger.error("Failed to get session stats", error=str(e))
            return {
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def force_cleanup_user_session(self, user_id: int) -> bool:
        """
        Force cleanup of a specific user's session.
        
        Args:
            user_id: User ID to cleanup
            
        Returns:
            True if session was cleaned up
        """
        try:
            async for session in self.db.get_session():
                repos = await self.db.get_repositories(session)
                
                state = await repos.conversations.get_by_user_id(user_id)
                if state:
                    await repos.conversations.reset_conversation(user_id)
                    await repos.commit()
                    
                    logger.info("Force cleaned up user session", user_id=user_id)
                    return True
                
                return False
        
        except Exception as e:
            logger.error("Failed to force cleanup user session", user_id=user_id, error=str(e))
            return False


# Global session manager instance
session_manager = None  # Will be initialized in main.py