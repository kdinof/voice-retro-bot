"""Repository for User model operations."""

from __future__ import annotations
from typing import Optional, List
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from models.user import User
from repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """Repository for User model operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, User)
    
    async def get_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """Get user by Telegram ID."""
        return await self.get_by_id(telegram_id)
    
    async def get_by_username(self, username: str) -> Optional[User]:
        """Get user by username."""
        query = select(User).where(User.username == username)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def get_with_retros(self, telegram_id: int) -> Optional[User]:
        """Get user with their retrospectives."""
        query = (
            select(User)
            .options(selectinload(User.retros))
            .where(User.telegram_id == telegram_id)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def get_with_conversation_state(self, telegram_id: int) -> Optional[User]:
        """Get user with conversation state."""
        query = (
            select(User)
            .options(selectinload(User.conversation_state))
            .where(User.telegram_id == telegram_id)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def create_or_update_from_telegram(
        self,
        telegram_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        language_code: Optional[str] = None
    ) -> User:
        """Create or update user from Telegram user data."""
        user = await self.get_by_telegram_id(telegram_id)
        
        if user:
            # Update existing user
            update_data = {
                "updated_at": datetime.utcnow()
            }
            
            if username is not None:
                update_data["username"] = username
            if first_name is not None:
                update_data["first_name"] = first_name
            if last_name is not None:
                update_data["last_name"] = last_name
            if language_code is not None:
                update_data["language_code"] = language_code
            
            return await self.update(telegram_id, **update_data)
        else:
            # Create new user
            return await self.create(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                language_code=language_code or "ru"
            )
    
    async def get_active_users(self) -> List[User]:
        """Get all active users."""
        query = select(User).where(User.is_active == True)
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def deactivate_user(self, telegram_id: int) -> bool:
        """Deactivate a user (soft delete)."""
        user = await self.update(telegram_id, is_active=False)
        return user is not None