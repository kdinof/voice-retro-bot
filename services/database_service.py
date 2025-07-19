"""Database service for managing database operations and repositories."""

from __future__ import annotations
from typing import AsyncGenerator, Optional

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_async_session, init_database, close_database
from repositories.user_repository import UserRepository
from repositories.retro_repository import RetroRepository
from repositories.conversation_repository import ConversationRepository


logger = structlog.get_logger()


class DatabaseService:
    """Service for managing database operations and repositories."""
    
    def __init__(self):
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize database and create tables."""
        if self._initialized:
            return
        
        try:
            await init_database()
            self._initialized = True
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error("Failed to initialize database", error=str(e))
            raise
    
    async def close(self) -> None:
        """Close database connections."""
        try:
            await close_database()
            logger.info("Database connections closed")
        except Exception as e:
            logger.error("Error closing database", error=str(e))
    
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get database session."""
        async for session in get_async_session():
            yield session
    
    async def get_repositories(self, session: AsyncSession) -> RepositoryManager:
        """Get repository manager with all repositories."""
        return RepositoryManager(session)


class RepositoryManager:
    """Manager for all repositories with a single session."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self._users: Optional[UserRepository] = None
        self._retros: Optional[RetroRepository] = None
        self._conversations: Optional[ConversationRepository] = None
    
    @property
    def users(self) -> UserRepository:
        """Get user repository."""
        if self._users is None:
            self._users = UserRepository(self.session)
        return self._users
    
    @property
    def retros(self) -> RetroRepository:
        """Get retro repository."""
        if self._retros is None:
            self._retros = RetroRepository(self.session)
        return self._retros
    
    @property
    def conversations(self) -> ConversationRepository:
        """Get conversation repository."""
        if self._conversations is None:
            self._conversations = ConversationRepository(self.session)
        return self._conversations
    
    async def commit(self) -> None:
        """Commit the current transaction."""
        await self.session.commit()
    
    async def rollback(self) -> None:
        """Rollback the current transaction."""
        await self.session.rollback()
    
    async def close(self) -> None:
        """Close the session."""
        await self.session.close()


# Global database service instance
database_service = DatabaseService()