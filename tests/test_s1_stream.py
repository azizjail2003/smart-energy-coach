"""
Automated test suite for Subsystem 1 Event-Driven Stream Processing (subsystems/s1_stream.py).
Validates ABC enforcement, Inheritance & Polymorphism, Operator Overloading (| and +),
Iterators & Generators, domain filtering/transformation, and AnalyticsService integration.
"""

from collections.abc import Iterator
from datetime import datetime
import inspect
import os
import tempfile
import unittest

import config
from subsystems.s1_analytics import (
    AlertMonitor,
    AnalyticsService,
    EnergyReading,
    EnergySimulator,
    SQLiteRepository,
)
from subsystems.s1_stream import (
    CarbonAndComfortTransformer,
    InactiveMeterFilter,
    LoadBalanceAndTariffTransformer,
    MeterReadingStream,
    StreamEnergyReading,
    StreamPipeline,
    StreamProcessor,
)


class TestS1StreamFramework(unittest.TestCase):
    """Unit and integration tests for the S1 Stream Processing Framework."""

    def setUp(self) -> None:
        self.simulator = EnergySimulator(seed=42)
        self.fixed_peak_time = datetime(2026, 5, 10, 13, 0, 0)      # 13:00 (Peak)
        self.fixed_offpeak_time = datetime(2026, 5, 10, 22, 0, 0)   # 22:00 (Off-Peak)

    # 1. ABC Contract Enforcement
    def test_01_stream_processor_abc_cannot_be_instantiated_directly(self) -> None:
        """Verifies StreamProcessor is a strict ABC and enforces process_event."""
        with self.assertRaises(TypeError):
            StreamProcessor()  # type: ignore[abstract]

        class IncompleteProcessor(StreamProcessor):
            pass

        with self.assertRaises(TypeError):
            IncompleteProcessor()  # type: ignore[abstract]

    # 2. Inheritance & Polymorphism (Payload & Processors)
    def test_02_inheritance_and_polymorphism_across_payload_and_processors(self) -> None:
        """Verifies StreamEnergyReading and all 4 processors obey polymorphic contracts."""
        base = self.simulator.generate_reading("Heating", ts=self.fixed_peak_time)
        upgraded = StreamEnergyReading.from_reading(base)

        self.assertIsInstance(upgraded, EnergyReading)
        self.assertIsInstance(upgraded, StreamEnergyReading)
        self.assertTrue(upgraded.validate())

        processors: list[StreamProcessor] = [
            InactiveMeterFilter(min_kwh_threshold=0.05),
            CarbonAndComfortTransformer(),
            LoadBalanceAndTariffTransformer(),
            StreamPipeline([InactiveMeterFilter(min_kwh_threshold=0.05)]),
        ]
        for proc in processors:
            self.assertIsInstance(proc, StreamProcessor)
            event_out = proc.process_event(base)
            self.assertIsInstance(event_out, StreamEnergyReading)
            stream_out = list(proc.process_stream([base]))
            self.assertEqual(len(stream_out), 1)
            self.assertIsInstance(stream_out[0], StreamEnergyReading)

    # 3. Iterator Protocol on MeterReadingStream
    def test_03_meter_reading_stream_iterator_protocol_and_5s_intervals(self) -> None:
        """Verifies __iter__, __next__, StopIteration, and 5-second timestamp steps."""
        stream = MeterReadingStream(
            simulator=self.simulator,
            building_id="library",
            start_time=self.fixed_peak_time,
            interval_seconds=5,
            max_events=6,
        )
        self.assertIs(iter(stream), stream)

        events = []
        while True:
            try:
                events.append(next(stream))
            except StopIteration:
                break

        self.assertEqual(len(events), 6)
        self.assertEqual(events[0].timestamp, self.fixed_peak_time)
        self.assertEqual(
            (events[4].timestamp - events[0].timestamp).total_seconds(), 5.0
        )

    # 4. Filter Stage: Corrupt, Disallowed, and Sub-Threshold Readings
    def test_04_inactive_meter_filter_drops_invalid_and_standby_readings(self) -> None:
        """Verifies InactiveMeterFilter filters out low kWh, bad devices, and invalid temps."""
        meter_filter = InactiveMeterFilter(
            min_kwh_threshold=0.10, allowed_devices={"Heating", "Servers"}
        )

        # Sub-threshold standby noise (0.02 kWh < 0.10) -> None
        standby = StreamEnergyReading(
            timestamp=self.fixed_peak_time,
            device_type="Heating",
            kwh=0.02,
            room_temp=21.0,
        )
        self.assertIsNone(meter_filter.process_event(standby))

        # Disallowed device ("Lighting" not in allowed_devices) -> None
        disallowed = StreamEnergyReading(
            timestamp=self.fixed_peak_time,
            device_type="Lighting",
            kwh=0.50,
            room_temp=21.0,
        )
        self.assertIsNone(meter_filter.process_event(disallowed))

        # Corrupt readings (negative kWh and out-of-range room_temp) -> caught and returns None
        corrupt_kwh = StreamEnergyReading(
            timestamp=self.fixed_peak_time,
            device_type="Heating",
            kwh=-5.0,
            room_temp=21.0,
        )
        corrupt_temp = StreamEnergyReading(
            timestamp=self.fixed_peak_time,
            device_type="Heating",
            kwh=1.0,
            room_temp=95.0,
        )
        self.assertIsNone(meter_filter.process_event(corrupt_kwh))
        self.assertIsNone(meter_filter.process_event(corrupt_temp))

        # Valid active reading -> survives
        valid = StreamEnergyReading(
            timestamp=self.fixed_peak_time,
            device_type="Servers",
            kwh=1.25,
            room_temp=21.0,
        )
        survived = meter_filter.process_event(valid)
        self.assertIsNotNone(survived)
        self.assertEqual(survived.kwh, 1.25)

    # 5. Transform Stage 1: Carbon and Comfort Enrichment
    def test_05_carbon_and_comfort_transformer_enriches_metrics(self) -> None:
        """Verifies CO2 kg, comfort index (K), and sustainability score computation."""
        transformer = CarbonAndComfortTransformer()
        raw = StreamEnergyReading(
            timestamp=self.fixed_peak_time,
            device_type="Heating",
            kwh=2.0,
            room_temp=21.0,  # Ideal temperature -> comfort_index = 1.0
            co2_kg=0.0,
            sustainability_score=0,
        )
        enriched = transformer.process_event(raw)
        self.assertIsNotNone(enriched)
        self.assertEqual(enriched.co2_kg, round(2.0 * config.CO2_FACTOR_KG_PER_KWH, 2))
        self.assertEqual(enriched.comfort_index, 1.0)
        self.assertGreater(enriched.sustainability_score, 0)

    # 6. Transform Stage 2: Load Balance, Peak Tariff (13:00 vs 22:00), and AlertMonitor
    def test_06_load_balance_and_tariff_transformer_tracks_state_and_tariffs(self) -> None:
        """Verifies cumulative load, device share %, peak tariff (13:00 vs 22:00), and alerts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SQLiteRepository(os.path.join(tmpdir, "limits.db"))
            alert_monitor = AlertMonitor(repo)
            transformer = LoadBalanceAndTariffTransformer(
                alert_monitor=alert_monitor,
                peak_hours=(8, 18),
                peak_tariff_multiplier=1.25,
            )

            # Event 1: Heating 2.0 kWh at 13:00 (Peak hour)
            ev1 = StreamEnergyReading(
                timestamp=self.fixed_peak_time,
                device_type="Heating",
                kwh=2.0,
                room_temp=21.0,
                building_id="library",
            )
            res1 = transformer.process_event(ev1)
            self.assertTrue(res1.is_peak_tariff)
            self.assertEqual(res1.building_load_balance_kwh, 2.0)
            self.assertEqual(res1.device_load_share_pct, 100.0)
            expected_peak_cost = round(
                round(2.0 * config.COST_EUR_PER_KWH, 2) * 1.25, 2
            )
            self.assertEqual(res1.cost_eur, expected_peak_cost)
            self.assertFalse(res1.alert_triggered)

            # Event 2: Servers 6.0 kWh at 22:00 (Off-Peak hour, exceeds default limit)
            ev2 = StreamEnergyReading(
                timestamp=self.fixed_offpeak_time,
                device_type="Servers",
                kwh=6.0,
                room_temp=21.0,
                building_id="library",
            )
            res2 = transformer.process_event(ev2)
            self.assertFalse(res2.is_peak_tariff)
            self.assertEqual(res2.building_load_balance_kwh, 8.0)
            self.assertEqual(res2.device_load_share_pct, 75.0)  # 6.0 / 8.0 = 75%
            self.assertEqual(res2.cost_eur, round(6.0 * config.COST_EUR_PER_KWH, 2))
            self.assertTrue(res2.alert_triggered)

            transformer.reset_balances()
            self.assertEqual(len(transformer.building_loads), 0)

    # 7. Operator Overloading (| and +) and Exact Steps Order
    def test_07_operator_overloading_or_and_add_creates_flat_pipeline(self) -> None:
        """Verifies | and + compose StreamProcessors in exact order and reject invalid types."""
        f_stage = InactiveMeterFilter(min_kwh_threshold=0.05)
        c_stage = CarbonAndComfortTransformer()
        l_stage = LoadBalanceAndTariffTransformer()

        pipe_or = f_stage | c_stage | l_stage
        pipe_add = (f_stage + c_stage) + l_stage
        pipe_mixed = (f_stage | c_stage) + l_stage

        expected_order = [f_stage, c_stage, l_stage]
        self.assertIsInstance(pipe_or, StreamPipeline)
        self.assertEqual(pipe_or.steps, expected_order)
        self.assertEqual(pipe_add.steps, expected_order)
        self.assertEqual(pipe_mixed.steps, expected_order)

        with self.assertRaises(TypeError):
            _ = f_stage | "invalid_processor"  # type: ignore[operator]
        with self.assertRaises(TypeError):
            _ = f_stage + 123  # type: ignore[operator]

    # 8. Generator Evaluation via process_stream (yield)
    def test_08_generator_process_stream_yields_lazily(self) -> None:
        """Verifies process_stream returns a lazy generator yielding only valid events."""
        pipeline = InactiveMeterFilter(min_kwh_threshold=0.10) | CarbonAndComfortTransformer()
        raw_events = [
            StreamEnergyReading(self.fixed_peak_time, "Heating", 0.01, 21.0),  # Dropped
            StreamEnergyReading(self.fixed_peak_time, "Heating", 1.50, 21.0),  # Kept
            StreamEnergyReading(self.fixed_peak_time, "Servers", 0.02, 21.0),  # Dropped
            StreamEnergyReading(self.fixed_peak_time, "Servers", 1.10, 21.0),  # Kept
        ]

        gen = pipeline.process_stream(raw_events)
        self.assertTrue(inspect.isgenerator(gen))
        self.assertIsInstance(gen, Iterator)
        results = list(gen)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].kwh, 1.50)
        self.assertEqual(results[1].kwh, 1.10)

    # 9. Bound StreamPipeline Iterator Protocol (__iter__ & __next__)
    def test_09_bound_pipeline_iterator_protocol_and_unbound_error(self) -> None:
        """Verifies iter() and next() on bound StreamPipeline skip filtered events until StopIteration."""
        pipeline = (
            InactiveMeterFilter(min_kwh_threshold=0.05)
            | CarbonAndComfortTransformer()
            | LoadBalanceAndTariffTransformer()
        )

        # Iterating without binding a source must raise RuntimeError
        with self.assertRaises(RuntimeError):
            iter(pipeline)
        with self.assertRaises(RuntimeError):
            next(pipeline)

        stream = MeterReadingStream(
            simulator=self.simulator,
            start_time=self.fixed_peak_time,
            max_events=10,
            inactive_probability=0.5,
        )
        bound_pipeline = pipeline.bind(stream)
        self.assertIs(iter(bound_pipeline), bound_pipeline)

        output = []
        while True:
            try:
                output.append(next(bound_pipeline))
            except StopIteration:
                break

        self.assertGreater(len(output), 0)
        self.assertLessEqual(len(output), 10)
        self.assertTrue(all(e.kwh >= 0.05 for e in output))

    # 10. End-to-End Integration with AnalyticsService & SQLite Persistence
    def test_10_analytics_service_stream_live_readings_persists_to_sqlite(self) -> None:
        """Verifies AnalyticsService.stream_live_readings processes, persists, and returns dicts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_stream.db")
            service = AnalyticsService(db_path)

            serialized_batch = service.stream_live_readings(
                building_id="library",
                max_events=8,
                min_kwh_threshold=0.05,
                persist=True,
            )
            self.assertEqual(len(serialized_batch), 8)
            self.assertTrue(all(isinstance(d, dict) for d in serialized_batch))
            self.assertEqual(service.repository.count_readings("library"), 8)
            self.assertIn("energy_today", service.get_dashboard_summary("library"))


if __name__ == "__main__":
    unittest.main()