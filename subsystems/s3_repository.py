"""
Repository layer for Subsystem 3.
Implements the data access methods required by S1 (Analytics) and S3 (AI Coach)
"""
from typing import  Dict
from sqlalchemy.orm import Session
from subsystems.s3_models import (
    Setting, DeviceCategory
)

class MySQLRepository:
    """Implementation of the EnergyRepository using SQLAlchemy."""
    
    def __init__(self, session: Session):
        """
        Initializes the repository with a database session.
        The session is managed by the application factory.
        """
        self.session = session

    # --- Settings & Alert Limits ---

    def get_limits(self, building_id: str) -> Dict[str, float]:
        """
        Retrieves the alert limits for a specific building.
        Returns a dictionary mapping device category names to their limit in kWh.
        """
        settings = self.session.query(Setting).filter_by(building_id=building_id).all()
        return {s.device_category.value: float(s.alert_limit_kwh) for s in settings}

    def save_limits(self, building_id: str, limits: Dict[str, float]) -> None:
        """
        Saves or updates alert limits for a given building.
        Expects a dictionary like {'HVAC': 15.5, 'Lighting': 10.0}.
        """
        for category_name, limit_val in limits.items():
            category_enum = DeviceCategory(category_name)
            
            # Check if a setting for this building and category already exists
            setting = self.session.query(Setting).filter_by(
                building_id=building_id, 
                device_category=category_enum
            ).first()
            
            if setting:
                setting.alert_limit_kwh = limit_val
            else:
                new_setting = Setting(
                    building_id=building_id,
                    device_category=category_enum,
                    alert_limit_kwh=limit_val
                )
                self.session.add(new_setting)
                
        # Commit the transaction to save all limits safely
        self.session.commit()