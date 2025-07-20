"""Retro model for storing daily retrospectives."""

from __future__ import annotations
from datetime import datetime, date
from typing import Optional, List, Dict, Any

from sqlalchemy import String, Text, Integer, Date, DateTime, BigInteger, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from models.database import Base


class Retro(Base):
    """Model for storing daily retrospectives."""
    
    __tablename__ = "retros"
    
    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign key to User
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.telegram_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Retrospective date (user's local date)
    date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True
    )
    
    # Energy and mood
    energy_level: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True
    )  # 1-5 scale
    
    mood: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True
    )  # Emoji or mood descriptor
    
    mood_explanation: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    
    # Retrospective content (stored as raw text)
    wins_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    
    learnings_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    
    next_actions_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    
    mits_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )  # Most Important Tasks
    
    experiment_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )  # Experiment description
    
    # Metadata
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    
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
    user: Mapped["User"] = relationship("User", back_populates="retros")
    
    def __repr__(self) -> str:
        return f"<Retro(id={self.id}, user_id={self.user_id}, date={self.date})>"
    
    @property
    def is_completed(self) -> bool:
        """Check if retrospective is completed."""
        return self.completed_at is not None
    
    @property
    def completion_percentage(self) -> float:
        """Calculate completion percentage based on filled fields."""
        total_fields = 6  # energy, mood, wins, learnings, next_actions, mits
        filled_fields = 0
        
        if self.energy_level is not None:
            filled_fields += 1
        if self.mood:
            filled_fields += 1
        if self.wins_text:
            filled_fields += 1
        if self.learnings_text:
            filled_fields += 1
        if self.next_actions_text:
            filled_fields += 1
        if self.mits_text:
            filled_fields += 1
            
        return (filled_fields / total_fields) * 100
    
    def to_markdown(self) -> str:
        """Generate markdown document for the retrospective."""
        lines = []
        
        # Header
        lines.append(f"# Daily Retro - {self.date}")
        
        # Add status indicator for incomplete retrospectives
        if not self.completed_at:
            lines.append("")
            lines.append("⚠️ *This retrospective is incomplete. Some sections are missing.*")
        
        lines.append("")
        
        # Energy and mood
        if self.energy_level:
            lines.append(f"**Energy Level:** {self.energy_level}/5")
        
        if self.mood:
            mood_text = f"**Mood:** {self.mood}"
            if self.mood_explanation:
                mood_text += f" - {self.mood_explanation}"
            lines.append(mood_text)
        
        lines.append("")
        
        # Sections
        sections = [
            ("🏆 Wins", self.wins_text),
            ("📚 Learnings", self.learnings_text),
            ("🎯 Next Actions", self.next_actions_text),
            ("⭐ Tomorrow's MITs", self.mits_text)
        ]
        
        for title, text_content in sections:
            if text_content:
                lines.append(f"## {title}")
                lines.append(text_content)
                lines.append("")
            elif not self.completed_at:
                # Show missing sections for incomplete retrospectives
                lines.append(f"## {title}")
                lines.append("*⏳ Not answered yet*")
                lines.append("")
        
        # Experiment
        if self.experiment_text:
            lines.append("## 🧪 Experiment")
            lines.append(self.experiment_text)
            lines.append("")
        elif not self.completed_at:
            lines.append("## 🧪 Experiment")
            lines.append("*⏳ Not answered yet*")
            lines.append("")
        
        # Footer
        if self.completed_at:
            lines.append(f"*Completed at {self.completed_at.strftime('%Y-%m-%d %H:%M')}*")
        
        return "\n".join(lines)