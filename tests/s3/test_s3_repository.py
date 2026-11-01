import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from subsystems.s3_coach.s3_models import Base
from subsystems.s3_coach.s3_repository import MySQLRepository

class TestS3Repository(unittest.TestCase):
    def setUp(self):
        # Runs before each test. Creates a temporary DB in RAM.
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.session = self.SessionLocal()
        self.repo = MySQLRepository(self.session)

    def tearDown(self):
        # Runs after each test. Destroys the temporary DB to prevent data leaks.
        self.session.close()
        Base.metadata.drop_all(self.engine)

    def test_save_and_get_ai_recommendation(self):
        # Write simulation (Save)
        self.repo.save_ai_recommendation(
            building_id="campus-A",
            context_hash="test-hash-12345",
            tone="analytical",
            response='{"tip": "Test"}',
            source="fallback",
            tokens=0
        )
        
        # Read simulation (Get)
        cached = self.repo.get_cached_recommendation(
            building_id="campus-A",
            context_hash="test-hash-12345"
        )
        
        # Assertions
        self.assertIsNotNone(cached)
        self.assertEqual(cached, '{"tip": "Test"}')