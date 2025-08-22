"""ToDo model for storing daily todo lists generated from retros."""

from __future__ import annotations
from datetime import datetime, date
from typing import Optional, List, Dict, Any

from sqlalchemy import String, Text, Integer, Date, DateTime, BigInteger, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from models.database import Base


class ToDo(Base):
    """Model for storing daily todo lists generated from retrospectives."""
    
    __tablename__ = "todos"
    
    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign key to User
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.telegram_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Todo date (user's local date)
    date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True
    )
    
    # Reference to the retro this todo was created from
    created_from_retro_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("retros.id", ondelete="SET NULL"),
        nullable=True
    )
    
    # Todo lists as JSON arrays
    next_actions_todos: Mapped[List[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list
    )
    
    mits_todos: Mapped[List[str]] = mapped_column(
        JSON,
        nullable=False, 
        default=list
    )
    
    # Metadata
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
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="todos")
    retro: Mapped[Optional["Retro"]] = relationship("Retro")
    
    def __repr__(self) -> str:
        return f"<ToDo(id={self.id}, user_id={self.user_id}, date={self.date})>"
    
    @property
    def total_todos_count(self) -> int:
        """Get total number of todos."""
        return len(self.next_actions_todos) + len(self.mits_todos)
    
    @property
    def has_todos(self) -> bool:
        """Check if there are any todos."""
        return len(self.next_actions_todos) > 0 or len(self.mits_todos) > 0
    
    def to_telegram_message(self) -> str:
        """Generate Telegram message for the todo list."""
        lines = []
        
        # Header
        lines.append(f"📝 **Дела на {self.date.strftime('%d.%m.%Y')}**")
        lines.append("")
        
        # Next Actions section
        if self.next_actions_todos:
            lines.append("🎯 **Запланированные дела:**")
            for i, todo in enumerate(self.next_actions_todos, 1):
                lines.append(f"{i}. {todo}")
            lines.append("")
        
        # MITs section
        if self.mits_todos:
            lines.append("⭐ **Главные задачи дня:**")
            for i, todo in enumerate(self.mits_todos, 1):
                lines.append(f"{i}. {todo}")
            lines.append("")
        
        # Footer
        if not self.has_todos:
            lines.append("😌 На сегодня дел не запланировано")
        else:
            lines.append("💪 Удачного дня!")
        
        return "\n".join(lines)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert todo to dictionary."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "date": self.date.isoformat(),
            "next_actions_todos": self.next_actions_todos,
            "mits_todos": self.mits_todos,
            "total_count": self.total_todos_count,
            "has_todos": self.has_todos,
            "created_from_retro_id": self.created_from_retro_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }