"""
FastAPI Application — Fraud Detection System
Endpoints:
  POST /detect                          — run full fraud detection pipeline
  GET  /health                          — health check
  GET  /profiles                        — list available demo user profiles
  GET  /profiles/{id}                   — get specific user profile
  POST /seed                            — seed Redis with demo data
  GET  /graph/summary/{user_id}         — get user's fraud graph summary
  POST /demo/scenario/{name}            — run a pre-built demo scenario

  Synthetic Data:
  POST /generate/users                  — generate synthetic users
  POST /generate/transactions           — generate synthetic transactions
  POST /generate/scenario               — build full fraud simulation

  Simulation (Upgrade):
  POST /simulate/population             — generate population profile
  POST /simulate/campaign               — generate a fraud campaign
  POST /simulate/ring                   — generate a fraud ring
  POST /simulate/full                   — full persona+campaign+ring+adversarial batch
  POST /simulate/adversarial            — apply adversarial mutations to transactions
  POST /simulate/evolve                 — generate fraud evolution arc (gen 1→4)
  GET  /simulate/evolution/summary      — session lineage of evolved campaigns
  POST /simulate/leakage-check          — detect label leakage in a dataset
  GET  /simulate/leakage-check/from-ground-truth — leakage check on stored records
  GET  /economic/events                 — macro economic event calendar
  GET  /economic/day-profile            — economic multipliers for a date
  GET  /metrics/evaluation              — accuracy/precision/recall/F1 from ground truth
  GET  /metrics/confusion-matrix        — confusion matrix vs detection results
  GET  /metrics/campaign-performance    — per-campaign accuracy metrics
  GET  /metrics/fraud-type-performance  — per fraud-type metrics + detection rate
  GET  /ground-truth/stats              — ground truth store statistics

  Feedback:
  POST /feedback/submit                 — submit analyst feedback
  GET  /feedback/stats                  — get detection metrics
  GET  /feedback/recent                 — recent feedback entries
  POST /feedback/evolve                 — trigger pattern evolution
  POST /feedback/update-reputation      — update device/merchant reputation
"""

import json
import logging
import sys
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional, List, Dict

import structlog
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from datetime import datetime, timezone
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings, validate_production_config
from app.models.transaction import Transaction
from app.models.user_profile import UserProfile, UserType
from app.models.fraud_decision import FraudDetectionResult
from app.services.feature_store import feature_store
from app.services.graph_intelligence import fraud_graph
from app.pipeline.fraud_pipeline import run_fraud_detection

# Synthetic data
from app.synthetic.user_generator import generate_user_batch
from app.synthetic.transaction_generator import generate_transaction_batch, transactions_to_jsonl
from app.synthetic.csv_loader import load_csv_transactions
from app.scenario.scenario_builder import build_scenario, PRESET_SCENARIOS

# Simulation upgrade
from app.simulation.persona_agent import PersonaType, create_persona_user, create_persona_batch
from app.simulation.fraud_campaign_agent import (
    generate_campaign, campaign_to_ground_truth_records, CAMPAIGN_GENERATORS,
)
from app.simulation.fraud_ring_agent import generate_ring, RING_TYPES
from app.simulation.adversarial_agent import apply_adversarial_mutations
from app.simulation.ground_truth_store import (
    init_ground_truth_db, bulk_store_ground_truth, get_stats as get_gt_stats,
    get_all_records as get_all_gt_records,
    get_campaign_records,
    GroundTruthRecord,
)
from app.simulation.evaluation_engine import evaluate, evaluate_batch
from app.simulation.dataset_validator import validate_dataset
from app.simulation.population_simulator import (
    generate_population, population_to_dict, POPULATION_WEIGHTS,
)
from app.simulation.life_events_engine import build_event_timeline, apply_event_modifier
from app.simulation.economic_environment import get_economic_environment
from app.simulation.fraud_evolution_agent import (
    generate_evolved_campaign, get_evolution_tracker,
)
from app.simulation.label_leakage_detector import (
    detect_leakage, leakage_report_to_dict,
)

# Feedback layer
from app.feedback.feedback_store import (
    init_db, close_db, submit_feedback, get_feedback_stats,
    get_recent_feedback, get_false_positives, OutcomeLabel,
)
from app.llm.grok_client import log_startup_info
from app.feedback.pattern_evolution import (
    adjust_pattern_weights_from_feedback, discover_emerging_patterns
)
from app.feedback.reputation_updater import update_reputation_from_feedback, update_user_risk_score


# ---------------------------------------------------------------------------
# Logging configuration (structlog over stdlib)
# ---------------------------------------------------------------------------

def _configure_logging() -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer()
            if settings.log_level.upper() == "DEBUG"
            else structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
    )


_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

_app_ready = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _app_ready
    _configure_logging()
    validate_production_config()
    log_startup_info()
    _logger.info(
        "Starting FraudGuard AI — env=%s redis=%s db=%s",
        settings.app_env,
        "upstash" if "upstash" in settings.redis_url else settings.redis_url.split("://")[0],
        "postgresql" if "postgresql" in settings.database_url else "sqlite",
    )
    await feature_store.connect()
    await init_db()
    await init_ground_truth_db()
    await _seed_demo_data()
    _app_ready = True
    _logger.info("FraudGuard AI startup complete — ready to serve requests")
    yield
    _app_ready = False
    await feature_store.close()
    await close_db()


app = FastAPI(
    title="Fraud Detection System",
    description="Bank-grade AI fraud detection with LangGraph agents",
    version="1.0.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS — merge localhost defaults with env-configured production origins
# ---------------------------------------------------------------------------
_BASE_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:8000",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:8000",
]
_extra_origins = [
    o.strip() for o in settings.cors_allowed_origins.split(",") if o.strip()
]
_ALLOWED_ORIGINS = _BASE_ORIGINS + _extra_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key", "X-Request-ID"],
)

# ---------------------------------------------------------------------------
# API Key authentication middleware
# ---------------------------------------------------------------------------
_AUTH_EXEMPT = frozenset({"/health", "/live", "/ready", "/metrics", "/docs", "/openapi.json"})


class APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if settings.api_key and request.url.path not in _AUTH_EXEMPT:
            provided = request.headers.get("x-api-key", "")
            if provided != settings.api_key:
                return JSONResponse(
                    {"detail": "Invalid or missing API key. Pass it as X-API-Key header."},
                    status_code=403,
                )
        return await call_next(request)


app.add_middleware(APIKeyMiddleware)

# ---------------------------------------------------------------------------
# Request ID middleware — generate/propagate X-Request-ID for log correlation
# ---------------------------------------------------------------------------


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


app.add_middleware(RequestIDMiddleware)

# ---------------------------------------------------------------------------
# Rate limiting (slowapi — per-IP, in-process)
# ---------------------------------------------------------------------------
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ---------------------------------------------------------------------------
# Prometheus metrics — exposed at /metrics
# ---------------------------------------------------------------------------
try:
    from prometheus_fastapi_instrumentator import Instrumentator
    Instrumentator().instrument(app).expose(app)
except ImportError:
    pass  # optional dependency; missing in CI if not installed


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class DetectRequest(BaseModel):
    transaction: Transaction
    user_id: str    # references a known profile; loads UserProfile from data


class DetectResponse(BaseModel):
    result: FraudDetectionResult
    pipeline_version: str = "1.0.0"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_profiles_cache: Optional[dict] = None


def _load_profiles() -> dict:
    global _profiles_cache
    if _profiles_cache is None:
        path = Path(__file__).parent / "data" / "user_profiles.json"
        with open(path) as f:
            _profiles_cache = json.load(f)
    return _profiles_cache


def _get_profile(user_id: str) -> UserProfile:
    profiles = _load_profiles()
    if user_id not in profiles:
        raise HTTPException(404, f"User profile '{user_id}' not found. Available: {list(profiles.keys())}")
    return UserProfile(**profiles[user_id])


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/live")
async def liveness():
    """Kubernetes/Render liveness probe — always returns 200 while process is alive."""
    return {"status": "alive"}


@app.get("/ready")
async def readiness():
    """Kubernetes/Render readiness probe — returns 200 only after startup completes."""
    if not _app_ready:
        raise HTTPException(status_code=503, detail="Application is still initializing")
    return {"status": "ready"}


@app.get("/health")
async def health():
    redis_ok = await feature_store.ping()

    db_ok = False
    try:
        from sqlalchemy import text
        from app.feedback.feedback_store import _get_engine
        async with _get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    overall = "ok" if (redis_ok and db_ok) else "degraded"
    return {
        "status": overall,
        "redis": "connected" if redis_ok else "disconnected",
        "database": "connected" if db_ok else "disconnected",
        "ready": _app_ready,
        "version": "1.0.0",
        "provider": "Groq" if not settings.mock_llm else "MockLLM",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/profiles")
async def list_profiles():
    profiles = _load_profiles()
    return {
        uid: {
            "user_type": p["user_type"],
            "risk_category": p["risk_category"],
            "avg_transaction_amount": p["spending_profile"]["avg_transaction_amount"],
        }
        for uid, p in profiles.items()
    }


@app.get("/profiles/{user_id}")
async def get_profile(user_id: str):
    return _get_profile(user_id)


@app.post("/detect", response_model=DetectResponse)
@limiter.limit("30/minute")
async def detect_fraud(request: Request, req: DetectRequest):
    profile = _get_profile(req.user_id)
    txn = req.transaction
    txn.user_id = req.user_id

    result = await run_fraud_detection(txn, profile)
    return DetectResponse(result=result)


@app.get("/graph/summary/{user_id}")
async def graph_summary(user_id: str):
    return fraud_graph.get_network_summary(user_id)


@app.post("/seed")
@limiter.limit("5/minute")
async def seed_data(request: Request):
    await _seed_demo_data()
    return {"status": "seeded", "message": "Demo data loaded into Redis"}


@app.post("/demo/scenario/{scenario_name}")
async def run_demo_scenario(scenario_name: str):
    """Run a pre-built demo scenario for hackathon presentations."""
    scenarios = _get_demo_scenarios()
    if scenario_name not in scenarios:
        raise HTTPException(404, f"Unknown scenario. Available: {list(scenarios.keys())}")

    scenario = scenarios[scenario_name]
    txn = Transaction(**scenario["transaction"])
    profile = _get_profile(scenario["user_id"])

    # Pre-seed velocity context for fraud scenarios that require prior activity
    now_ts = time.time()
    if scenario_name == "card_testing":
        # Simulate 9 recent micro-transactions (card testing pattern)
        for i in range(9):
            await feature_store.record_transaction(
                scenario["user_id"], f"seed_ct_{i}", 50.0 + i * 10, now_ts - (60 * (i + 1))
            )
    elif scenario_name == "velocity_fraud":
        # Simulate 14 rapid transactions in the past hour
        for i in range(14):
            await feature_store.record_transaction(
                scenario["user_id"], f"seed_vel_{i}", 200.0 + i * 50, now_ts - (200 * i)
            )

    t0 = time.perf_counter()
    result = await run_fraud_detection(txn, profile)
    wall_ms = (time.perf_counter() - t0) * 1000

    return {
        "scenario": scenario_name,
        "description": scenario["description"],
        "result": result,
        "wall_clock_ms": round(wall_ms, 2),
    }


# ---------------------------------------------------------------------------
# Demo seeding
# ---------------------------------------------------------------------------

async def _seed_demo_data():
    """Seed Redis with realistic behavioral features for all demo users."""
    profiles = _load_profiles()

    cohort_path = Path(__file__).parent / "data" / "cohort_profiles.json"
    with open(cohort_path) as f:
        cohorts = json.load(f)

    for uid, p_data in profiles.items():
        profile = UserProfile(**p_data)
        avg = profile.spending_profile.avg_transaction_amount
        features = {
            "avg_amount_7d": avg,
            "avg_amount_30d": avg,
            "std_amount_30d": avg * 0.4,
            "txn_count_1h": 0,
            "txn_count_24h": 3,
            "merchant_diversity": 15,
            "geo_frequency": len(profile.travel_profile.frequent_countries),
            "merchant_frequency": 5,
            "travel_frequency": profile.travel_profile.travel_frequency,
        }
        await feature_store.update_user_features(uid, features)
        for dev in profile.known_devices:
            await feature_store.register_device(uid, dev)
            await feature_store.set_device_reputation(dev, {
                "trust_score": 0.85,
                "fraud_count": 0,
                "account_count": 1,
                "age_days": 180,
                "last_seen_ts": time.time(),
            })
        for loc in profile.known_locations:
            await feature_store.register_location(uid, loc)

    # Seed cohort features
    for cohort_name, cohort_data in cohorts.items():
        flat = {k: v for k, v in cohort_data.items() if isinstance(v, (int, float, str))}
        await feature_store.seed_cohort_features(cohort_name, flat)

    # Seed a few merchant reputations
    trusted_merchants = {
        "merchant_amazon": {"reputation_score": 0.95, "chargeback_rate": 0.001, "refund_rate": 0.03, "fraud_associations": 0, "transaction_volume": 100000, "customer_diversity": 5000},
        "merchant_swiggy": {"reputation_score": 0.92, "chargeback_rate": 0.002, "refund_rate": 0.05, "fraud_associations": 0, "transaction_volume": 50000, "customer_diversity": 3000},
        "merchant_unknown_xyz": {"reputation_score": 0.30, "chargeback_rate": 0.08, "refund_rate": 0.20, "fraud_associations": 3, "transaction_volume": 50, "customer_diversity": 5},
    }
    for mid, data in trusted_merchants.items():
        await feature_store.set_merchant_reputation(mid, data)


# ---------------------------------------------------------------------------
# Demo scenarios
# ---------------------------------------------------------------------------

def _get_demo_scenarios() -> dict:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "account_takeover": {
            "description": "Attacker with new device making large international transfer",
            "user_id": "user_001",
            "transaction": {
                "transaction_id": "demo_ato_001",
                "user_id": "user_001",
                "amount": 85000.0,
                "currency": "INR",
                "merchant_id": "merchant_wire_transfer_co",
                "merchant_name": "Wire Transfer Services",
                "merchant_category": "wire_transfer",
                "device_id": "dev_unknown_attacker_001",
                "device_type": "mobile",
                "ip_address": "45.33.32.156",
                "latitude": 51.508,
                "longitude": -0.128,
                "location_city": "London",
                "location_country": "UK",
                "timestamp": now,
                "transaction_type": "transfer",
                "channel": "online",
                "is_international": True,
                "card_present": False,
            },
        },
        "card_testing": {
            "description": "Fraudster testing stolen card with micro-transactions before large purchase",
            "user_id": "user_005",
            "transaction": {
                "transaction_id": "demo_ct_004",
                "user_id": "user_005",
                "amount": 12500.0,
                "currency": "INR",
                "merchant_id": "merchant_electronics_shop",
                "merchant_name": "Premium Electronics",
                "merchant_category": "electronics",
                "device_id": "dev_mob_006",
                "device_type": "mobile",
                "ip_address": "103.21.244.0",
                "latitude": 19.076,
                "longitude": 72.878,
                "location_city": "Mumbai",
                "location_country": "India",
                "timestamp": now,
                "transaction_type": "purchase",
                "channel": "online",
                "is_international": False,
                "card_present": False,
            },
        },
        "legitimate_travel": {
            "description": "Known traveler making normal purchase abroad — should be approved",
            "user_id": "user_002",
            "transaction": {
                "transaction_id": "demo_legit_001",
                "user_id": "user_002",
                "amount": 3500.0,
                "currency": "INR",
                "merchant_id": "merchant_dubai_restaurant",
                "merchant_name": "Nobu Dubai",
                "merchant_category": "restaurants",
                "device_id": "dev_mob_003",
                "device_type": "mobile",
                "ip_address": "185.220.101.1",
                "latitude": 25.204,
                "longitude": 55.270,
                "location_city": "Dubai",
                "location_country": "UAE",
                "timestamp": now,
                "transaction_type": "purchase",
                "channel": "in-store",
                "is_international": True,
                "card_present": True,
            },
        },
        "impossible_travel": {
            "description": "Transaction in London 10 minutes after transaction in Mumbai — impossible travel",
            "user_id": "user_003",
            "transaction": {
                "transaction_id": "demo_imp_001",
                "user_id": "user_003",
                "amount": 45000.0,
                "currency": "INR",
                "merchant_id": "merchant_london_luxury",
                "merchant_name": "Harrods London",
                "merchant_category": "luxury",
                "device_id": "dev_desk_003_unknown",
                "device_type": "desktop",
                "ip_address": "51.15.0.1",
                "latitude": 51.508,
                "longitude": -0.128,
                "location_city": "London",
                "location_country": "UK",
                "timestamp": now,
                "transaction_type": "purchase",
                "channel": "in-store",
                "is_international": True,
                "card_present": True,
                "metadata": {"prev_city": "Mumbai", "prev_ts_offset_minutes": 10},
            },
        },
        "velocity_fraud": {
            "description": "High-frequency transaction burst — velocity fraud attempt",
            "user_id": "user_005",
            "transaction": {
                "transaction_id": "demo_vel_001",
                "user_id": "user_005",
                "amount": 4800.0,
                "currency": "INR",
                "merchant_id": "merchant_unknown_xyz",
                "merchant_name": "Unknown Merchant XYZ",
                "merchant_category": "gambling",
                "device_id": "dev_mob_006",
                "device_type": "mobile",
                "ip_address": "103.21.244.0",
                "latitude": 19.076,
                "longitude": 72.878,
                "location_city": "Mumbai",
                "location_country": "India",
                "timestamp": now,
                "transaction_type": "purchase",
                "channel": "online",
                "is_international": False,
                "card_present": False,
            },
        },
    }


# ---------------------------------------------------------------------------
# Synthetic Data Endpoints
# ---------------------------------------------------------------------------

class GenerateUsersRequest(BaseModel):
    count: int = 10
    user_type: Optional[str] = None   # None = mixed


class GenerateTransactionsRequest(BaseModel):
    user_count: int = 10
    transaction_count: int = 100
    fraud_rate: float = 0.05
    span_days: int = 7
    format: str = "json"   # "json" | "jsonl"


class GenerateFromCsvRequest(BaseModel):
    filename: str = "bs140513_032310.csv"
    limit: int = 100


@app.post("/generate/from-csv")
async def generate_from_csv(req: GenerateFromCsvRequest):
    try:
        transactions = load_csv_transactions(req.filename, req.limit)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    
    results = []
    for txn in transactions:
        profile = _get_profile(txn.user_id)
        res = await run_fraud_detection(txn, profile)
        results.append(res)
    
    return {
        "status": "success",
        "processed_count": len(results),
        "results": results
    }


class BuildScenarioRequest(BaseModel):
    scenario_name: str = "small_demo"
    custom_config: Optional[dict] = None


@app.post("/generate/users")
async def generate_users(req: GenerateUsersRequest):
    user_type = None
    if req.user_type:
        try:
            user_type = UserType(req.user_type)
        except ValueError:
            raise HTTPException(400, f"Invalid user_type. Valid: {[e.value for e in UserType]}")
    users = generate_user_batch(min(req.count, 500), user_type)
    return {
        "count": len(users),
        "users": [u["metadata"] for u in users],
    }


@app.post("/generate/transactions")
async def generate_transactions_endpoint(req: GenerateTransactionsRequest):
    users = generate_user_batch(min(req.user_count, 200))
    profiles = [u["profile"] for u in users]
    batch = generate_transaction_batch(
        profiles,
        count=min(req.transaction_count, 5000),
        fraud_rate=0.0,   # pure generation; use /generate/scenario for fraud injection
        span_days=req.span_days,
    )
    if req.format == "jsonl":
        return {"format": "jsonl", "data": transactions_to_jsonl(batch), "count": len(batch)}
    return {"format": "json", "count": len(batch), "transactions": batch}


@app.post("/generate/scenario")
async def generate_scenario(req: BuildScenarioRequest):
    try:
        result = build_scenario(req.scenario_name, req.custom_config)
    except ValueError as e:
        raise HTTPException(400, str(e))
    # Return summary + first 50 transactions (full dataset can be large)
    preview = result.copy()
    preview["transactions"] = result["transactions"][:50]
    preview["note"] = f"Showing first 50 of {len(result['transactions'])} transactions"
    return preview


@app.get("/generate/scenarios")
async def list_scenario_presets():
    return {
        name: {"description": cfg.description, "users": cfg.user_count,
               "transactions": cfg.transaction_count, "fraud_rate": cfg.fraud_rate}
        for name, cfg in PRESET_SCENARIOS.items()
    }


# ---------------------------------------------------------------------------
# Feedback Endpoints
# ---------------------------------------------------------------------------

class FeedbackSubmitRequest(BaseModel):
    transaction_id: str
    user_id: str
    system_decision: str
    system_risk_score: float
    analyst_decision: str
    outcome_label: str   # true_positive | false_positive | true_negative | false_negative
    fraud_type_confirmed: Optional[str] = None
    notes: Optional[str] = None
    reviewer_id: Optional[str] = None
    device_id: Optional[str] = None      # device involved in the transaction
    merchant_id: Optional[str] = None    # merchant involved in the transaction


@app.post("/feedback/submit")
@limiter.limit("30/minute")
async def submit_feedback_endpoint(request: Request, req: FeedbackSubmitRequest):
    try:
        label = OutcomeLabel(req.outcome_label)
    except ValueError:
        raise HTTPException(400, f"Invalid outcome_label. Valid: {[e.value for e in OutcomeLabel]}")

    feedback_id = await submit_feedback(
        transaction_id=req.transaction_id,
        user_id=req.user_id,
        system_decision=req.system_decision,
        system_risk_score=req.system_risk_score,
        analyst_decision=req.analyst_decision,
        outcome_label=label,
        fraud_type_confirmed=req.fraud_type_confirmed,
        notes=req.notes,
        reviewer_id=req.reviewer_id,
        device_id=req.device_id,
        merchant_id=req.merchant_id,
    )
    # Process reputation update for the newly submitted record (high-watermark handles idempotency)
    await update_reputation_from_feedback()

    return {"feedback_id": feedback_id, "status": "recorded"}


@app.get("/feedback/stats")
async def feedback_stats():
    return await get_feedback_stats()


@app.get("/feedback/recent")
async def feedback_recent(limit: int = Query(default=20, le=100)):
    return await get_recent_feedback(limit)


@app.get("/feedback/false-positives")
async def feedback_false_positives(limit: int = Query(default=20, le=100)):
    return await get_false_positives(limit)


@app.post("/feedback/evolve")
@limiter.limit("5/minute")
async def trigger_pattern_evolution(request: Request, use_llm: bool = Query(default=False)):
    """
    Trigger pattern evolution.
    use_llm=false (default): deterministic weight adjustment (CORE, fast).
    use_llm=true: LLM-based emerging pattern discovery (OPTIONAL, slower).
    """
    core_result = await adjust_pattern_weights_from_feedback()
    result = {"core_adjustment": core_result}
    if use_llm:
        llm_result = await discover_emerging_patterns()
        result["llm_discovery"] = llm_result
    return result


@app.post("/feedback/update-reputation")
async def trigger_reputation_update(limit: int = Query(default=200, le=500)):
    result = await update_reputation_from_feedback(limit=limit)
    return {"status": "updated", **result}


@app.post("/feedback/user-risk/{user_id}")
async def update_user_risk(user_id: str, confirmed_fraud: bool = Query(default=False)):
    return await update_user_risk_score(user_id, confirmed_fraud)


# ---------------------------------------------------------------------------
# Simulation Endpoints (Upgrade)
# ---------------------------------------------------------------------------

class CampaignRequest(BaseModel):
    campaign_type: Optional[str] = None   # None = random
    apply_adversarial: bool = True
    difficulty_target: Optional[float] = None  # 0-100


class RingRequest(BaseModel):
    ring_type: Optional[str] = None   # None = random
    apply_adversarial: bool = True


class FullSimulationRequest(BaseModel):
    persona_count: int = 10
    span_days: int = 30
    campaign_count: int = 3
    ring_count: int = 2
    fraud_rate: float = 0.07
    apply_adversarial: bool = True
    store_ground_truth: bool = True


class AdversarialRequest(BaseModel):
    transactions: List[dict]
    difficulty_target: Optional[float] = None


@app.post("/simulate/campaign")
async def simulate_campaign(req: CampaignRequest):
    """Generate a fraud campaign with optional adversarial mutations."""
    campaign_type = req.campaign_type
    if campaign_type and campaign_type not in CAMPAIGN_GENERATORS:
        raise HTTPException(400, f"Unknown campaign type. Valid: {list(CAMPAIGN_GENERATORS.keys())}")

    campaign = generate_campaign(campaign_type=campaign_type)
    txns = campaign["transactions"]

    if req.apply_adversarial and txns:
        adv_result = apply_adversarial_mutations(
            txns, difficulty_target=req.difficulty_target
        )
        txns = adv_result["transactions"]
        campaign["attack_difficulty"] = adv_result["attack_difficulty"]
        campaign["mutations_applied"] = adv_result["mutations_applied"]

    # Store ground truth
    gt_records = campaign_to_ground_truth_records(campaign)
    if gt_records:
        for r in gt_records:
            r.attack_difficulty = campaign.get("attack_difficulty", 0.0)
        await bulk_store_ground_truth(gt_records)

    campaign["transactions"] = txns
    campaign["transaction_count"] = len(txns)
    return campaign


@app.post("/simulate/ring")
async def simulate_ring(req: RingRequest):
    """Generate a fraud ring with shared device/IP/merchant graph."""
    if req.ring_type and req.ring_type not in RING_TYPES:
        raise HTTPException(400, f"Unknown ring type. Valid: {RING_TYPES}")

    ring = generate_ring(ring_type=req.ring_type)
    txns = ring.get("transactions", [])

    if req.apply_adversarial and txns:
        adv_result = apply_adversarial_mutations(txns)
        txns = adv_result["transactions"]
        ring["attack_difficulty"] = adv_result["attack_difficulty"]
        ring["mutations_applied"] = adv_result["mutations_applied"]

    # Store ground truth
    gt_records = []
    for txn in txns:
        gt_records.append(GroundTruthRecord(
            transaction_id=txn["transaction_id"],
            is_fraud=txn.get("is_fraud", True),
            fraud_type=txn.get("fraud_type"),
            campaign_id=None,
            ring_id=txn.get("ring_id"),
            attack_difficulty=ring.get("attack_difficulty", 0.0),
            expected_label=txn.get("expected_label", "BLOCKED"),
            persona_type=None,
            amount=txn.get("amount", 0.0),
        ))
    if gt_records:
        await bulk_store_ground_truth(gt_records)

    ring["transactions"] = txns
    ring["transaction_count"] = len(txns)
    return ring


@app.post("/simulate/full")
@limiter.limit("5/minute")
async def simulate_full(request: Request, req: FullSimulationRequest):
    """Full simulation: personas + campaigns + rings + adversarial mutations."""
    results = {
        "persona_count": req.persona_count,
        "campaigns": [],
        "rings": [],
        "all_transactions": [],
        "quality": None,
        "ground_truth_stored": 0,
    }

    # Generate campaigns
    campaign_types = list(CAMPAIGN_GENERATORS.keys())
    for i in range(min(req.campaign_count, 10)):
        ctype = campaign_types[i % len(campaign_types)]
        campaign = generate_campaign(campaign_type=ctype)
        txns = campaign["transactions"]
        if req.apply_adversarial and txns:
            adv = apply_adversarial_mutations(txns)
            txns = adv["transactions"]
            campaign["attack_difficulty"] = adv["attack_difficulty"]
        campaign["transactions"] = txns
        results["campaigns"].append({
            "campaign_id": campaign["campaign_id"],
            "type": campaign["campaign_type"],
            "transaction_count": len(txns),
            "attack_difficulty": campaign.get("attack_difficulty", 0),
        })
        results["all_transactions"].extend(txns)

    # Generate rings
    for i in range(min(req.ring_count, 5)):
        ring_type = RING_TYPES[i % len(RING_TYPES)]
        ring = generate_ring(ring_type=ring_type)
        txns = ring.get("transactions", [])
        if req.apply_adversarial and txns:
            adv = apply_adversarial_mutations(txns)
            txns = adv["transactions"]
        ring["transactions"] = txns
        results["rings"].append({
            "ring_id": ring["ring_id"],
            "type": ring["ring_type"],
            "member_count": ring.get("member_count", 0),
            "transaction_count": len(txns),
        })
        results["all_transactions"].extend(txns)

    # Store ground truth
    if req.store_ground_truth:
        gt_records = []
        for txn in results["all_transactions"]:
            gt_records.append(GroundTruthRecord(
                transaction_id=txn["transaction_id"],
                is_fraud=txn.get("is_fraud", True),
                fraud_type=txn.get("fraud_type"),
                campaign_id=txn.get("campaign_id"),
                ring_id=txn.get("ring_id"),
                attack_difficulty=txn.get("attack_difficulty", 0.0),
                expected_label=txn.get("expected_label", "BLOCKED"),
                persona_type=None,
                amount=txn.get("amount", 0.0),
            ))
        if gt_records:
            await bulk_store_ground_truth(gt_records)
            results["ground_truth_stored"] = len(gt_records)

    # Validate dataset quality
    quality = validate_dataset(results["all_transactions"])
    results["quality"] = {
        "score": quality["quality_score"],
        "passed": quality["passed"],
        "recommendations": quality["recommendations"],
    }
    results["total_transactions"] = len(results["all_transactions"])

    # Don't return all transaction bodies — just summary
    results.pop("all_transactions")
    return results


@app.post("/simulate/adversarial")
async def simulate_adversarial(req: AdversarialRequest):
    """Apply adversarial evasion mutations to a provided transaction list."""
    if not req.transactions:
        raise HTTPException(400, "transactions list cannot be empty")
    result = apply_adversarial_mutations(
        req.transactions,
        difficulty_target=req.difficulty_target,
    )
    return {
        "mutated_count": len(result["transactions"]),
        "mutations_applied": result["mutations_applied"],
        "attack_difficulty": result["attack_difficulty"],
        "transactions": result["transactions"][:20],  # preview
    }


@app.get("/metrics/evaluation")
async def metrics_evaluation():
    """Return ground truth statistics and evaluation data.

    Note: accuracy/precision/recall require actual pipeline predictions stored
    alongside each transaction. Currently returns ground truth composition only.
    To get real detection metrics, run transactions through /detect and compare
    pipeline decisions against ground truth labels.
    """
    stats = await get_gt_stats()
    records = await get_all_gt_records(limit=10000)

    total = len(records)
    fraud_count = sum(1 for r in records if r.is_fraud)
    legit_count = total - fraud_count

    # Fraud type breakdown
    from collections import defaultdict
    by_type: dict = defaultdict(int)
    for r in records:
        if r.fraud_type:
            by_type[r.fraud_type] += 1

    return {
        "ground_truth_stats": stats,
        "dataset_composition": {
            "total_records": total,
            "fraud_count": fraud_count,
            "legitimate_count": legit_count,
            "fraud_rate": round(fraud_count / total, 4) if total else 0,
            "by_fraud_type": dict(by_type),
        },
        "note": (
            "Live detection metrics (precision/recall/F1) require pipeline predictions. "
            "Use POST /detect for each transaction and compare decisions to ground truth labels."
        ),
    }


@app.get("/metrics/confusion-matrix")
async def metrics_confusion_matrix():
    """Return confusion matrix from ground truth store."""
    from app.simulation.ground_truth_store import get_all_records
    records = await get_all_records(limit=10000)
    simulated = {r.transaction_id: r.expected_label for r in records}
    result = await evaluate(simulated)
    return result["overall"]


@app.get("/ground-truth/stats")
async def ground_truth_stats():
    """Summary statistics from the ground truth store."""
    return await get_gt_stats()


# ---------------------------------------------------------------------------
# Extended Simulation Endpoints (Phase 2 Upgrade)
# ---------------------------------------------------------------------------

class PopulationRequest(BaseModel):
    total_users: int = 100
    domestic_only: bool = False


class EvolutionRequest(BaseModel):
    campaign_type: Optional[str] = None
    num_generations: int = 4
    store_ground_truth: bool = True


class LeakageCheckRequest(BaseModel):
    records: List[dict]          # list of {transaction_id, is_fraud, merchant_category, ...}


@app.post("/simulate/population")
async def simulate_population(req: PopulationRequest):
    """Generate a realistic population profile with distributed persona types."""
    count = min(req.total_users, 5000)
    pop = generate_population(total_users=count, domestic_only=req.domestic_only)
    summary = population_to_dict(pop)
    summary["user_ids"] = [u["metadata"]["user_id"] for u in pop.users[:20]]  # preview
    return summary


@app.post("/simulate/evolve")
async def simulate_fraud_evolution(req: EvolutionRequest):
    """
    Generate an evolutionary fraud arc (Generation 1 → 4).
    Shows how fraud adapts from basic to APT-level evasion.
    """
    if req.campaign_type and req.campaign_type not in CAMPAIGN_GENERATORS:
        raise HTTPException(400, f"Unknown campaign type. Valid: {list(CAMPAIGN_GENERATORS.keys())}")

    result = generate_evolved_campaign(
        campaign_type=req.campaign_type,
        num_generations=min(req.num_generations, 10),
    )

    if req.store_ground_truth:
        gt_records = []
        for txn in result.get("transactions", []):
            gt_records.append(GroundTruthRecord(
                transaction_id=txn["transaction_id"],
                is_fraud=txn.get("is_fraud", True),
                fraud_type=txn.get("fraud_type"),
                campaign_id=txn.get("campaign_id"),
                ring_id=txn.get("ring_id"),
                attack_difficulty=txn.get("attack_difficulty", 0.0),
                expected_label=txn.get("expected_label", "BLOCKED"),
                persona_type=None,
                amount=txn.get("amount", 0.0),
                attack_version=txn.get("attack_version", 1),
                campaign_generation=txn.get("campaign_generation", 1),
            ))
        if gt_records:
            await bulk_store_ground_truth(gt_records)

    result.pop("transactions", None)  # omit bulk from response
    return result


@app.get("/simulate/evolution/summary")
async def evolution_summary():
    """Show lineage of all evolved fraud campaigns in this session."""
    tracker = get_evolution_tracker()
    return tracker.get_lineage_summary()


@app.get("/economic/events")
async def economic_events(year: int = Query(default=2025)):
    """List all macro economic events for a given year."""
    env = get_economic_environment(year)
    return {"year": year, "events": env.list_events()}


@app.get("/economic/day-profile")
async def economic_day_profile(
    date_str: str = Query(default=None, alias="date"),
    country: str = Query(default="India"),
):
    """Get economic multipliers for a specific date."""
    from datetime import datetime as _dt
    env = get_economic_environment()
    if date_str:
        try:
            dt = _dt.fromisoformat(date_str)
        except ValueError:
            raise HTTPException(400, "Invalid date format. Use YYYY-MM-DD.")
    else:
        dt = _dt.now(timezone.utc)
    return env.get_day_profile(dt, country)


@app.post("/simulate/leakage-check")
async def check_label_leakage(req: LeakageCheckRequest):
    """
    Detect label leakage in a synthetic dataset.
    A 'REJECT' verdict means a simple rule engine could achieve >80% F1.
    """
    if not req.records:
        raise HTTPException(400, "records list cannot be empty")
    report = detect_leakage(req.records)
    return leakage_report_to_dict(report)


@app.get("/simulate/leakage-check/from-ground-truth")
async def leakage_check_from_ground_truth(limit: int = Query(default=5000, le=50000)):
    """Run label leakage check directly against the ground truth store."""
    records = await get_all_gt_records(limit=limit)
    if not records:
        raise HTTPException(404, "No records in ground truth store. Run /simulate/full first.")
    record_dicts = [
        {
            "transaction_id": r.transaction_id,
            "is_fraud": r.is_fraud,
            "fraud_type": r.fraud_type,
            "persona_type": r.persona_type,
            "amount": r.amount,
            "attack_difficulty": r.attack_difficulty,
            "campaign_generation": r.campaign_generation,
        }
        for r in records
    ]
    report = detect_leakage(record_dicts)
    return leakage_report_to_dict(report)


@app.get("/metrics/campaign-performance")
async def metrics_campaign_performance():
    """Per-campaign accuracy metrics from ground truth store."""
    stats = await get_gt_stats()
    by_campaign = stats.get("by_campaign", {})

    records = await get_all_gt_records(limit=50000)
    campaign_metrics = {}
    for r in records:
        if not r.campaign_id:
            continue
        cid = r.campaign_id
        if cid not in campaign_metrics:
            campaign_metrics[cid] = {
                "campaign_id": cid,
                "total": 0, "fraud": 0,
                "fraud_types": set(),
                "avg_difficulty": 0.0,
                "generation": r.campaign_generation,
            }
        m = campaign_metrics[cid]
        m["total"] += 1
        if r.is_fraud:
            m["fraud"] += 1
            if r.fraud_type:
                m["fraud_types"].add(r.fraud_type)
        m["avg_difficulty"] = (m["avg_difficulty"] * (m["total"] - 1) + r.attack_difficulty) / m["total"]

    result = []
    for cid, m in campaign_metrics.items():
        m["fraud_rate"] = round(m["fraud"] / max(m["total"], 1), 4)
        m["avg_difficulty"] = round(m["avg_difficulty"], 1)
        m["fraud_types"] = list(m["fraud_types"])
        result.append(m)

    result.sort(key=lambda x: -x["avg_difficulty"])
    return {"campaigns": result, "total_campaigns": len(result)}


@app.get("/metrics/fraud-type-performance")
async def metrics_fraud_type_performance():
    """Per fraud-type metrics: count, avg difficulty, expected detection rate."""
    records = await get_all_gt_records(limit=50000)
    if not records:
        return {"fraud_types": []}

    type_buckets: Dict = {}
    for r in records:
        if not r.is_fraud:
            continue
        ft = r.fraud_type or "unknown"
        if ft not in type_buckets:
            type_buckets[ft] = {
                "fraud_type": ft, "count": 0,
                "total_difficulty": 0.0,
                "by_generation": {},
            }
        b = type_buckets[ft]
        b["count"] += 1
        b["total_difficulty"] += r.attack_difficulty
        gen = str(r.campaign_generation)
        b["by_generation"][gen] = b["by_generation"].get(gen, 0) + 1

    result = []
    for ft, b in type_buckets.items():
        avg_diff = round(b["total_difficulty"] / max(b["count"], 1), 1)
        # Estimate detection rate: harder = lower detection
        est_detection = max(0.05, min(0.99, 1.0 - (avg_diff / 130.0)))
        result.append({
            "fraud_type": ft,
            "count": b["count"],
            "avg_difficulty": avg_diff,
            "estimated_detection_rate": round(est_detection, 3),
            "by_generation": b["by_generation"],
        })

    result.sort(key=lambda x: -x["count"])
    return {"fraud_types": result, "total_fraud_transactions": sum(r["count"] for r in result)}
