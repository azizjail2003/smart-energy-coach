from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from subsystems.s3_models import Base, Building, Device, DeviceCategory
from subsystems.s3_repository import MySQLRepository
from datetime import datetime

# --- Create an in-memory SQLite engine ---
engine = create_engine('sqlite:///:memory:')

# This physically creates the 7 tables defined in s3_models.py
Base.metadata.create_all(engine) 

Session = sessionmaker(bind=engine)
session = Session()

# --- Create a dummy building ---
test_building = Building(
    building_id="campus-A", 
    name="Central Library", 
    total_area_m2=1500.50
)
session.add(test_building)
session.commit()

# --- Instantiate the repository ---
repo = MySQLRepository(session)

# --- Test the newly written methods ---
print("--- Saving limits to the database... ---")
new_limits = {'HVAC': 25.5, 'Lighting': 12.0}
repo.save_limits("campus-A", new_limits)
print("Limits saved successfully!")

print("\n--- Retrieving limits from the database... ---")
retrieved_limits = repo.get_limits("campus-A")
print(f"Result obtained: {retrieved_limits}")

# --- Test Time-Series and Alerts ---
print("\n--- Preparing device for logging... ---")
# Create a dummy device first (required by EnergyLog foreign key)
test_device = Device(
    building_id="campus-A",
    category=DeviceCategory.HVAC,
    name="Main Chiller",
    rated_power_kw=150.0
)
session.add(test_device)
session.commit()

print("--- Saving new energy log and alert... ---")
current_time = datetime.now()

# Test save_energy_log
repo.save_energy_log(
    building_id="campus-A",
    device_id=test_device.device_id,
    timestamp=current_time,
    consumption=18.5,
    co2=12.2,
    temp=22.5
)

# Test save_alert
repo.save_alert(
    building_id="campus-A",
    timestamp=current_time,
    alert_type="HIGH_CONSUMPTION",
    message="HVAC exceeded hourly limit",
    threshold=15.0,
    value=18.5
)

print("Log and Alert saved successfully!")