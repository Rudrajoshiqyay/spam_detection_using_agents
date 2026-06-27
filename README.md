# FraudGuard AI

Bank-grade fraud detection system powered by LangGraph multi-agent orchestration, Groq LLMs, Neon PostgreSQL, and Upstash Redis.

## Architecture

```
Transaction → Feature Store → Fast Screening → Fraud Pattern Matching
→ Sequence Intelligence → Kill Chain → Cohort Analysis → Graph Intelligence
→ 5 Parallel AI Agents → Consensus → Investigation → Counterfactual
→ Explainability → Analyst Recommendation → Storytelling → Final Decision
```

17-node LangGraph pipeline with 10 LLM agents running on Groq (llama-3.1-8b-instant / llama-3.3-70b-versatile).

## Quick Start (Local Dev)

```bash
pip install -r requirements.txt
cp .env.example .env       # edit with your keys
python -m uvicorn app.main:app --reload
```

For local dev, set `MOCK_LLM=true` and `USE_FAKE_REDIS=true` — no API keys required.

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `GROQ_API_KEY` | Yes (unless MOCK_LLM=true) | — | Groq API key (starts with `gsk_`) |
| `FAST_MODEL` | No | `llama-3.1-8b-instant` | Model for 5 parallel analysis agents |
| `DEEP_MODEL` | No | `llama-3.3-70b-versatile` | Model for investigation/storytelling |
| `MOCK_LLM` | No | `false` | `true` = skip Groq, use deterministic fallbacks |
| `REDIS_URL` | Yes (unless USE_FAKE_REDIS=true) | `redis://localhost:6379` | Redis connection URL |
| `UPSTASH_REDIS_REST_URL` | No | — | Upstash REST API URL (optional) |
| `UPSTASH_REDIS_REST_TOKEN` | No | — | Upstash REST token (optional) |
| `USE_FAKE_REDIS` | No | `false` | `true` = in-memory fakeredis (dev/tests) |
| `DATABASE_URL` | No | `sqlite+aiosqlite:///./fraud_feedback.db` | SQLAlchemy async DB URL |
| `API_KEY` | No | — | If set, all non-monitoring endpoints require `X-API-Key` header |
| `CORS_ALLOWED_ORIGINS` | No | — | Comma-separated extra CORS origins (e.g. your Vercel URL) |
| `FAST_SCREENING_THRESHOLD` | No | `35` | Risk score below which transactions auto-approve |
| `HIGH_RISK_THRESHOLD` | No | `70` | Risk score above which transactions auto-block |
| `LOG_LEVEL` | No | `INFO` | `DEBUG`, `INFO`, `WARNING`, or `ERROR` |
| `APP_ENV` | No | `development` | Set to `production` for prod deployments |

## Production Deployment

### Startup Validation

On startup, the system validates configuration and fails loudly if:
- `MOCK_LLM=false` but `GROQ_API_KEY` is missing or invalid
- `USE_FAKE_REDIS=false` but `REDIS_URL` points to localhost
- `DATABASE_URL` is empty

This prevents silent misconfigurations in production.

### Render Deployment

1. Create a new **Web Service** on [Render](https://render.com)
2. Connect your GitHub repository
3. Set **Build Command**: `pip install -r requirements.txt`
4. Set **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Set **Health Check Path**: `/ready`
6. Add all environment variables from `.env.example`
7. Set `RENDER_DEPLOY_HOOK` in GitHub secrets for automated deployments

### Vercel Deployment (Frontend)

If you have a Vercel frontend, add its URL to `CORS_ALLOWED_ORIGINS`:

```
CORS_ALLOWED_ORIGINS=https://your-app.vercel.app
```

### Neon PostgreSQL Setup

1. Create a project at [neon.tech](https://neon.tech)
2. Copy the connection string from the dashboard
3. Set `DATABASE_URL=postgresql+asyncpg://user:pass@host/db`

The system uses SSL automatically for PostgreSQL connections.

### Upstash Redis Setup

1. Create a database at [upstash.com](https://upstash.com)
2. Copy the **Redis URL** (starts with `rediss://`)
3. Set `REDIS_URL=rediss://default:<token>@<host>.upstash.io:6379`
4. Set `USE_FAKE_REDIS=false`

### Groq API Setup

1. Sign up at [console.groq.com](https://console.groq.com)
2. Create an API key
3. Set `GROQ_API_KEY=gsk_...`
4. Set `MOCK_LLM=false`

## Authentication

When `API_KEY` is set, all endpoints (except `/health`, `/live`, `/ready`, `/metrics`) require:

```
X-API-Key: <your-api-key>
```

Returns `HTTP 403` for missing or invalid keys. Leave `API_KEY` empty to disable auth (development mode).

## Rate Limiting

Per-IP rate limits (in-process, resets on restart):

| Endpoint | Limit |
|---|---|
| `POST /detect` | 30/minute |
| `POST /seed` | 5/minute |
| `POST /simulate/full` | 5/minute |
| `POST /feedback/submit` | 30/minute |
| `POST /feedback/evolve` | 5/minute |
| All other endpoints | 200/minute (global default) |

## Health Endpoints

| Endpoint | Auth | Description |
|---|---|---|
| `GET /live` | None | Liveness probe — always 200 while process is alive |
| `GET /ready` | None | Readiness probe — 200 only after startup completes |
| `GET /health` | None | Detailed health: Redis, DB, version, provider |
| `GET /metrics` | None | Prometheus metrics |

Configure Render to use `/ready` as the health check path.

## CI/CD

GitHub Actions workflow at `.github/workflows/ci.yml`:

1. Runs on every push to `main` and `dev`, and all PRs to `main`
2. Installs dependencies
3. Runs all tests with `MOCK_LLM=true` and `USE_FAKE_REDIS=true` (no credentials needed)
4. On successful `main` branch push, triggers Render deploy via webhook

Set `RENDER_DEPLOY_HOOK` in GitHub repository secrets to enable automated deployment.

## Testing

```bash
# Run all tests (323 unit + integration + production hardening)
MOCK_LLM=true USE_FAKE_REDIS=true pytest tests/ -x -q

# Run only production hardening tests
MOCK_LLM=true USE_FAKE_REDIS=true pytest tests/test_production.py -v
```

Tests use:
- In-memory fakeredis (no Redis required)
- SQLite (no PostgreSQL required)
- Mock LLM (no Groq API key required)

## API Endpoints

### Core
- `POST /detect` — Run fraud detection pipeline
- `GET /health` — System health check
- `GET /live` — Liveness probe
- `GET /ready` — Readiness probe
- `GET /metrics` — Prometheus metrics

### Profiles
- `GET /profiles` — List demo user profiles
- `GET /profiles/{user_id}` — Get specific profile

### Demo
- `POST /seed` — Seed Redis with demo data
- `POST /demo/scenario/{name}` — Run preset scenario

### Simulation
- `POST /simulate/population` — Generate population
- `POST /simulate/campaign` — Generate fraud campaign
- `POST /simulate/ring` — Generate fraud ring
- `POST /simulate/full` — Full simulation

### Feedback
- `POST /feedback/submit` — Submit analyst feedback
- `GET /feedback/stats` — Detection metrics
- `GET /feedback/recent` — Recent feedback entries
- `POST /feedback/evolve` — Trigger pattern evolution

### Graph
- `GET /graph/summary/{user_id}` — Network analysis summary
