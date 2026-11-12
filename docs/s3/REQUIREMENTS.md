# Subsystem 3 Requirements (AI Coach, Data Persistence & Deployment)

This document contains the complete list of Functional (FR) and Non-Functional (NFR) requirements for Subsystem 3, adjusted to reflect the final implementation of the MVP.

## Functional Requirements

| ID | Requirement | Details (implementation, acceptance) | Why |
| :--- | :--- | :--- | :--- |
| **S3-FR1** | The AI module shall send the current building energy context to the OpenAI API. | `building_context()` collects score, E/C/K, top-consuming category, active alerts and week-over-week change from S1 into a compact prompt with a system message per tone. • Prompt contains no raw log rows, only aggregates. | Core AI feature. |
| **S3-FR2** | The system shall parse the AI response into a structured recommendation. | Model is asked for a JSON object with a single key `"tip"`; returned through OpenAI API and checked for the required key; malformed output triggers the fallback. • UI receives 1 actionable recommendation. | Usable advice, not raw text. |
| **S3-FR3** | The AI Coach shall answer user questions on carbon-reduction strategies. | `AICoach.ask()` sends the question plus building context; answers limited to energy and sustainability topics by the system prompt. • Off-topic questions are politely redirected. | Interactive assistance. |
| **S3-FR4** | The system shall return rule-based fallback recommendations when the API is unreachable. | `FallbackCoach` applies deterministic rules and output formatting; response flagged `source='fallback'`. • With the network disabled or API keys missing, the coach still answers. | App never fails completely. |
| **S3-FR5** | The system shall cache recommendations by context hash. | SHA-256 of the rounded context + tone; a hit returns the stored row with `source='cache'`. • Two identical requests make only one API call. | Controls API cost. |
| **S3-FR6** | The system shall store all application data in MySQL. | SQLAlchemy models for the 7 tables in the schema; `MySQLRepository` implements the repository interface. • Data survives a container restart. | Persistent storage. |
| **S3-FR7** | The database shall enforce integrity with foreign keys, NOT NULL and CHECK constraints. | Constraints defined in the schema and mirrored in the models. • Inserting kWh < 0 or an unknown building is rejected. | Rejects invalid data at the source. |
| **S3-FR8** | The data layer shall return recent historical records filtered by building. | `get_energy_logs(building_id, limit)` and `get_alerts()` use parameterized queries, ordered newest first, with a default limit of 20 rows. | Feeds history and dashboard. |
| **S3-FR9** | The system shall provide a method to seed initial sample data. | `seed_sample_data()` method populates empty tables with baseline logs, alerts, and recommendations. • Restores the system to a verifiable demo state. | Recovery, analysis and demo resets. |
| **S3-FR10** | `docker-compose.yml` shall run the web and MySQL containers with persistent volumes and health checks. | Services `web` and `db`; `mysql_data` and `s1_data` volumes; db health check with `mysqladmin ping`; web waits for a healthy db; `restart: unless-stopped`. | Multi-container deployment. |

## Non-Functional Requirements

| ID | Requirement | Details (implementation, acceptance) | Why |
| :--- | :--- | :--- | :--- |
| **S3-NFR1** | An AI recommendation must return within 4 seconds under normal network conditions. | Small model, compact prompt, response logged with latency. • Demo requests finish quickly. | Acceptable wait time. |
| **S3-NFR2** | Secrets must come from environment variables or a `.env` file that is never committed. | `OPENAI_API_KEY`, `NVIDIA_API_KEY`, `SECRET_KEY` loaded dynamically; `.env` in `.gitignore`. • Repository search finds no hardcoded keys. | Security. |
| **S3-NFR3** | API calls must time out gracefully and cap output tokens. | OpenAI client configured with `timeout=10` and `max_tokens=500`; NVIDIA client uses `timeout=8` and `max_tokens=300`. • Simulated timeout triggers fallback. | No hanging threads, controlled cost. |
| **S3-NFR4** | The LLM provider must sit behind a polymorphic interface. | Abstract `LLMClient` with `generate_recommendation()`; `OpenAIClient`, `NVIDIAClient`, and `FallbackCoach` implement it. • Swapping providers changes one object only. | Low coupling. |
| **S3-NFR5** | AI tests must mock the external APIs; no real API credits used. | `test_s3_core.py` uses `unittest.mock.patch` and `MagicMock` to return fixed responses, timeouts and errors. • Tests pass with `USE_MOCK="true"` and no API key. | Mandatory testing at zero cost. |
| **S3-NFR6** | Data-layer tests must run against in-memory SQLite. | `test_s3_core.py` creates the models on `sqlite:///:memory:` per test using `setUp` and `tearDown`. • Fast execution without a DB server. | Fast tests, independent execution. |
| **S3-NFR7** | Typical history queries must return fast enough to maintain dashboard responsiveness. | Queries use SQLAlchemy's `order_by` and `limit` to quickly fetch the latest records without scanning the entire table. | Fast dashboard. |
| **S3-NFR8** | Concurrent writes must not corrupt data. | Writes (alerts, recommendations, telemetry) use transactions via SQLAlchemy sessions with `session.rollback()` on error. | Data integrity. |
| **S3-NFR9** | The full stack must start with one command, documented in the README. | `docker compose up --build -d`. README gives clone, `.env` setup, and run steps. • A clean machine reaches the dashboard by following the README alone. | Portability for evaluators. |
| **S3-NFR10** | Containers must be small and efficient. | `python:3.12-slim` single-stage build, leveraging Docker layer caching by installing `requirements.txt` before copying source code. • Gunicorn runs with 2 workers. | Efficiency and fast builds. |