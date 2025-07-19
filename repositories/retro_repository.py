"""Repository for Retro model operations."""

from __future__ import annotations
from typing import Optional, List, Dict, Any
from datetime import datetime, date

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from sqlalchemy.orm import selectinload

from models.retro import Retro
from repositories.base import BaseRepository


class RetroRepository(BaseRepository[Retro]):
    """Repository for Retro model operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, Retro)
    
    async def get_by_user_and_date(
        self, 
        user_id: int, 
        retro_date: date
    ) -> Optional[Retro]:
        """Get retrospective by user and date."""
        query = select(Retro).where(
            and_(
                Retro.user_id == user_id,
                Retro.date == retro_date
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def get_user_retros(
        self, 
        user_id: int,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[Retro]:
        """Get all retrospectives for a user, ordered by date (newest first)."""
        query = (
            select(Retro)
            .where(Retro.user_id == user_id)
            .order_by(desc(Retro.date))
        )
        
        if offset:
            query = query.offset(offset)
        if limit:
            query = query.limit(limit)
            
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def get_completed_retros(
        self, 
        user_id: int,
        limit: Optional[int] = None
    ) -> List[Retro]:
        """Get completed retrospectives for a user."""
        query = (
            select(Retro)
            .where(
                and_(
                    Retro.user_id == user_id,
                    Retro.completed_at.isnot(None)
                )
            )
            .order_by(desc(Retro.date))
        )
        
        if limit:
            query = query.limit(limit)
            
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def get_incomplete_retros(self, user_id: int) -> List[Retro]:
        """Get incomplete retrospectives for a user."""
        query = (
            select(Retro)
            .where(
                and_(
                    Retro.user_id == user_id,
                    Retro.completed_at.is_(None)
                )
            )
            .order_by(desc(Retro.date))
        )
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def create_daily_retro(
        self, 
        user_id: int, 
        retro_date: Optional[date] = None
    ) -> Retro:
        """Create a new daily retrospective."""
        if retro_date is None:
            retro_date = date.today()
        
        # Check if retro already exists for this date
        existing = await self.get_by_user_and_date(user_id, retro_date)
        if existing:
            return existing
        
        return await self.create(
            user_id=user_id,
            date=retro_date
        )
    
    async def update_retro_field(
        self, 
        retro_id: int, 
        field: str, 
        value: Any
    ) -> Optional[Retro]:
        """Update a specific field in a retrospective."""
        return await self.update(retro_id, **{field: value})
    
    async def add_to_list_field(
        self, 
        retro_id: int, 
        field: str, 
        item: str
    ) -> Optional[Retro]:
        """Add an item to a list field (wins, learnings, etc.)."""
        retro = await self.get_by_id(retro_id)
        if not retro:
            return None
        
        current_list = getattr(retro, field) or []
        current_list.append(item)
        
        return await self.update(retro_id, **{field: current_list})
    
    async def complete_retro(self, retro_id: int) -> Optional[Retro]:
        """Mark a retrospective as completed."""
        return await self.update(
            retro_id, 
            completed_at=datetime.utcnow()
        )
    
    async def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        """Get statistics for a user's retrospectives."""
        all_retros = await self.get_user_retros(user_id)
        completed_retros = [r for r in all_retros if r.is_completed]
        
        if not all_retros:
            return {
                "total_retros": 0,
                "completed_retros": 0,
                "completion_rate": 0.0,
                "average_energy": 0.0,
                "total_wins": 0,
                "total_learnings": 0
            }
        
        total_energy = sum(
            r.energy_level for r in completed_retros 
            if r.energy_level is not None
        )
        energy_count = len([
            r for r in completed_retros 
            if r.energy_level is not None
        ])
        
        total_wins = sum(
            len(r.wins) for r in completed_retros 
            if r.wins
        )
        
        total_learnings = sum(
            len(r.learnings) for r in completed_retros 
            if r.learnings
        )
        
        return {
            "total_retros": len(all_retros),
            "completed_retros": len(completed_retros),
            "completion_rate": len(completed_retros) / len(all_retros) * 100,
            "average_energy": total_energy / energy_count if energy_count > 0 else 0.0,
            "total_wins": total_wins,
            "total_learnings": total_learnings
        }