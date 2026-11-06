# AI-Powered Smart Energy Management System (FH Dortmund - Group 7)

![Python 3.11](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.x-000000?style=for-the-badge&logo=flask&logoColor=white)
![MySQL](https://img.shields.io/badge/MySQL-8.0-4479A1?style=for-the-badge&logo=mysql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![Pytest](https://img.shields.io/badge/Pytest-100%25_Passing-0A9EDC?style=for-the-badge&logo=pytest&logoColor=white)

> **Master's Capstone Project — Topic 1: Smart Energy Coach**  
> **Institution:** Fachhochschule Dortmund (University of Applied Sciences and Arts)  
> **Team:** Group 7 (Python Capstone Project)

---

## 1. Project Overview & Objectives

The **AI-Powered Smart Energy Management System** is an end-to-end campus sustainability platform designed for **Topic 1** of the FH Dortmund Master's Capstone Project. With a primary operational focus on the **FH Dortmund Smart Library** and multi-building support for `library`, `lecture-hall-a`, and `lab-building`, the system monitors device-level energy consumption, evaluates environmental and financial KPIs, detects threshold anomalies, simulates what-if conservation scenarios, and delivers actionable, AI-generated energy coaching.

### Core Objectives
* **Carbon Footprint Reduction:** Continuously track electricity consumption across four primary campus device categories (**Heating**, **Lighting**, **Servers**, and **Other**) and quantify real-time CO₂ emissions.
* **Occupant Comfort Preservation:** Balance energy reductions against indoor thermal comfort by evaluating room temperatures relative to an ideal **21.0 °C** campus setpoint.
* **Cost Efficiency & Savings Transparency:** Calculate real-time operational costs in Euros (€), compare daily usage against historical baselines (**18.0 kWh/day**), and project financial savings via interactive "What-If" scenario modeling.
* **Resilient AI Coaching:** Provide tailored, context-aware sustainability recommendations powered by the OpenAI API (`gpt-4o-mini`), backed by a deterministic offline fallback coach and persistent SQLite/MySQL storage.

---

## 2. Team Members & Subsystem Ownership

The system is architected into three decoupled subsystems with strict facade and repository boundaries, each owned by a dedicated team member:

| Team Member | Subsystem | Directory / Module | Core Responsibilities & Ownership |
| :--- | :--- | :--- | :--- |
| **Abdelhamid Ahbane** | **Subsystem 1 (S1):** Monitoring, Simulation & Analytics Engine | [`subsystems/s1_analytics.py`](subsystems/s1_analytics.py) | Deterministic energy simulation, mathematical KPI & Sustainability Score engine, 14-day hourly history seeding (`1,344` rows/building), `AlertMonitor`, multi-window aggregations, Week-over-Week comparison, and What-If scenario projections. |
| **Abdelaziz Jail** | **Subsystem 2 (S2):** Web Interface & Visualization | [`subsystems/s2_web/`](subsystems/s2_web/) | Flask web application, `PageView` & `CoachView` controllers, `ChartPresenter` (Chart.js 4.4.6 visualizations), interactive `ScenarioForm` & `ThresholdForm` (Flask-WTF), CSRF security, and RESTful JSON API endpoints. |
| **Nestor David Carrizo** | **Subsystem 3 (S3):** AI Coach, Data Persistence & Deployment | [`subsystems/s3_ai_data/`](subsystems/s3_ai_data/) | FH Dortmund OpenAI API Coach integration, deterministic Fallback & Cached Coach engine, `S3MySQLRepository` & SQLite data persistence layer, database schema migrations, and multi-container Docker Compose deployment. |

---

## 3. Repository Structure

```text
.
├── config.py                                  # Shared system constants, DB credentials, and OpenAI config
├── README.md                                  # Project & Subsystem 1 documentation
├── requirements.txt                           # Verified Python dependencies
├── docs/                                      # Subsystem 1 UML class diagrams & staged handoff docs
│   ├── Class_diagram_s1/
│   │   ├── class-diagram-s1-svg.svg           # Subsystem 1 UML Class Diagram (SVG)
│   │   └── class-diagram-s1.png               # Subsystem 1 UML Class Diagram (PNG)
│   └── handoffs_s1/
│       ├── STAGE_1_HANDOFF.md                 # Stage 1: EnergyReading data contract & validation
│       ├── STAGE_2_HANDOFF.md                 # Stage 2: ScoreCalculator mathematical engine
│       ├── STAGE_3_HANDOFF.md                 # Stage 3: EnergySimulator & 14-day seeding
│       ├── STAGE_4_HANDOFF.md                 # Stage 4: AnalyticsService facade & AlertMonitor
│       └── STAGE_5_FINAL_MASTER_HANDOFF.md    # Stage 5: Final Subsystem 1 master handoff & scripts
├── subsystems/
│   └── s1_analytics.py                        # Subsystem 1: Simulation, ScoreCalculator, AlertMonitor, AnalyticsService
└── tests/
    └── test_s1_analytics.py                   # Subsystem 1 unit, performance, and determinism test suite (14 tests)
```

---

## 4. Deep Dive: Subsystem 1 (Simulation & Analytics Engine)

**Owner:** Abdelhamid Ahbane  
**Implementation:** [`subsystems/s1_analytics.py`](subsystems/s1_analytics.py) | **Test Suite:** [`tests/test_s1_analytics.py`](tests/test_s1_analytics.py)

Subsystem 1 serves as the analytical core of the application. It transforms raw or simulated device telemetry into validated readings, environmental metrics, composite sustainability scores, threshold alerts, time-series aggregations, and scenario projections without exposing internal SQL or mathematical formulas to downstream consumers.

### 4.1 The 5 Collaborating UML Classes

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

1. **`EnergyReading` (`@dataclass`):**
  * Validated data contract representing a single timestamped measurement across seven attributes: `timestamp` (`datetime`), `device_type`, `kwh`, `room_temp`, `co2_kg`, `sustainability_score` (aliased via `@property def score`), and `building_id` (defaulting to `"library"`).
   * Enforces strict pre-persistence data integrity via `validate()`:
     * Rejects negative energy consumption (`kWh < 0`).
     * Enforces realistic indoor temperature bounds (`0.0 °C <= room_temp <= 45.0 °C`).
     * Restricts `device_type` to configured campus categories (`Heating`, `Lighting`, `Servers`, `Other`).
     * Ensures `building_id` is a valid, non-empty string.
2. **`ScoreCalculator`:**
   * Pure, stateless mathematical engine with zero database or web dependencies (`S1-NFR1`, `S1-NFR2`). Computes CO₂, EUR cost, thermal comfort, and the weighted sustainability score using parameters from `config.py`.
3. **`EnergySimulator`:**
  * Generates realistic synthetic campus device telemetry governed by time-of-day occupancy multipliers, device base loads, and an isolated pseudo-random number generator (`random.Random(42)`). Returned timestamps are `datetime` objects.
4. **`AlertMonitor`:**
   * Autonomous per-building threshold manager. Loads custom alert limits from persistent storage (`alert_thresholds` table), merges them safely with `config.DEFAULT_LIMITS`, and flags anomalous device readings.
5. **`AnalyticsService` (Facade):**
  * Unified service facade consumed by Subsystem 2 (Web UI) and Subsystem 3 (AI Coach). Coordinates seeding, live simulation steps, dashboard summaries, `get_score()`, `get_aggregates(period, category)`, `get_alerts()`, week-over-week comparisons, and `estimate_scenario(changes)` over an injected S3 MySQL repository (or the built-in `SQLiteRepository` offline adapter).

---

### 4.2 Mathematical Engine & Formulas (`ScoreCalculator`)

All conversion factors are centrally managed in [`config.py`](config.py):
* **Carbon Emission Factor:** `0.38 kg CO₂ / kWh`
* **Electricity Tariff:** `0.35 € / kWh`
* **Ideal Indoor Temperature:** `21.0 °C`
* **Daily Baseline Consumption:** `18.0 kWh/day`

#### 1. CO₂ Emissions (`calc_co2`)
```text
CO₂ (kg) = round(kWh × 0.38, 2)
```

#### 2. Operational Energy Cost (`calc_cost`)
```text
Cost (€) = round(kWh × 0.35, 2)
```

#### 3. Thermal Comfort Index (`calc_comfort`)
Measures occupant comfort on a normalized `0.0` to `1.0` scale. Comfort peaks at `1.0` when `room_temp = 21.0 °C` and decreases linearly by `0.1` per degree of deviation, reaching `0.0` at `±10.0 °C` from the ideal setpoint:
```text
K = round(max(0.0, min(1.0, 1.0 - (|room_temp - 21.0| / 10.0))), 2)
```

#### 4. Weighted Sustainability Score (`calc_sustainability_score`)
Combines three normalized sub-scores—**Energy Efficiency (`E`)**, **Carbon Efficiency (`C`)**, and **Thermal Comfort (`K`)**—into an integer score from `0` to `100`:
```text
E     = round(max(0.0, min(1.0, 1.0 - (hourly_kwh / 4.0))), 2)
C     = round(max(0.0, min(1.0, 1.0 - ((hourly_kwh × 0.38) / 1.6))), 2)
Score = round(100 × (0.40 × E + 0.35 × C + 0.25 × K))   [Range: 0 to 100]
```

---

### 4.3 Deterministic Simulation & 14-Day Hourly Seeding (`S1-FR1`, `S1-FR2`, `S1-NFR2`, `S1-NFR4`)

To guarantee reproducible unit tests, consistent UI demonstrations, and deterministic grading across environments, `EnergySimulator` isolates its random state using `random.Random(42)`:

* **Device Base Loads:**
  * **Heating:** `1.4 kWh`
  * **Servers:** `1.1 kWh`
  * **Lighting:** `0.5 kWh`
  * **Other:** `0.3 kWh`
* **Campus Occupancy Schedule:**
  * **Daytime Peak (08:00 – 18:00):** `1.4×` multiplier
  * **Off-Peak / Night (19:00 – 07:00):** `0.6×` multiplier
* **Realistic Variation Bounds:**
  * Energy noise multiplier: uniform random factor between `0.85` and `1.25`
  * Room temperature variation: `21.0 °C` with uniform random offset between `-1.5 °C` and `+2.0 °C`
* **14-Day Batch Seeding (`seed_history` & `seed_if_empty`):**
  * Generates `14 days × 24 hours = 336` hourly timestamps across all `4` device categories, producing **`1,344` validated readings per building**.
  * Persisted in a single batch transaction (`executemany`) executing well under the 10-second NFR ceiling (typically `< 0.05 seconds`).

---

### 4.4 Time-Series Aggregations, Week-over-Week Engine & Scenario Projections (`S1-FR7`, `S1-FR9`)

* **Multi-Window Aggregations (`get_aggregates`):**
  * **`hourly_series`:** 24-hour chronological breakdown of total kWh and per-device kWh for the current day.
  * **`last_week_hourly_series`:** Corresponding 24-hour series from 7 days prior for direct overlay charting.
  * **`daily_totals` & `weekly_totals`:** Aggregated kWh, CO₂ (kg), and Cost (€) for the 24-hour and 168-hour windows, including `vs_last_week_pct`.
  * **`by_device_week`:** 7-day cumulative kWh split across `Heating`, `Lighting`, `Servers`, and `Other`.
  * Supports `period="day"`, `"week"`, and `"month"`, optional device `category`, and returns hourly series timestamps as Python `datetime` objects.
* **Week-over-Week Comparison Engine (`compute_week_over_week`):**
  * Compares the trailing 7-day window (`latest - 167h` to `latest`) against the preceding 7-day window (`latest - 335h` to `latest - 167h`), returning exact percentage changes (`change_pct`) for `energy_kwh`, `co2_kg`, and `cost_eur`.
* **What-If Scenario Projections (`simulate_scenario`):**
  * Pure, non-destructive calculation modeling hardware and setpoint adjustments without modifying database records:
    * **Heating Setpoint Adjustment (`heating_delta_c`):** Each `1.0 °C` reduction lowers Heating consumption by **6%** (`Heating_kWh × heating_delta_c × 0.06`).
    * **Lighting Reduction (`light_reduction_pct`):** Scales Lighting consumption directly by the selected percentage (`0%` to `50%`).
    * Returns `before_kwh`, `after_kwh`, `before_co2`, `after_co2`, `before_cost`, `after_cost`, `before_score`, and `after_score`.

### 4.5 Subsystem 1 Requirements Traceability Matrix

| ID | Requirement Summary | Implemented By | Automated Proof (`tests/test_s1_analytics.py`) |
| :--- | :--- | :--- | :--- |
| **FR1** | Generate realistic device energy readings | `EnergySimulator.generate_reading()`, `simulate_live_step()` | `test_single_calculation_performance_under_50ms`, `test_live_step_and_alert_fallback_safety` |
| **FR2** | Seed 14-day hourly historical dataset (1,344 rows) | `EnergySimulator.seed_history()`, `seed_if_empty()` | `test_seed_and_summary_with_temp_db`, `test_fixed_seed_determinism` |
| **FR3** | Calculate CO₂ emissions and EUR cost | `ScoreCalculator.calc_co2()`, `calc_cost()` | `test_co2_and_cost_calculation` |
| **FR4** | Calculate indoor thermal comfort index | `ScoreCalculator.calc_comfort()` | `test_comfort_score_at_ideal_temp` |
| **FR5** | Calculate weighted sustainability score (0–100) | `ScoreCalculator.calc_sustainability_score()` | `test_comfort_score_at_ideal_temp` |
| **FR6** | Produce unified dashboard KPIs & view model | `AnalyticsService.get_dashboard_summary()`, `get_score()` | `test_seed_and_summary_with_temp_db`, `test_score_alerts_and_scenario_api` |
| **FR7** | Detect threshold alerts & compute aggregations/WoW | `AlertMonitor.check_alerts()`, `get_alerts()`, `get_aggregates()`, `compute_week_over_week()` | `test_week_over_week_and_time_aggregations`, `test_alert_monitor_loads_building_limits`, `test_score_alerts_and_scenario_api` |
| **FR8** | Calculate financial & carbon savings vs. baseline | `AnalyticsService.get_dashboard_summary()` | `test_seed_and_summary_with_temp_db` |
| **FR9** | Project non-destructive What-If scenarios | `AnalyticsService.simulate_scenario()`, `estimate_scenario()` | `test_scenario_reduces_energy_when_heating_lowered`, `test_uml_method_signature_compatibility`, `test_score_alerts_and_scenario_api` |
| **FR10** | Validate and persist readings per building | `EnergyReading.validate()`, `save_reading()` | `test_reading_validation_rejects_negative_kwh`, `test_building_isolation` |
| **NFR1–10** | `< 50 ms` calc, determinism (`seed=42`), modular facade, type safety, safe fallbacks | `s1_analytics.py` & `config.py` | Full 14-test suite in `tests/test_s1_analytics.py`, including `test_returned_timestamps_are_datetime_objects` |

---

## 5. Cross-Subsystem Links & Integration Architecture

```text
+-----------------------------------------------------------------------------------+
|                   SUBSYSTEM 2: Web Interface & Visualization                      |
|               (Owner: Abdelaziz Jail — subsystems/s2_web/)                        |
|                                                                                   |
|  [Jinja2 Templates + Chart.js]  <--->  [PageView / CoachView / ChartPresenter]    |
|  [ScenarioForm / ThresholdForm] <--->  [HTML Routes (/) & REST API (/api/*)]      |
+-----------------------------------------+-----------------------------------------+
                                          |
                 Calls Facade API         |         Requests AI Coaching &
          (get_dashboard_summary,         |         Persists Thresholds
           simulate_scenario, etc.)       v
+-----------------------------------------+-----------------------------------------+
|              SUBSYSTEM 1: Simulation & Analytics Engine                           |
|              (Owner: Abdelhamid Ahbane — subsystems/s1_analytics.py)              |
|                                                                                   |
|  [AnalyticsService Facade] ---> [EnergySimulator] ---> [ScoreCalculator]          |
|             |              ---> [AlertMonitor]    ---> [EnergyReading]            |
+-------------+---------------------------------------------------------------------+
              |
              |  Delegates Persistence via Repository Protocol
              v
+-----------------------------------------------------------------------------------+
|            SUBSYSTEM 3: AI Coach, Data Persistence & Deployment                   |
|            (Owner: Nestor David Carrizo — subsystems/s3_ai_data/)                 |
|                                                                                   |
|  [S3MySQLRepository / SQLiteRepository]  <--->  [(MySQL 8.0 / SQLite DB)]         |
|  [AICoachService (OpenAI + Fallback)]    <--->  [FH Dortmund OpenAI Endpoint]     |
+-----------------------------------------------------------------------------------+
```

### 5.1 Integration with Subsystem 2: Web UI & Visualization ([`subsystems/s2_web/`](subsystems/s2_web/))
**Owner:** Abdelaziz Jail

Subsystem 2 is structured around five core classes (`PageView`, `ChartPresenter`, `ScenarioForm`, `ThresholdForm`, and `CoachView`) and interacts with Subsystem 1 exclusively through the `AnalyticsService` facade:

* **Application Startup & Seeding:**
  ```python
  from subsystems.s1_analytics import AnalyticsService

  analytics_service = AnalyticsService(db_or_repo)
  analytics_service.seed_if_empty(days=14, building_id="library")
  ```
* **HTML Page Routes (`subsystems/s2_web/views/pages.py`):**
  * `/` (**Dashboard**): Renders real-time KPIs (`energy_today`, `co2_today`, `cost_today`, `savings_eur`, `savings_co2`), the Sustainability Score card (`score`, `E`, `C`, `K`), 24h vs. Last Week line charts, and active AI Coach tips.
  * `/history` (**History & Alerts**): Displays 7-day/30-day device share bar charts, daily energy totals, and threshold breach logs from `AlertMonitor`.
  * `/scenarios` (**What-If Scenarios**): Validates user slider inputs via `ScenarioForm` (Heating change from `-3 °C` to `+3 °C`, Lighting reduction from `0%` to `50%`) and invokes `analytics_service.simulate_scenario(...)`.
  * `/coach` (**AI Coach**): Interactive chat interface supporting tone selection (`encouraging`, `analytical`, `strict`).
  * `/settings` (**Alert Thresholds**): Validates per-device kWh limits (`0.1` to `20.0 kWh/h`) via `ThresholdForm` and persists them per building.
* **RESTful JSON API Endpoints (`subsystems/s2_web/views/api.py`):**
  * `GET /api/kpis?building=library&category=heating`
  * `GET /api/score?building=library`
  * `GET /api/hourly?building=library&day=2024-05-14&compare=1`
  * `GET /api/aggregates?building=library&period=week`
  * `GET /api/alerts?building=library`
  * `POST /api/coach/ask` (CSRF-protected JSON endpoint)
  * `GET /api/coach/status`

### 5.2 Integration with Subsystem 3: AI Coach & Data Layer ([`subsystems/s3_ai_data/`](subsystems/s3_ai_data/))
**Owner:** Nestor David Carrizo

Subsystem 3 provides two critical pillars for the integrated platform:

1. **Relational Persistence (`S3MySQLRepository` & `SQLiteRepository`):**
   Implements the repository protocol injected into `AnalyticsService(db_or_repo)` to manage two core tables:
   ```sql
   CREATE TABLE IF NOT EXISTS energy_readings (
       id INTEGER PRIMARY KEY AUTO_INCREMENT,
       timestamp DATETIME NOT NULL,
       building_id VARCHAR(50) NOT NULL,
       device_type ENUM('Heating','Lighting','Servers','Other') NOT NULL,
       kwh DECIMAL(6,2) NOT NULL,
       room_temp DECIMAL(4,1) NOT NULL,
       co2_kg DECIMAL(6,2) NOT NULL,
       sustainability_score INT NOT NULL
   );

   CREATE TABLE IF NOT EXISTS alert_thresholds (
       building_id VARCHAR(50) NOT NULL,
       device_type VARCHAR(50) NOT NULL,
       limit_kwh DECIMAL(6,2) NOT NULL,
       PRIMARY KEY (building_id, device_type)
   );
   ```
2. **Context-Aware AI Coach (`AICoachService`):**
   Consumes the stable dictionary output of `AnalyticsService.get_dashboard_summary(building_id)`—specifically `energy_today`, `co2_today`, `score`, `by_device`, `alerts`, and `week_over_week`—to construct a grounded system prompt for the OpenAI API (`gpt-4o-mini`). If the API key is omitted or network connectivity fails, S3 seamlessly degrades to a deterministic **Fallback Coach** so the UI never hangs or crashes.

---

## 6. Getting Started & Local Development

### Prerequisites
* **Python:** `3.11+` (tested with Python 3.11 and 3.12)
* **Database:** Built-in SQLite (zero-config default) or MySQL 8.0+

### 1. Clone the Repository
```bash
git clone https://github.com/fh-dortmund-group7/smart-energy-coach.git
cd smart-energy-coach
```

### 2. Create a Virtual Environment & Install Dependencies
**Linux / macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3. Configure Environment Variables (`.env`)
Create a `.env` file in the project root:
```ini
# Flask Security & Mode
SECRET_KEY=replace-with-a-64-char-hex-secret-key
FLASK_DEBUG=0
USE_MOCK=false

# Local SQLite Fallback Path
DB_PATH=data/energy.db

# MySQL Database Configuration (Subsystem 3)
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=energy_user
MYSQL_PASSWORD=energy_pass
MYSQL_DATABASE=smart_energy

# FH Dortmund / OpenAI API Configuration (Subsystem 3)
OPENAI_API_KEY=sk-your-openai-api-key
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini
```
*(Tip: Generate a secure `SECRET_KEY` with `python -c "import secrets; print(secrets.token_hex(32))"`)*

### 4. Run the Application Locally
**Development Server:**
```bash
flask run
```
**Production-Style Server (Gunicorn):**
```bash
gunicorn -w 2 -b 127.0.0.1:8000 wsgi:app
```
Open `http://127.0.0.1:5000` (Flask) or `http://127.0.0.1:8000` (Gunicorn) in your browser.

### 5. Run the Automated Test Suite
Execute the full Pytest suite (covering S1 analytics, S2 web routes/forms, and S3 persistence/AI fallback):
```bash
python -m pytest -v
```
To run only Subsystem 1's unit and performance tests:
```bash
python -m pytest tests/test_s1_analytics.py -v
```
To verify syntax compilation across core modules:
```bash
python -m py_compile config.py subsystems/s1_analytics.py tests/test_s1_analytics.py
```

---

## 7. Docker Deployment

Subsystem 3 provides full containerization orchestrating the **Flask/Gunicorn Web Application** alongside a persistent **MySQL 8.0 Database** with automatic healthchecks and volume mounting.

Build and launch the entire stack with a single command:

```bash
docker compose up --build
```

* **Web Application UI & API:** Accessible at `http://localhost:8000` (or `http://localhost:5000` depending on port mapping).
* **MySQL 8.0 Service:** Exposed internally on port `3306` with automatic schema initialization and 14-day historical seeding on first boot.
* To stop the stack and preserve database volumes:
  ```bash
  docker compose down
  ```

---

## 8. Screencast & Presentation Links

* **7-Minute Individual & Project Screencast Video:**  
  [🎥 Watch Screencast Video *(Link to be added after recording)*](#)
* **Team Capstone Presentation Video (3–5 Minutes):**  
  [🎬 Watch Team Overview Video *(Link to be added after recording)*](#)
* **Final Defense Presentation Slides (PDF / PPTX):**  
  [📊 View Presentation Slides *(Link to be added)*](#)

---

*Developed for the Master's Python Capstone Project at **Fachhochschule Dortmund** by **Group 7** (Abdelhamid Ahbane, Abdelaziz Jail, and Nestor David Carrizo).*
