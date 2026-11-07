# AI-Powered Smart Energy Management System – Homework Assignment 3

Group 7, Fachhochschule Dortmund. A Flask web application that monitors the energy use of campus buildings, scores their sustainability and gives advice through an AI coach.

**Homework Assignment 3: web APIs and database access.** The Flask app (S2) shows data read from the database: S1 stores the energy readings and alert limits and calculates the figures from them, and S3 stores the AI coach's answers and returns them from its cache.

## Team Overview

| Member | Subsystem | Folder / Module |
| --- | --- | --- |
| Abdelhamid Ahbane | S1 – Monitoring, Simulation & Analytics Engine | `subsystems/s1_analytics.py` |
| Abdelaziz Jail | S2 – Web Interface & Visualization (Flask) | `subsystems/s2_web` |
| Nestor David Carrizo | S3 – AI Coach, Data Persistence & Deployment | `subsystems/s3_coach` |

## How the data flows

```mermaid
flowchart LR
    Browser -->|pages and JSON API| S2[S2 Flask app]
    S2 -->|readings, scores, alerts, limits| S1[S1 AnalyticsService]
    S1 --> DB1[(S1 database: energy readings, alert limits)]
    S2 -->|chat questions| S3[S3 AICoach]
    S3 -->|building context| S1
    S3 --> DB2[(S3 database: AI answers and cache)]
    S3 -.->|with an API key| LLM[NVIDIA or OpenAI]
```

- **Dashboard, History, Scenarios and Settings** read their figures from S1. Limits saved in Settings are written to S1's database and change the alerts straight away.
- **AI Coach** sends the question to S3. S3 adds the building's figures from S1, asks NVIDIA or OpenAI when an API key is set and otherwise its rule-based fallback, and stores every answer so the same question is answered from the cache.

## System Design

### S2 – Web Interface & Visualization

Six classes. `PageView` is the only class the browser reaches; it reads numbers from S1, shapes them with `ChartPresenter`, validates input with the two forms and asks `CoachView` for the AI tip. `S1AnalyticsAdapter` reads S1's data and returns it in the format the pages use. Every private attribute has a `@property` getter and setter.

```mermaid
classDiagram
    direction LR
    class PageView {
        -_analytics
        -_presenter
        -_coach
        +analytics «property»
        +presenter «property»
        +coach «property»
        +index(building, category)
        +history(building, period, category)
        +scenarios(building, form)
        +settings(building, form)
        +api_kpis() api_score() api_hourly() api_aggregates() api_alerts()
    }
    class ChartPresenter {
        -_timezone
        +timezone «property»
        +to_line_chart(points)
        +to_bar_chart(totals)
        +to_daily_chart(days)
        +sparkline(values)
    }
    class ScenarioForm {
        <<FlaskForm>>
        +heating_change
        +lighting_reduction
        +changes «property»
        +validate() bool
    }
    class ThresholdForm {
        <<FlaskForm>>
        +heating
        +lighting
        +servers
        +other
        +limits «property»
        +validate() bool
    }
    class CoachView {
        -_coach
        +coach «property»
        +page(building)
        +ask(question, tone, building)
        +status()
        +tips(building)
    }
    class S1AnalyticsAdapter {
        +get_kpis(building)
        +get_score(building)
        +get_hourly(building, day, category)
        +get_alerts(building)
        +estimate_scenario(building, heating, lighting)
        +get_limits(building) save_limits(building, limits)
    }
    PageView --> S1AnalyticsAdapter : reads data through
    PageView --> ChartPresenter : builds charts with
    PageView --> ScenarioForm : scenarios page
    PageView --> ThresholdForm : settings page
    PageView --> CoachView : AI tip on dashboard
```

| Class | File | Role |
| --- | --- | --- |
| `PageView` | `subsystems/s2_web/views/page_view.py` | Builds the context of every page and the payload of every JSON endpoint. |
| `ChartPresenter` | `subsystems/s2_web/presenter.py` | Turns readings into Chart.js data in the display timezone. |
| `ScenarioForm` | `subsystems/s2_web/forms.py` | What-if inputs: heating change (−3 to +3 °C) and lighting reduction (0 to 50 %). |
| `ThresholdForm` | `subsystems/s2_web/forms.py` | One alert limit per device type (0.1 to 20 kWh/h). |
| `CoachView` | `subsystems/s2_web/views/coach_view.py` | AI Coach page, chat answers and the dashboard tip, on top of the S3 coach. |
| `S1AnalyticsAdapter` | `subsystems/s2_web/services/s1_adapter.py` | Reads S1's readings, scores and alerts and turns them into the format the pages use (device names, time zone). |

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

### S3 – AI Coach, Data Persistence & Deployment

Six main classes. `AICoach` is the central orchestrator that S1 and S2 interact with; it manages caching via `MySQLRepository` and delegates generation to a strategy interface (`LLMClient`) implemented by `OpenAIClient`, `NVIDIAClient`, and `FallbackCoach`. Domain errors are handled through the `S3CoachError` exception hierarchy. Every private attribute uses `@property` getters and setters for state initialization and encapsulation.

```mermaid
classDiagram
    direction LR
    
    class LLMClient {
        <<Interface>>
        +generate_recommendation(payload, tone) str
    }
    
    class OpenAIClient {
        -_api_key
        -_client
        +api_key «property»
        -_setup_client()
        +generate_recommendation(payload, tone) str
    }
    
    class NVIDIAClient {
        -_api_key
        -_client
        +api_key «property»
        -_setup_client()
        +generate_recommendation(payload, tone) str
    }
    
    class FallbackCoach {
        -_engine_name
        +engine_name «property»
        -_setup_engine()
        +generate_recommendation(payload, tone) str
    }
    
    class MySQLRepository {
        -_session
        +session «property»
        -_setup_repository(session)
        +get_limits(building_id) dict
        +save_limits(building_id, limits)
        +save_energy_log(building_id, device_id, timestamp, consumption, co2, temp, comfort)
        +save_alert(building_id, timestamp, alert_type, message, threshold, value)
        +get_cached_recommendation(building_id, context_hash) str
        +save_ai_recommendation(building_id, context_hash, tone, response, source, tokens)
    }
    
    class AICoach {
        -_repo
        -_last_source
        -_fallback_engine
        -_nvidia_engine
        -_openai_engine
        +repo «property»
        +last_source «property»
        -_initialize_strategies()
        -_generate_hash(payload, tone) str
        +get_recommendation(building_id, payload, tone) str
        +ask(question, tone, building_id) dict
        +status() str
        +tips(building_id) list
    }

    class S3ConfigurationError {
        <<Exception>>
    }
    
    class S3DatabaseError {
        <<Exception>>
    }

    class S3APIError {
        <<Exception>>
    }

    LLMClient <|.. OpenAIClient : implements
    LLMClient <|.. NVIDIAClient : implements
    LLMClient <|.. FallbackCoach : implements
    
    AICoach *-- FallbackCoach : strategy
    AICoach *-- OpenAIClient : strategy
    AICoach *-- NVIDIAClient : strategy
    AICoach o-- MySQLRepository : persistence
    
    AICoach ..> S3ConfigurationError : raises
    AICoach ..> S3APIError : catches
    MySQLRepository ..> S3DatabaseError : raises
    MySQLRepository ..> S3ConfigurationError : raises
```

| Class | File | Role |
| --- | --- | --- |
| `AICoach` | `subsystems/s3_coach/s3_ai_coach.py` | Orchestrator that checks cache, attempts live APIs, and handles fallbacks. |
| `MySQLRepository` | `subsystems/s3_coach/s3_repository.py` | Handles database persistence and retrieves cached AI recommendations. |
| `LLMClient` | `subsystems/s3_coach/s3_ai_coach.py` | Abstract interface defining the contract for all AI recommendation engines. |
| `OpenAIClient` & `NVIDIAClient` | `subsystems/s3_coach/s3_ai_coach.py` | Live API strategies with secure environment key encapsulation. |
| `FallbackCoach` | `subsystems/s3_coach/s3_ai_coach.py` | Rule-based local engine for offline or API-error scenarios. |
| `S3CoachError` | `subsystems/s3_coach/s3_errors.py` | Custom exception hierarchy (`S3ConfigurationError`, `S3APIError`, `S3DatabaseError`). |
| `AIRecommendation` | `subsystems/s3_coach/s3_models.py` | SQLAlchemy ORM model for the `ai_recommendations` caching table. |

## How to run

Tested with Python 3.12.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
export USE_MOCK=false                       # read from S1 and S3 instead of the demo data
export S1_DB_PATH=instance/s1_energy.db     # S1 database, created and filled on first start
flask --app wsgi run
```

Open http://127.0.0.1:5000. S3 keeps its answers in `smart_energy.db` unless `DATABASE_URL` points to another database, for example a MySQL server (`mysql+pymysql://user:password@localhost:3306/smart_energy`). To let the AI coach use a live model, also export `NVIDIA_API_KEY` or `OPENAI_API_KEY` before starting; without a key it answers with its fallback.

## Tests

```bash
pytest
```

This runs the tests of all three subsystems, including `tests/s2/test_adapters.py`, which checks that every page works with the real S1 and S3.

## Presentation Link

Team video (3 to 5 minutes): [Homework Assignment 3 presentation](https://drive.google.com/file/d/1I49TwlNNM-RX25xeFP6YbW1sH9z8aezh/view?usp=sharing)

---

Full documentation: S1 in [`docs/s1/README.md`](docs/s1/README.md), S2 in [`docs/s2/README.md`](docs/s2/README.md).
