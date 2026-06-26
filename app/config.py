from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    redis_url: str = "redis://localhost:6379"
    database_url: str = "sqlite+aiosqlite:///./fraud_detection.db"

    # Stage-1 routing thresholds
    fast_screening_threshold: int = 35   # below = auto-approve
    high_risk_threshold: int = 70        # above = auto-block in screening

    # Model selection
    fast_model: str = "claude-haiku-4-5-20251001"   # parallel analysis agents
    deep_model: str = "claude-sonnet-4-6"            # investigation / storytelling

    # Demo / dev flags
    mock_llm: bool = False    # skip LLM calls, use deterministic fallbacks
    use_fake_redis: bool = True  # auto-fallback to fakeredis if real Redis down

    log_level: str = "INFO"

    class Config:
        env_file = ".env"


settings = Settings()
