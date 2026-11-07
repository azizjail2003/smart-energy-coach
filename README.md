# AI-Powered Smart Energy Management System – Homework Assignment 4

Group 7, Fachhochschule Dortmund. A web application that monitors the energy use of campus buildings, scores their sustainability and gives advice through an AI coach.

**Homework Assignment 4: error handling and testing.** Each subsystem has its own error-handling class, and the application has 15 automated tests written with Flask's test client.

## Team Overview

| Member | Subsystem | Folder |
| --- | --- | --- |
| Abdelhamid Ahbane | S1 – Monitoring, Simulation & Analytics Engine | `subsystems/s1_analytics` |
| Abdelaziz Jail | S2 – Web Interface & Visualization (Flask) | `subsystems/s2_web` |
| Nestor David Carrizo | S3 – AI Coach, Data Persistence & Deployment | `subsystems/s3_ai_data` |

## System Design

Error-handling classes of each subsystem.

### S2 – Web Interface & Visualization

Every error that S2 raises on purpose inherits from `S2Error`. The `ErrorHandler` class catches these, and any unexpected crash, and answers with a friendly page or a JSON message with the right status code. Users never see a stack trace. Code: `subsystems/s2_web/errors.py`.

```mermaid
classDiagram
    direction LR
    class S2Error {
        +status = 500
        +code = "server_error"
        +message
    }
    class InvalidInputError {
        +status = 400
        +code = "invalid_parameter"
    }
    class ServiceUnavailableError {
        +status = 503
        +code = "service_unavailable"
    }
    class ErrorHandler {
        +init_app(app)
        +respond(status, code, message)
        +handle_s2_error(error)
        +handle_csrf_error(error)
        +handle_http_error(error)
        +handle_unexpected_error(error)
    }
    Exception <|-- S2Error
    S2Error <|-- InvalidInputError
    S2Error <|-- ServiceUnavailableError
    ErrorHandler ..> S2Error : catches
```

| Class | When it is used | Answer |
| --- | --- | --- |
| `InvalidInputError` | Unknown building, bad date, missing parameter, invalid coach question | 400 |
| `ServiceUnavailableError` | S1 (analytics) or S3 (AI coach) does not answer: `PageView.kpis` and `CoachView` turn a `ConnectionError` or `TimeoutError` into this error. On the dashboard a missing coach only hides the tip. | 503 |
| `ErrorHandler` | Registered once in `create_app`; also handles 404, 405, an expired form token and unexpected crashes (500) | Error page, or JSON for `/api/` |

### S1 – Monitoring, Simulation & Analytics Engine


Five collaborating UML classes (plus the `SQLiteRepository` offline persistence adapter). `AnalyticsService` is the facade consumed by S2 and S3; it coordinates deterministic device simulation (`EnergySimulator`), pure KPI and sustainability math (`ScoreCalculator`), per-building threshold checks (`AlertMonitor`), and validated measurement records (`EnergyReading`).

```mermaid
classDiagram
    direction TB

    class AnalyticsService {
        <<Facade>>
        +str db_path
        +SQLiteRepository repository
        +ScoreCalculator calculator
        +EnergySimulator simulator
        +AlertMonitor alert_monitor
        +save_reading(reading: EnergyReading) None
        +seed_if_empty(days: int, building_id: str) int
        +simulate_live_step(building_id: str) list~dict~
        +get_dashboard_summary(building_id: str, limits: dict) dict
        +get_score(building_id: str) dict
        +get_aggregates(period: str, category: str, building_id: str) dict
        +compute_week_over_week(building_id: str) dict
        +check_alerts(building_id: str, limits: dict, recent_rows: list) list~dict~
        +get_alerts(building_id: str, limits: dict, recent_rows: list) list~dict~
        +simulate_scenario(current_summary: dict, heating_delta_c: float, light_reduction_pct: float, building_id: str) dict
        +estimate_scenario(changes: dict, building_id: str) dict
    }

    class EnergySimulator {
        +ScoreCalculator calculator
        +int seed
        +list~str~ devices
        +dict~str, float~ base_loads
        +set_seed(seed: int) None
        +generate_reading(device: str, ts: datetime, building_id: str) EnergyReading
        +seed_history(days: int, building_id: str, reference_time: datetime) list~EnergyReading~
    }

    class ScoreCalculator {
        +float co2_factor
        +float cost_factor
        +float cost_per_kwh
        +float ideal_temp
        +calc_co2(kwh: float) float
        +calc_cost(kwh: float) float
        +calc_comfort(room_temp: float) float
        +calc_sustainability_score(total_hourly_kwh: float, room_temp: float) dict
    }

    class AlertMonitor {
        +SQLiteRepository repository
        +dict~str, float~ default_limits
        +get_limits_for_building(building_id: str) dict~str, float~
        +check_alerts(building_id: str, readings: list, limits: dict) list~dict~
    }

    class EnergyReading {
        <<dataclass>>
        +datetime timestamp
        +str device_type
        +float kwh
        +float room_temp
        +float co2_kg
        +int sustainability_score
        +str building_id
        +int score
        +validate() bool
        +to_dict() dict
    }

    class SQLiteRepository {
        <<Repository>>
        +str db_path
        +count_readings(building_id: str) int
        +insert_readings(readings: list~EnergyReading~) None
        +fetch_readings(building_id: str, limit: int) list~dict~
        +get_limits_for_building(building_id: str) dict~str, float~
        +save_limit(building_id: str, device_type: str, limit: float) None
    }

    AnalyticsService *-- "1" ScoreCalculator : owns
    AnalyticsService *-- "1" EnergySimulator : owns
    AnalyticsService *-- "1" AlertMonitor : owns
    AnalyticsService o-- "1" SQLiteRepository : delegates persistence
    EnergySimulator o-- "1" ScoreCalculator : computes score & CO2
    EnergySimulator ..> EnergyReading : creates & validates
    AlertMonitor o-- "1" SQLiteRepository : loads thresholds
    SQLiteRepository ..> EnergyReading : persists
```

| Class | File | Role |
| --- | --- | --- |
| `AnalyticsService` | `subsystems/s1_analytics.py` | Facade coordinating seeding, live steps, KPIs, scores, aggregations, alerts, and what-if scenarios. |
| `EnergySimulator` | `subsystems/s1_analytics.py` | Deterministic generator (`seed=42`) for live device telemetry and 14-day hourly history (`1,344` rows/building). |
| `ScoreCalculator` | `subsystems/s1_analytics.py` | Stateless mathematical engine for CO₂ (`0.38 kg/kWh`), cost (`0.35 €/kWh`), comfort (`21.0 °C`), and score (`0–100`). |
| `AlertMonitor` | `subsystems/s1_analytics.py` | Loads per-building thresholds from storage, merges defaults, and detects device limit breaches. |
| `EnergyReading` | `subsystems/s1_analytics.py` | Dataclass validating non-negative kWh, realistic temperature (`0–45 °C`), device category, and building ID. |

| Exception Class | Inherits From | When Raised |
| --- | --- | --- |
| `AnalyticsError` | `Exception` | Base exception for all Subsystem 1 errors. |
| `InvalidReadingError` | `AnalyticsError`, `ValueError` | Invalid kWh (`< 0`), temperature (`∉ [0, 45] °C`), device type, building ID, or timestamp. |
| `ThresholdConfigurationError` | `AnalyticsError`, `ValueError` | Negative alert limit or blank building ID when saving thresholds. |
| `ScenarioSimulationError` | `AnalyticsError`, `TypeError`, `ValueError` | Unsupported `current_summary` argument type in scenario simulation. |
| `RepositoryError` | `AnalyticsError`, `sqlite3.Error` | SQLite persistence or connection failure in `SQLiteRepository`. |


---

## Tests

The 15 error-handling tests for S2 are in `tests/s2/test_errors.py`. Each test checks one case: the class hierarchy, 400 for bad input and an expired form, 404, 405, 500 without details, and 503 when S1 or S3 is down.

Tested with Python 3.12.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest tests/s2/test_errors.py -v
```

## Presentation 
https://drive.google.com/file/d/1G8hfVQlEG_Auu_9NAmw64GoZx8LJ-52z/view?usp=sharing

Team video (3 to 5 minutes): _link to be added after recording_.

---

Full S2 documentation (setup, structure, click path, JSON API): [`docs/s2/README.md`](docs/s2/README.md).
