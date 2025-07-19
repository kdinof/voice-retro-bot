"""Conversation state model for managing multi-step retro flow."""

from __future__ import annotations
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum

from sqlalchemy import String, DateTime, BigInteger, JSON, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from models.database import Base


class RetroStep(str, Enum):
    """Enumeration of retrospective conversation steps."""
    IDLE = "idle"
    ENERGY = "energy"
    MOOD = "mood"
    MOOD_EXPLANATION = "mood_explanation"
    WINS = "wins"
    LEARNINGS = "learnings"
    NEXT_ACTIONS = "next_actions"
    MITS = "mits"
    EXPERIMENT = "experiment"
    REVIEW = "review"
    COMPLETED = "completed"


class ConversationState(Base):
    """Model for storing conversation state during retro flow."""
    
    __tablename__ = "conversation_states"
    
    # Foreign key to User (one-to-one relationship)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.telegram_id", ondelete="CASCADE"),
        primary_key=True,
        index=True
    )
    
    # Current step in the conversation flow
    current_step: Mapped[RetroStep] = mapped_column(
        SQLEnum(RetroStep),
        nullable=False,
        default=RetroStep.IDLE
    )
    
    # Current retro ID being worked on
    current_retro_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("retros.id", ondelete="CASCADE"),
        nullable=True
    )
    
    # Temporary data for current conversation
    temp_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        default=dict
    )
    
    # Last message ID for editing progress messages
    last_message_id: Mapped[Optional[int]] = mapped_column(
        nullable=True
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
    
    # Session timeout (30 minutes default)
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="conversation_state")
    
    def __repr__(self) -> str:
        return f"<ConversationState(user_id={self.user_id}, step={self.current_step})>"
    
    @property
    def is_expired(self) -> bool:
        """Check if conversation state has expired."""
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at
    
    @property
    def is_active(self) -> bool:
        """Check if conversation is currently active."""
        return (
            self.current_step != RetroStep.IDLE and 
            self.current_step != RetroStep.COMPLETED and
            not self.is_expired
        )
    
    def set_temp_data(self, key: str, value: Any) -> None:
        """Set temporary data for current conversation."""
        if self.temp_data is None:
            self.temp_data = {}
        self.temp_data[key] = value
    
    def get_temp_data(self, key: str, default: Any = None) -> Any:
        """Get temporary data from current conversation."""
        if self.temp_data is None:
            return default
        return self.temp_data.get(key, default)
    
    def clear_temp_data(self) -> None:
        """Clear all temporary data."""
        self.temp_data = {}
    
    def reset_conversation(self) -> None:
        """Reset conversation to idle state."""
        self.current_step = RetroStep.IDLE
        self.current_retro_id = None
        self.clear_temp_data()
        self.last_message_id = None
        self.expires_at = None
    
    def get_next_step(self) -> Optional[RetroStep]:
        """Get the next step in the conversation flow."""
        step_order = [
            RetroStep.ENERGY,
            RetroStep.MOOD,
            RetroStep.MOOD_EXPLANATION,
            RetroStep.WINS,
            RetroStep.LEARNINGS,
            RetroStep.NEXT_ACTIONS,
            RetroStep.MITS,
            RetroStep.EXPERIMENT,
            RetroStep.REVIEW,
            RetroStep.COMPLETED
        ]
        
        try:
            current_index = step_order.index(self.current_step)
            if current_index < len(step_order) - 1:
                return step_order[current_index + 1]
        except ValueError:
            pass
        
        return None
    
    def get_step_progress(self) -> tuple[int, int]:
        """Get current step progress (current, total)."""
        step_order = [
            RetroStep.ENERGY,
            RetroStep.MOOD,
            RetroStep.MOOD_EXPLANATION,
            RetroStep.WINS,
            RetroStep.LEARNINGS,
            RetroStep.NEXT_ACTIONS,
            RetroStep.MITS,
            RetroStep.EXPERIMENT,
            RetroStep.REVIEW
        ]
        
        try:
            current_index = step_order.index(self.current_step)
            return (current_index + 1, len(step_order))
        except ValueError:
            return (0, len(step_order))