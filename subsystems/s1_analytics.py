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


class ScoreCalculator:
    """Calculate deterministic energy, carbon, cost, and comfort metrics."""

    def __init__(self) -> None:
        """Load scoring constants from the shared configuration module."""
        # NFR5: keep business constants configurable without changing the engine.
        self.co2_factor: float = config.CO2_FACTOR_KG_PER_KWH
        self.cost_factor: float = config.COST_EUR_PER_KWH
        self.cost_per_kwh: float = config.COST_EUR_PER_KWH
        self.ideal_temp: float = config.IDEAL_TEMP_C

    def calc_co2(self, kwh: float) -> float:
        """Return carbon emissions in kilograms for the supplied energy use."""
        # FR3 and NFR2: this pure calculation has no side effects or external state.
        return round(kwh * self.co2_factor, 2)

    def calc_cost(self, kwh: float) -> float:
        """Return energy cost in EUR for the supplied energy use."""
        # FR3 and NFR2: use the configured price and return a stable rounded value.
        return round(kwh * self.cost_factor, 2)

    def calc_comfort(self, room_temp: float) -> float:
        """Return a comfort index from 0.0 to 1.0 around the ideal temperature."""
        # FR4 and NFR2: clamp the deterministic comfort score to its valid range.
        diff = abs(room_temp - self.ideal_temp)
        return round(max(0.0, min(1.0, 1.0 - (diff / 10.0))), 2)

    def calc_sustainability_score(
        self, total_hourly_kwh: float, room_temp: float
    ) -> dict:
        """Return weighted sustainability subscores and the overall score."""
        # FR5, NFR1, and NFR2: combine normalized efficiency and comfort metrics.
        e_sub = round(max(0.0, min(1.0, 1.0 - (total_hourly_kwh / 4.0))), 2)
        c_sub = round(
            max(
                0.0,
                min(1.0, 1.0 - ((total_hourly_kwh * self.co2_factor) / 1.6)),
            ),
            2,
        )
        k_sub = self.calc_comfort(room_temp)
        total_score = int(round(100 * (0.40 * e_sub + 0.35 * c_sub + 0.25 * k_sub)))
        return {"score": total_score, "E": e_sub, "C": c_sub, "K": k_sub}
