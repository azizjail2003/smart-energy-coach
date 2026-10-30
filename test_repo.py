from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from subsystems.s3_models import Base, Building
from subsystems.s3_repository import MySQLRepository

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

# 3. Instantiate the repository
repo = MySQLRepository(session)

# 4. Test the newly written methods
print("--- Saving limits to the database... ---")
new_limits = {'HVAC': 25.5, 'Lighting': 12.0}
repo.save_limits("campus-A", new_limits)
print("Limits saved successfully!")

print("\n--- Retrieving limits from the database... ---")
retrieved_limits = repo.get_limits("campus-A")
print(f"Result obtained: {retrieved_limits}")