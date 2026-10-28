"""Stage 1 energy data model for the Energy Simulation and Analytics Engine."""

from dataclasses import asdict, dataclass
from pathlib import Path
import sys

try:
    import config
except ModuleNotFoundError as error:
    if error.name != "config":
        raise
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import config


@dataclass
class EnergyReading:
    """Validated energy measurement shared by analytics and web templates."""

    timestamp: str
    device_type: str
    kwh: float
    room_temp: float
    co2_kg: float
    sustainability_score: int

    @property
    def score(self) -> int:
        """Return the sustainability score using the UML-compatible name."""
        return self.sustainability_score

    def validate(self) -> bool:
        """Validate the reading before it is written to SQLite.

        Raises:
            ValueError: If energy, temperature, or device data is invalid.
        """
        # FR10 and NFR4: reject measurements that would compromise data integrity.
        if self.kwh < 0:
            raise ValueError("Energy reading (kWh) cannot be negative.")
        if not (0.0 <= self.room_temp <= 45.0):
            raise ValueError("Room temperature out of realistic bounds (0-45 C).")
        if self.device_type not in config.DEVICES:
            raise ValueError(f"Unknown device type: {self.device_type}")
        return True

    def to_dict(self) -> dict:
        """Return the reading as a standard dictionary for template use."""
        # NFR6: use the standard dictionary contract shared with other subsystems.
        # NFR8 and NFR9: typed fields and clear documentation keep the contract readable.
        return asdict(self)
