"""
Database models for Subsystem 3: AI, Data Persistence & Deployment.
Defines the SQLAlchemy ORM.
7 tables specified in the architecture.
"""
import enum
from sqlalchemy import (
    Column, String, Integer, Enum, ForeignKey, CheckConstraint, Numeric
)
from sqlalchemy.orm import declarative_base

# Base class for all SQLAlchemy models
Base = declarative_base()

# --- Enumerations (Data Validation) ---
# Enums restrict columns to specific, safe values to prevent bad data.

class DeviceCategory(enum.Enum):
    HVAC = 'HVAC'
    Lighting = 'Lighting'
    Servers = 'Servers'
    Other = 'Other'

class ToneEnum(enum.Enum):
    strict = 'strict'
    analytical = 'analytical'
    encouraging = 'encouraging'

class SourceEnum(enum.Enum):
    openai = 'openai'
    fallback = 'fallback'
    cache = 'cache'

# --- Core Entities ---

class Building(Base):
    """Represents a campus building with its sustainability targets."""
    __tablename__ = 'buildings'
    
    building_id = Column(String(32), primary_key=True)
    name = Column(String(120), nullable=False)
    location = Column(String(120))
    total_area_m2 = Column(Numeric(10, 2), CheckConstraint('total_area_m2 > 0'), nullable=False)
    target_score = Column(Numeric(5, 2), default=90.00)

class Device(Base):
    """Represents an energy-consuming device inside a specific building."""
    __tablename__ = 'devices'
    
    device_id = Column(Integer, primary_key=True, autoincrement=True)
    building_id = Column(String(32), ForeignKey('buildings.building_id'), nullable=False)
    category = Column(Enum(DeviceCategory), nullable=False)
    name = Column(String(120), nullable=False)
    rated_power_kw = Column(Numeric(8, 2), nullable=False)