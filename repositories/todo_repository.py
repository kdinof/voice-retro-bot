"""Repository for ToDo model operations."""

from __future__ import annotations
from typing import Optional, List, Dict, Any
from datetime import datetime, date

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from sqlalchemy.orm import selectinload

from models.todo import ToDo
from repositories.base import BaseRepository


class ToDoRepository(BaseRepository[ToDo]):
    """Repository for ToDo model operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, ToDo)
    
    async def get_by_user_and_date(
        self, 
        user_id: int, 
        todo_date: date
    ) -> Optional[ToDo]:
        """Get todo by user and date."""
        query = select(ToDo).where(
            and_(
                ToDo.user_id == user_id,
                ToDo.date == todo_date
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def get_user_todos(
        self, 
        user_id: int,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[ToDo]:
        """Get all todos for a user, ordered by date (newest first)."""
        query = (
            select(ToDo)
            .where(ToDo.user_id == user_id)
            .order_by(desc(ToDo.date))
        )
        
        if offset:
            query = query.offset(offset)
        if limit:
            query = query.limit(limit)
            
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def get_latest_todo(self, user_id: int) -> Optional[ToDo]:
        """Get the most recent todo for a user."""
        query = (
            select(ToDo)
            .where(ToDo.user_id == user_id)
            .order_by(desc(ToDo.date))
            .limit(1)
        )
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def get_todos_for_date_range(
        self,
        user_id: int,
        start_date: date,
        end_date: date
    ) -> List[ToDo]:
        """Get todos for a user within a date range."""
        query = (
            select(ToDo)
            .where(
                and_(
                    ToDo.user_id == user_id,
                    ToDo.date >= start_date,
                    ToDo.date <= end_date
                )
            )
            .order_by(desc(ToDo.date))
        )
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def create_or_update_todo(
        self,
        user_id: int,
        todo_date: date,
        next_actions_todos: List[str],
        mits_todos: List[str],
        created_from_retro_id: Optional[int] = None
    ) -> ToDo:
        """Create or update a todo for a specific date."""
        existing = await self.get_by_user_and_date(user_id, todo_date)
        
        if existing:
            # Update existing todo
            return await self.update(
                existing.id,
                next_actions_todos=next_actions_todos,
                mits_todos=mits_todos,
                created_from_retro_id=created_from_retro_id or existing.created_from_retro_id
            )
        else:
            # Create new todo
            return await self.create(
                user_id=user_id,
                date=todo_date,
                next_actions_todos=next_actions_todos,
                mits_todos=mits_todos,
                created_from_retro_id=created_from_retro_id
            )
    
    async def get_todos_created_from_retro(
        self,
        retro_id: int
    ) -> List[ToDo]:
        """Get all todos created from a specific retro."""
        query = select(ToDo).where(ToDo.created_from_retro_id == retro_id)
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def get_active_users_for_scheduling(self) -> List[int]:
        """Get list of user IDs who have todos (for daily scheduling)."""
        query = select(ToDo.user_id).distinct()
        result = await self.session.execute(query)
        return [row[0] for row in result.fetchall()]
    
    async def delete_old_todos(self, cutoff_date: date) -> int:
        """Delete todos older than cutoff date and return count of deleted records."""
        from sqlalchemy import delete
        
        stmt = delete(ToDo).where(ToDo.date < cutoff_date)
        result = await self.session.execute(stmt)
        await self.session.commit()
        
        return result.rowcount
    
    async def get_user_todo_stats(self, user_id: int) -> Dict[str, Any]:
        """Get statistics for a user's todos."""
        all_todos = await self.get_user_todos(user_id)
        
        if not all_todos:
            return {
                "total_todos": 0,
                "total_next_actions": 0,
                "total_mits": 0,
                "average_todos_per_day": 0.0,
                "days_with_todos": 0
            }
        
        total_next_actions = sum(len(todo.next_actions_todos) for todo in all_todos)
        total_mits = sum(len(todo.mits_todos) for todo in all_todos)
        days_with_todos = len([todo for todo in all_todos if todo.has_todos])
        
        return {
            "total_todos": len(all_todos),
            "total_next_actions": total_next_actions,
            "total_mits": total_mits,
            "average_todos_per_day": (total_next_actions + total_mits) / len(all_todos),
            "days_with_todos": days_with_todos
        }