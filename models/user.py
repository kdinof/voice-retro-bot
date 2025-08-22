"""User model for Telegram users."""

from __future__ import annotations
from datetime import datetime
from typing import Optional, List

from sqlalchemy import String, DateTime, BigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from models.database import Base


class User(Base):
    """User model for storing Telegram user information."""
    
    __tablename__ = "users"
    
    # Primary key: Telegram user ID
    telegram_id: Mapped[int] = mapped_column(
        BigInteger, 
        primary_key=True,
        index=True
    )
    
    # User information
    username: Mapped[Optional[str]] = mapped_column(
        String(32), 
        nullable=True,
        index=True
    )
    
    first_name: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True
    )
    
    last_name: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True
    )
    
    language_code: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
        default="ru"
    )
    
    timezone: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        default="Europe/Moscow"
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    
    # User preferences
    is_active: Mapped[bool] = mapped_column(default=True)
    
    # Relationships
    retros: Mapped[List["Retro"]] = relationship(
        "Retro",
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="Retro.date.desc()"
    )
    
    conversation_state: Mapped[Optional["ConversationState"]] = relationship(
        "ConversationState",
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False
    )
    
    todos: Mapped[List["ToDo"]] = relationship(
        "ToDo",
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="ToDo.date.desc()"
    )
    
    def __repr__(self) -> str:
        return f"<User(telegram_id={self.telegram_id}, username='{self.username}')>"
    
    @property
    def display_name(self) -> str:
        """Get user display name."""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        elif self.username:
            return f"@{self.username}"
        else:
            return f"User {self.telegram_id}"