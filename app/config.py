import logging
from pydantic import ConfigDict
from pydantic_settings import BaseSettings

_logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", extra="ignore")

    # LLM (Groq)
    groq_api_key: str = ""
    fast_model: str = "llama-3.1-8b-instant"
    deep_model: str = "llama-3.3-70b-versatile"
    mock_llm: bool = False

    # Redis
    redis_url: str = "redis://localhost:6379"
    upstash_redis_rest_url: str = ""
    upstash_redis_rest_token: str = ""
    use_fake_redis: bool = False  # safe default: False forces real Redis in prod

    # Database
    database_url: str = "sqlite+aiosqlite:///./fraud_feedback.db"

    # Security
    api_key: str = ""  # empty = auth disabled (dev); non-empty = enforced on all non-monitoring endpoints
    cors_allowed_origins: str = ""  # comma-separated extra origins merged with localhost defaults

    # Detection thresholds
    fast_screening_threshold: int = 35
    high_risk_threshold: int = 70

    # Observability
    log_level: str = "INFO"
    app_env: str = "development"  # "production" for prod deployments


settings = Settings()


def validate_production_config() -> None:
    """
    Called at startup — raises RuntimeError on unsafe or missing configuration.

    This is intentionally NOT a Pydantic validator so that tests that import
    individual modules without going through main.py lifespan are unaffected.
    """
    errors: list[str] = []

    if not settings.mock_llm:
        if not settings.groq_api_key.startswith("gsk_"):
            errors.append(
                "GROQ_API_KEY is missing or invalid (must start with 'gsk_'). "
                "Set MOCK_LLM=true for demo/test mode."
            )

    if not settings.use_fake_redis:
        if not settings.redis_url or settings.redis_url == "redis://localhost:6379":
            errors.append(
                "REDIS_URL must point to a real Redis instance when USE_FAKE_REDIS=false. "
                "Example: rediss://default:<token>@<host>.upstash.io:6379"
            )

    if not settings.database_url:
        errors.append("DATABASE_URL must be configured.")

    if errors:
        msg = "FraudGuard AI startup failed — configuration errors detected:\n" + "\n".join(
            f"  • {e}" for e in errors
        )
        raise RuntimeError(msg)

    _logger.info(
        "Configuration validated — env=%s mock_llm=%s use_fake_redis=%s db=%s",
        settings.app_env,
        settings.mock_llm,
        settings.use_fake_redis,
        "postgresql" if "postgresql" in settings.database_url else "sqlite",
    )
