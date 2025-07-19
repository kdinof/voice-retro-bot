"""Base repository class with common CRUD operations."""

from __future__ import annotations
from typing import TypeVar, Generic, Optional, List, Type, Any, Dict
from abc import ABC, abstractmethod

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.orm import selectinload

from models.database import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType], ABC):
    """Base repository class with common CRUD operations."""
    
    def __init__(self, session: AsyncSession, model: Type[ModelType]):
        self.session = session
        self.model = model
    
    async def create(self, **kwargs) -> ModelType:
        """Create a new record."""
        instance = self.model(**kwargs)
        self.session.add(instance)
        await self.session.commit()
        await self.session.refresh(instance)
        return instance
    
    async def get_by_id(self, id_value: Any) -> Optional[ModelType]:
        """Get a record by primary key."""
        return await self.session.get(self.model, id_value)
    
    async def get_all(
        self, 
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[ModelType]:
        """Get all records with optional pagination."""
        query = select(self.model)
        
        if offset:
            query = query.offset(offset)
        if limit:
            query = query.limit(limit)
            
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def update(self, id_value: Any, **kwargs) -> Optional[ModelType]:
        """Update a record by primary key."""
        # Get primary key column name
        pk_column = self.model.__table__.primary_key.columns.values()[0]
        
        stmt = (
            update(self.model)
            .where(pk_column == id_value)
            .values(**kwargs)
        )
        
        await self.session.execute(stmt)
        await self.session.commit()
        
        return await self.get_by_id(id_value)
    
    async def delete(self, id_value: Any) -> bool:
        """Delete a record by primary key."""
        # Get primary key column name
        pk_column = self.model.__table__.primary_key.columns.values()[0]
        
        stmt = delete(self.model).where(pk_column == id_value)
        result = await self.session.execute(stmt)
        await self.session.commit()
        
        return result.rowcount > 0
    
    async def exists(self, **filters) -> bool:
        """Check if a record exists with given filters."""
        query = select(self.model).filter_by(**filters)
        result = await self.session.execute(query)
        return result.scalar_one_or_none() is not None
    
    async def count(self, **filters) -> int:
        """Count records with given filters."""
        from sqlalchemy import func
        
        # Get primary key column
        pk_column = list(self.model.__table__.primary_key.columns.values())[0]
        
        query = select(func.count(pk_column)).filter_by(**filters)
        result = await self.session.execute(query)
        return result.scalar() or 0