"""
Database models and enumerations for Subsystem 3.
Defines the structure for storing AI recommendations and system state.
"""
import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Enum as SQLEnum, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class ToneEnum(enum.Enum):
    """Enumeration for the available AI personality tones."""
    strict = "strict"
    analytical = "analytical"
    encouraging = "encouraging"

class SourceEnum(enum.Enum):
    """Enumeration for the source of the AI recommendation."""
    openai = "openai"
    fallback = "fallback"
    cache = "cache"
    nvidia = "nvidia"

class AIRecommendation(Base):
    """
    ORM Model representing the 'ai_recommendations' table.
    Stores cached responses to optimize API costs and response times.
    """
    __tablename__ = "ai_recommendations"
    
    rec_id = Column(Integer, primary_key=True, autoincrement=True)
    building_id = Column(String(32), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    tone = Column(SQLEnum(ToneEnum), nullable=False)
    context_hash = Column(String(64), nullable=False)
    response_text = Column(Text, nullable=False)
    source = Column(SQLEnum(SourceEnum), nullable=False)
    tokens_used = Column(Integer, default=0)