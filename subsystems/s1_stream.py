"""
Event-Driven Stream Processing Framework for Subsystem 1 (Monitoring, Simulation & Analytics).
Implements Abstract Base Classes, Inheritance & Polymorphism, Operator Overloading (| and +),
and Iterators & Generators for high-frequency smart meter telemetry.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta

import config
from subsystems.s1_analytics import (
    AlertMonitor,
    EnergyReading,
    EnergySimulator,
    ScoreCalculator,
)

@dataclass
class StreamEnergyReading(EnergyReading):
    """
    Polymorphic subclass of EnergyReading enriched with real-time stream analytics.
    Remains 100% compatible with SQLiteRepository.insert_readings and AnalyticsService.
    """

    co2_kg: float = 0.0
    sustainability_score: int = 0
    building_id: str = config.DEFAULT_BUILDING_ID
    comfort_index: float = 0.0
    cost_eur: float = 0.0
    is_peak_tariff: bool = False
    building_load_balance_kwh: float = 0.0
    device_load_share_pct: float = 0.0
    alert_triggered: bool = False

    @classmethod
    def from_reading(cls, reading: EnergyReading) -> StreamEnergyReading:
        """Upgrades a standard EnergyReading instance into a StreamEnergyReading."""
        if isinstance(reading, cls):
            return reading
        return cls(
            timestamp=reading.timestamp,
            device_type=reading.device_type,
            kwh=reading.kwh,
            room_temp=reading.room_temp,
            co2_kg=reading.co2_kg,
            sustainability_score=reading.sustainability_score,
            building_id=reading.building_id,
        )



class MeterReadingStream(Iterator[StreamEnergyReading]):
    """
    Iterator that simulates high-frequency IoT smart meter telemetry across
    a building's device categories in round-robin order.
    """

    def __init__(
        self,
        simulator: EnergySimulator | None = None,
        building_id: str = config.DEFAULT_BUILDING_ID,
        start_time: datetime | None = None,
        interval_seconds: int = 5,
        max_events: int | None = None,
        inactive_probability: float = 0.0,
    ) -> None:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be greater than 0.")
        if max_events is not None and max_events < 0:
            raise ValueError("max_events cannot be negative.")
        if not (0.0 <= inactive_probability <= 1.0):
            raise ValueError("inactive_probability must be between 0.0 and 1.0.")

        self.simulator: EnergySimulator = simulator or EnergySimulator()
        self.building_id: str = building_id
        self.current_time: datetime = start_time or datetime.now()
        self.interval_seconds: int = interval_seconds
        self.max_events: int | None = max_events
        self.inactive_probability: float = inactive_probability

        self._events_emitted: int = 0
        self._device_index: int = 0

    def __iter__(self) -> MeterReadingStream:
        """Returns the stream iterator instance."""
        return self

    def __next__(self) -> StreamEnergyReading:
        """Generates and emits the next high-frequency smart meter reading."""
        if self.max_events is not None and self._events_emitted >= self.max_events:
            raise StopIteration

        devices = self.simulator.devices
        device = devices[self._device_index]
        event_timestamp = self.current_time

        base_reading = self.simulator.generate_reading(
            device=device,
            ts=event_timestamp,
            building_id=self.building_id,
        )
        stream_event = StreamEnergyReading.from_reading(base_reading)
        # Preserve exact 5-second incremental timestamp (generate_reading zeroes out seconds)
        stream_event.timestamp = event_timestamp

        # Deterministically inject low-power standby noise when configured
        if (
            self.inactive_probability > 0.0
            and self.simulator._rng.random() < self.inactive_probability
        ):
            stream_event.kwh = round(self.simulator._rng.uniform(0.0, 0.02), 4)
            stream_event.co2_kg = self.simulator.calculator.calc_co2(stream_event.kwh)

        self._events_emitted += 1
        self._device_index = (self._device_index + 1) % len(devices)
        if self._device_index == 0:
            self.current_time = self.current_time + timedelta(
                seconds=self.interval_seconds
            )

        return stream_event

class StreamProcessor(ABC):
    """
    Abstract base class defining the uniform contract for stream processing stages.
    Supports lazy generator evaluation and pipeline composition via | and +.
    """

    @abstractmethod
    def process_event(self, event: EnergyReading) -> StreamEnergyReading | None:
        """
        Processes a single EnergyReading event.
        Returns a transformed StreamEnergyReading, or None if filtered out.
        """
        raise NotImplementedError

    def process_stream(
        self, stream: Iterable[EnergyReading]
    ) -> Iterator[StreamEnergyReading]:
        """
        Generator method that lazily evaluates an upstream iterable of readings,
        yielding only valid transformed StreamEnergyReading events.
        """
        for raw_event in stream:
            processed = self.process_event(raw_event)
            if processed is not None:
                yield processed

    def __or__(self, other: StreamProcessor) -> StreamPipeline:
        """Overloads the bitwise OR operator (|) to chain stream processors."""
        if not isinstance(other, StreamProcessor):
            return NotImplemented
        return StreamPipeline([self, other])

    def __add__(self, other: StreamProcessor) -> StreamPipeline:
        """Overloads the addition operator (+) to combine stream processors."""
        if not isinstance(other, StreamProcessor):
            return NotImplemented
        return StreamPipeline([self, other])

class StreamPipeline(StreamProcessor, Iterator[StreamEnergyReading]):
    """
    Composite pipeline chaining multiple StreamProcessor stages sequentially.
    Acts polymorphically as a StreamProcessor and directly as an Iterator when bound.
    """

    def __init__(self, processors: list[StreamProcessor] | None = None) -> None:
        self.steps: list[StreamProcessor] = []
        self._source_iterator: Iterator[EnergyReading] | None = None

        for proc in processors or []:
            if not isinstance(proc, StreamProcessor):
                raise TypeError(
                    f"Expected StreamProcessor instance, got {type(proc).__name__}."
                )
            if isinstance(proc, StreamPipeline):
                self.steps.extend(proc.steps)
            else:
                self.steps.append(proc)

    def process_event(self, event: EnergyReading) -> StreamEnergyReading | None:
        """Passes an event sequentially through all stages, short-circuiting on None."""
        current: EnergyReading | StreamEnergyReading | None = (
            StreamEnergyReading.from_reading(event)
        )
        for step in self.steps:
            if current is None:
                return None
            current = step.process_event(current)
        return current

    def bind(self, source: Iterable[EnergyReading]) -> StreamPipeline:
        """Binds an upstream iterable source to this pipeline for direct iteration."""
        self._source_iterator = iter(source)
        return self

    def __iter__(self) -> StreamPipeline:
        """Validates that a source stream is bound and returns the pipeline iterator."""
        if self._source_iterator is None:
            raise RuntimeError(
                "No upstream source bound to StreamPipeline. Call pipeline.bind(source) first."
            )
        return self

    def __next__(self) -> StreamEnergyReading:
        """Pulls events from the bound source until one survives all pipeline stages."""
        if self._source_iterator is None:
            raise RuntimeError(
                "No upstream source bound to StreamPipeline. Call pipeline.bind(source) first."
            )
        while True:
            raw_event = next(self._source_iterator)
            result = self.process_event(raw_event)
            if result is not None:
                return result


class InactiveMeterFilter(StreamProcessor):
    """
    Filters out corrupt, invalid, disallowed, or sub-threshold standby meter readings.
    """

    def __init__(
        self,
        min_kwh_threshold: float = 0.05,
        allowed_devices: set[str] | None = None,
    ) -> None:
        if min_kwh_threshold < 0:
            raise ValueError("min_kwh_threshold cannot be negative.")
        self.min_kwh_threshold: float = min_kwh_threshold
        self.allowed_devices: set[str] | None = (
            set(allowed_devices) if allowed_devices is not None else None
        )

    def process_event(self, event: EnergyReading) -> StreamEnergyReading | None:
        """Validates reading integrity, device whitelist, and minimum power threshold."""
        try:
            event.validate()
        except (ValueError, TypeError, AttributeError):
            return None

        if (
            self.allowed_devices is not None
            and event.device_type not in self.allowed_devices
        ):
            return None

        if event.kwh < self.min_kwh_threshold:
            return None

        return StreamEnergyReading.from_reading(event)


class CarbonAndComfortTransformer(StreamProcessor):
    """
    Enriches valid stream events with carbon equivalents (CO2 kg), comfort index (K),
    and recalculated sustainability scores using S1's ScoreCalculator.
    """

    def __init__(self, calculator: ScoreCalculator | None = None) -> None:
        self.calculator: ScoreCalculator = calculator or ScoreCalculator()

    def process_event(self, event: EnergyReading) -> StreamEnergyReading | None:
        """Computes CO2 emissions, comfort index, and sustainability score."""
        stream_event = StreamEnergyReading.from_reading(event)
        stream_event.co2_kg = self.calculator.calc_co2(stream_event.kwh)
        stream_event.comfort_index = self.calculator.calc_comfort(stream_event.room_temp)
        score_breakdown = self.calculator.calc_sustainability_score(
            stream_event.kwh, stream_event.room_temp
        )
        stream_event.sustainability_score = int(score_breakdown["score"])
        return stream_event

class LoadBalanceAndTariffTransformer(StreamProcessor):
    """
    Stateful transformer that tracks cumulative building/device load balances,
    identifies peak-tariff hours, calculates dynamic EUR costs, and flags threshold alerts.
    """

    def __init__(
        self,
        calculator: ScoreCalculator | None = None,
        alert_monitor: AlertMonitor | None = None,
        peak_hours: tuple[int, int] = (8, 18),
        peak_tariff_multiplier: float = 1.25,
    ) -> None:
        if peak_tariff_multiplier <= 0:
            raise ValueError("peak_tariff_multiplier must be greater than 0.")
        self.calculator: ScoreCalculator = calculator or ScoreCalculator()
        self.alert_monitor: AlertMonitor | None = alert_monitor
        self.peak_hours: tuple[int, int] = peak_hours
        self.peak_tariff_multiplier: float = peak_tariff_multiplier

        self.building_loads: dict[str, float] = {}
        self.device_loads: dict[str, dict[str, float]] = {}

    def reset_balances(self) -> None:
        """Clears cumulative load balances for all buildings and devices."""
        self.building_loads.clear()
        self.device_loads.clear()

    def process_event(self, event: EnergyReading) -> StreamEnergyReading | None:
        """Updates running load balances, tariff flags, EUR costs, and alert flags."""
        stream_event = StreamEnergyReading.from_reading(event)
        b_id = stream_event.building_id
        dev = stream_event.device_type

        # 1. Update cumulative building and per-device load balances
        new_building_total = self.building_loads.get(b_id, 0.0) + stream_event.kwh
        self.building_loads[b_id] = new_building_total

        if b_id not in self.device_loads:
            self.device_loads[b_id] = {}
        new_device_total = self.device_loads[b_id].get(dev, 0.0) + stream_event.kwh
        self.device_loads[b_id][dev] = new_device_total

        stream_event.building_load_balance_kwh = round(new_building_total, 2)
        if new_building_total > 0:
            stream_event.device_load_share_pct = round(
                (new_device_total / new_building_total) * 100.0, 1
            )
        else:
            stream_event.device_load_share_pct = 0.0

        # 2. Evaluate peak-tariff window and dynamic EUR cost
        start_hour, end_hour = self.peak_hours
        is_peak = start_hour <= stream_event.timestamp.hour <= end_hour
        stream_event.is_peak_tariff = is_peak

        base_cost = self.calculator.calc_cost(stream_event.kwh)
        if is_peak:
            stream_event.cost_eur = round(base_cost * self.peak_tariff_multiplier, 2)
        else:
            stream_event.cost_eur = round(base_cost, 2)

        # 3. Check device threshold limits to flag anomalies
        if self.alert_monitor is not None:
            limits = self.alert_monitor.get_limits_for_building(b_id)
        else:
            limits = dict(config.DEFAULT_LIMITS)

        device_limit = limits.get(dev)
        stream_event.alert_triggered = (
            device_limit is not None and stream_event.kwh > device_limit
        )

        return stream_event

def build_default_pipeline(
    calculator: ScoreCalculator | None = None,
    alert_monitor: AlertMonitor | None = None,
    min_kwh_threshold: float = 0.05,
) -> StreamPipeline:
    """
    Constructs the standard 3-stage S1 stream processing pipeline using the
    overloaded bitwise OR (|) operator.
    """
    calc = calculator or ScoreCalculator()
    return (
        InactiveMeterFilter(min_kwh_threshold=min_kwh_threshold)
        | CarbonAndComfortTransformer(calculator=calc)
        | LoadBalanceAndTariffTransformer(calculator=calc, alert_monitor=alert_monitor)
    )