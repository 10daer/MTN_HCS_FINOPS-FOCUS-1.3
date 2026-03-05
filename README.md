# MTN HCS FINOPS-FOCUS (1.3) — Data Mapper API

A professional data transformation service that fetches data from a source API and maps it into the **FOCUS (FinOps Open Cost & Usage Specification)** format.

## Architecture

```
Request → POST /api/v1/transform → Fetch from API-A → Map to FOCUS → Response
```

| Layer        | Responsibility                                       |
| ------------ | ---------------------------------------------------- |
| `api/routes` | HTTP endpoints — receive requests, return responses  |
| `services`   | Business logic — orchestrate fetching & transforming |
| `mappers`    | Pure transformation — Source format → FOCUS format   |
| `schemas`    | Pydantic models — validate input/output data shapes  |
| `core`       | Cross-cutting — logging, exceptions, error handlers  |

## Quick Start

### 1. Clone & Install

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env with your actual values
```

### 3. Run

```bash
uvicorn app.main:app --reload
```

### 4. Test

```bash
pytest -v --cov=app
```

## API Endpoints

| Method | Endpoint            | Description                        |
| ------ | ------------------- | ---------------------------------- |
| POST   | `/api/v1/transform` | Fetch from source & transform data |
| GET    | `/health`           | Health check                       |

## Docker

```bash
docker build -t mtn-finops-focus .
docker run -p 8000:8000 --env-file .env mtn-finops-focus
```

## License

Proprietary — MTN / Qucoon
