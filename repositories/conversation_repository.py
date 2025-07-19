"""Repository for ConversationState model operations."""

from __future__ import annotations
from typing import Optional, Any
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from models.conversation_state import ConversationState, RetroStep
from repositories.base import BaseRepository


class ConversationRepository(BaseRepository[ConversationState]):
    """Repository for ConversationState model operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, ConversationState)
    
    async def get_by_user_id(self, user_id: int) -> Optional[ConversationState]:
        """Get conversation state by user ID."""
        return await self.get_by_id(user_id)
    
    async def create_or_update_state(
        self, 
        user_id: int,
        step: RetroStep,
        retro_id: Optional[int] = None,
        temp_data: Optional[dict] = None,
        last_message_id: Optional[int] = None,
        timeout_minutes: int = 30
    ) -> ConversationState:
        """Create or update conversation state."""
        state = await self.get_by_user_id(user_id)
        
        expires_at = datetime.utcnow() + timedelta(minutes=timeout_minutes)
        
        if state:
            # Update existing state
            update_data = {
                "current_step": step,
                "updated_at": datetime.utcnow(),
                "expires_at": expires_at
            }
            
            if retro_id is not None:
                update_data["current_retro_id"] = retro_id
            if temp_data is not None:
                update_data["temp_data"] = temp_data
            if last_message_id is not None:
                update_data["last_message_id"] = last_message_id
            
            return await self.update(user_id, **update_data)
        else:
            # Create new state
            return await self.create(
                user_id=user_id,
                current_step=step,
                current_retro_id=retro_id,
                temp_data=temp_data or {},
                last_message_id=last_message_id,
                expires_at=expires_at
            )
    
    async def update_step(
        self, 
        user_id: int, 
        step: RetroStep
    ) -> Optional[ConversationState]:
        """Update conversation step."""
        return await self.update(
            user_id,
            current_step=step,
            updated_at=datetime.utcnow()
        )
    
    async def set_temp_data(
        self, 
        user_id: int, 
        key: str, 
        value: Any
    ) -> Optional[ConversationState]:
        """Set temporary data for conversation."""
        state = await self.get_by_user_id(user_id)
        if not state:
            return None
        
        if state.temp_data is None:
            state.temp_data = {}
        
        state.temp_data[key] = value
        
        return await self.update(
            user_id,
            temp_data=state.temp_data,
            updated_at=datetime.utcnow()
        )
    
    async def get_temp_data(
        self, 
        user_id: int, 
        key: str, 
        default: Any = None
    ) -> Any:
        """Get temporary data from conversation."""
        state = await self.get_by_user_id(user_id)
        if not state or not state.temp_data:
            return default
        
        return state.temp_data.get(key, default)
    
    async def clear_temp_data(self, user_id: int) -> Optional[ConversationState]:
        """Clear all temporary data."""
        return await self.update(
            user_id,
            temp_data={},
            updated_at=datetime.utcnow()
        )
    
    async def set_current_retro(
        self, 
        user_id: int, 
        retro_id: int
    ) -> Optional[ConversationState]:
        """Set current retro ID."""
        return await self.update(
            user_id,
            current_retro_id=retro_id,
            updated_at=datetime.utcnow()
        )
    
    async def reset_conversation(self, user_id: int) -> Optional[ConversationState]:
        """Reset conversation to idle state."""
        return await self.update(
            user_id,
            current_step=RetroStep.IDLE,
            current_retro_id=None,
            temp_data={},
            last_message_id=None,
            expires_at=None,
            updated_at=datetime.utcnow()
        )
    
    async def cleanup_expired_states(self) -> int:
        """Clean up expired conversation states."""
        now = datetime.utcnow()
        
        stmt = delete(ConversationState).where(
            ConversationState.expires_at < now
        )
        
        result = await self.session.execute(stmt)
        await self.session.commit()
        
        return result.rowcount
    
    async def get_active_conversations_count(self) -> int:
        """Get count of active conversations."""
        now = datetime.utcnow()
        
        query = select(ConversationState).where(
            ConversationState.current_step != RetroStep.IDLE,
            ConversationState.expires_at > now
        )
        
        result = await self.session.execute(query)
        return len(list(result.scalars().all()))