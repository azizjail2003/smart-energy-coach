import unittest
from subsystems.s3_coach.s3_models import SourceEnum

class TestS3Models(unittest.TestCase):
    def test_source_enum_valid_values(self):
        #Validates that the enumeration protects database integrity
        self.assertEqual(SourceEnum.nvidia.value, "nvidia")
        self.assertEqual(SourceEnum.fallback.value, "fallback")
        self.assertEqual(SourceEnum.openai.value, "openai")