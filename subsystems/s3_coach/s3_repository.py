"""
Database repository for Subsystem 3.
"""
from typing import Optional
from subsystems.s3_coach.s3_models import AIRecommendation, ToneEnum, SourceEnum
from datetime import datetime

class MySQLRepository:
    """
    Handles database persistence and retrieval.
    """
    
    def __init__(self, session):
        # Constructor: Proper state initialization
        self._session = None
        # Initialization Method
        self._setup_repository(session)

    def _setup_repository(self, session):
        """Configuration logic to securely inject the database session."""
        self.session = session

    # Getters & Setters
    @property
    def session(self):
        """Retrieves the active SQLAlchemy session."""
        return self._session

    @session.setter
    def session(self, value):
        """Validates and sets the SQLAlchemy session."""
        if not value:
            raise ValueError("A valid SQLAlchemy session must be provided.")
        self._session = value

    def get_cached_recommendation(self, building_id: str, context_hash: str) -> Optional[str]:
        """
        Retrieves a cached AI recommendation if it exists.
        Returns the cached JSON string or None.
        """
        cached = self.session.query(AIRecommendation).filter_by(
            building_id=building_id,
            context_hash=context_hash
        ).order_by(AIRecommendation.created_at.desc()).first()
        
        if cached:
            return cached.response_text
        return None

    def save_ai_recommendation(self, building_id: str, context_hash: str, tone: str, 
                               response: str, source: str, tokens: int = 0) -> None:
        """Saves a new AI recommendation to the persistent database."""
        new_rec = AIRecommendation(
            building_id=building_id,
            created_at=datetime.now(),
            tone=ToneEnum(tone),
            context_hash=context_hash,
            response_text=response,
            source=SourceEnum(source),
            tokens_used=tokens
        )
        self.session.add(new_rec)
        self.session.commit()