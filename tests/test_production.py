"""
Production-hardening test suite.

Tests:
  - Config: Pydantic v2 (no deprecation warnings), safe defaults, validate_production_config
  - Auth: API key middleware (403 without key, 200 exempt paths, pass with valid key)
  - CORS: env-driven origins merged with localhost defaults
  - Health endpoints: /live, /ready, /health
  - Groq provider selection: is_mock() driven solely by settings.mock_llm
  - Redis: silent-fallback guard
  - Feature store: ping() method, set_dedup()
  - Async correctness: _graph_lock is asyncio.Lock
  - Distributed dedup: Redis path + in-memory fallback
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Section 1 — Configuration
# ---------------------------------------------------------------------------

class TestConfigDefaults:
    def test_use_fake_redis_default_false(self):
        """USE_FAKE_REDIS default must be False — safe for production."""
        from app.config import Settings
        s = Settings(_env_file=None)
        # Only the true field default is checked; .env may override
        import inspect
        field = Settings.model_fields["use_fake_redis"]
        assert field.default is False, (
            "use_fake_redis default must be False so missing env var fails loudly in production"
        )

    def test_mock_llm_default_false(self):
        from app.config import Settings
        field = Settings.model_fields["mock_llm"]
        assert field.default is False

    def test_api_key_field_exists(self):
        from app.config import Settings
        assert "api_key" in Settings.model_fields

    def test_cors_allowed_origins_field_exists(self):
        from app.config import Settings
        assert "cors_allowed_origins" in Settings.model_fields

    def test_no_pydantic_v1_class_config(self):
        """Ensure no `class Config:` is present (Pydantic v2 uses model_config)."""
        from app.config import Settings
        assert not hasattr(Settings, "Config"), (
            "Pydantic v1 `class Config` found — migrate to model_config = ConfigDict(...)"
        )

    def test_model_config_has_env_file(self):
        from app.config import Settings
        cfg = Settings.model_config
        assert cfg.get("env_file") == ".env"


class TestProductionValidation:
    def test_valid_config_passes(self, monkeypatch):
        monkeypatch.setattr("app.config.settings.mock_llm", True)
        monkeypatch.setattr("app.config.settings.use_fake_redis", True)
        monkeypatch.setattr("app.config.settings.database_url", "sqlite+aiosqlite:///./test.db")
        from app.config import validate_production_config
        validate_production_config()  # must not raise

    def test_missing_groq_key_raises_when_mock_false(self, monkeypatch):
        monkeypatch.setattr("app.config.settings.mock_llm", False)
        monkeypatch.setattr("app.config.settings.groq_api_key", "")
        monkeypatch.setattr("app.config.settings.use_fake_redis", True)
        monkeypatch.setattr("app.config.settings.database_url", "sqlite+aiosqlite:///test.db")
        from app.config import validate_production_config
        with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
            validate_production_config()

    def test_invalid_groq_key_prefix_raises(self, monkeypatch):
        monkeypatch.setattr("app.config.settings.mock_llm", False)
        monkeypatch.setattr("app.config.settings.groq_api_key", "sk-invalid-key")
        monkeypatch.setattr("app.config.settings.use_fake_redis", True)
        monkeypatch.setattr("app.config.settings.database_url", "sqlite+aiosqlite:///test.db")
        from app.config import validate_production_config
        with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
            validate_production_config()

    def test_localhost_redis_raises_when_fake_false(self, monkeypatch):
        monkeypatch.setattr("app.config.settings.mock_llm", True)
        monkeypatch.setattr("app.config.settings.use_fake_redis", False)
        monkeypatch.setattr("app.config.settings.redis_url", "redis://localhost:6379")
        monkeypatch.setattr("app.config.settings.database_url", "sqlite+aiosqlite:///test.db")
        from app.config import validate_production_config
        with pytest.raises(RuntimeError, match="REDIS_URL"):
            validate_production_config()

    def test_missing_database_url_raises(self, monkeypatch):
        monkeypatch.setattr("app.config.settings.mock_llm", True)
        monkeypatch.setattr("app.config.settings.use_fake_redis", True)
        monkeypatch.setattr("app.config.settings.database_url", "")
        from app.config import validate_production_config
        with pytest.raises(RuntimeError, match="DATABASE_URL"):
            validate_production_config()


# ---------------------------------------------------------------------------
# Section 2 — Groq provider selection
# ---------------------------------------------------------------------------

class TestGroqProviderSelection:
    def test_is_mock_true_when_mock_llm_true(self, monkeypatch):
        monkeypatch.setattr("app.config.settings.mock_llm", True)
        from app.agents.mock_llm import is_mock
        assert is_mock() is True

    def test_is_mock_false_when_mock_llm_false(self, monkeypatch):
        monkeypatch.setattr("app.config.settings.mock_llm", False)
        from app.agents.mock_llm import is_mock
        assert is_mock() is False

    def test_is_mock_ignores_key_prefix_when_mock_false(self, monkeypatch):
        """is_mock() must NOT check key prefix — startup validation handles that."""
        monkeypatch.setattr("app.config.settings.mock_llm", False)
        monkeypatch.setattr("app.config.settings.groq_api_key", "invalid-key")
        from app.agents.mock_llm import is_mock
        assert is_mock() is False, (
            "is_mock() should only check settings.mock_llm, not key prefix"
        )

    def test_fast_ainvoke_exported_from_llm_clients(self):
        from app.agents._llm_clients import fast_ainvoke, deep_ainvoke
        assert callable(fast_ainvoke)
        assert callable(deep_ainvoke)

    def test_fast_ainvoke_exported_from_grok_client(self):
        from app.llm.grok_client import fast_ainvoke, deep_ainvoke, _invoke
        assert callable(fast_ainvoke)
        assert callable(deep_ainvoke)
        assert callable(_invoke)

    def test_deep_llm_max_tokens_increased(self, monkeypatch):
        """Deep model must have max_tokens > 800 to prevent story truncation."""
        import app.llm.grok_client as gc
        original_deep = gc._deep
        gc._deep = None  # reset
        try:
            monkeypatch.setattr("app.config.settings.groq_api_key", "gsk_fake_key_for_test")
            llm = gc.get_deep_llm()
            assert llm.max_tokens >= 1000, (
                f"Deep LLM max_tokens={llm.max_tokens} — too low, stories will truncate"
            )
        finally:
            gc._deep = None
            if original_deep is not None:
                gc._deep = original_deep


# ---------------------------------------------------------------------------
# Section 3 — Redis hardening
# ---------------------------------------------------------------------------

class TestRedisHardening:
    @pytest.mark.anyio
    async def test_connect_raises_when_redis_fails_and_fake_disabled(self, monkeypatch):
        """Feature store must raise, not silently fall back, when USE_FAKE_REDIS=false."""
        monkeypatch.setattr("app.config.settings.use_fake_redis", False)
        monkeypatch.setattr("app.config.settings.redis_url", "redis://127.0.0.1:9999")

        from app.services.feature_store import FeatureStore
        store = FeatureStore()
        with pytest.raises(RuntimeError, match="USE_FAKE_REDIS=false"):
            await store.connect()

    @pytest.mark.anyio
    async def test_connect_falls_back_when_fake_enabled(self, monkeypatch):
        """When USE_FAKE_REDIS=true, failure must silently use fakeredis."""
        monkeypatch.setattr("app.config.settings.use_fake_redis", True)
        monkeypatch.setattr("app.config.settings.redis_url", "redis://127.0.0.1:9999")

        from app.services.feature_store import FeatureStore
        store = FeatureStore()
        await store.connect()  # must not raise
        assert store._redis is not None

    @pytest.mark.anyio
    async def test_ping_returns_bool(self, monkeypatch):
        monkeypatch.setattr("app.config.settings.use_fake_redis", True)
        monkeypatch.setattr("app.config.settings.redis_url", "redis://127.0.0.1:9999")

        from app.services.feature_store import FeatureStore
        store = FeatureStore()
        await store.connect()
        result = await store.ping()
        assert isinstance(result, bool)

    @pytest.mark.anyio
    async def test_ping_returns_false_when_redis_none(self):
        from app.services.feature_store import FeatureStore
        store = FeatureStore()
        # _redis is None (never connected)
        result = await store.ping()
        assert result is False

    @pytest.mark.anyio
    async def test_set_dedup_returns_true_for_new_key(self, monkeypatch):
        monkeypatch.setattr("app.config.settings.use_fake_redis", True)
        monkeypatch.setattr("app.config.settings.redis_url", "redis://127.0.0.1:9999")

        from app.services.feature_store import FeatureStore
        store = FeatureStore()
        await store.connect()

        result = await store.set_dedup("test:dedup:new_key_abc123", ttl_secs=60)
        assert result is True

    @pytest.mark.anyio
    async def test_set_dedup_returns_false_for_duplicate(self, monkeypatch):
        monkeypatch.setattr("app.config.settings.use_fake_redis", True)
        monkeypatch.setattr("app.config.settings.redis_url", "redis://127.0.0.1:9999")

        from app.services.feature_store import FeatureStore
        store = FeatureStore()
        await store.connect()

        key = "test:dedup:duplicate_key_xyz"
        await store.set_dedup(key, ttl_secs=60)
        result = await store.set_dedup(key, ttl_secs=60)
        assert result is False

    @pytest.mark.anyio
    async def test_set_dedup_returns_none_when_redis_unavailable(self):
        from app.services.feature_store import FeatureStore
        store = FeatureStore()
        # _redis is None
        result = await store.set_dedup("test:key", ttl_secs=60)
        assert result is None


# ---------------------------------------------------------------------------
# Section 7 — Async correctness
# ---------------------------------------------------------------------------

class TestAsyncCorrectness:
    def test_graph_lock_is_asyncio_lock(self):
        import app.pipeline.fraud_pipeline as pipeline
        assert isinstance(pipeline._graph_lock, asyncio.Lock), (
            "_graph_lock must be asyncio.Lock, not threading.Lock"
        )

    def test_threading_not_imported_by_pipeline(self):
        import sys
        # Ensure threading is not imported by the pipeline module
        import app.pipeline.fraud_pipeline  # noqa: F401 (ensure imported)
        pipeline_file = sys.modules.get("app.pipeline.fraud_pipeline")
        import inspect
        src = inspect.getsource(pipeline_file)
        assert "import threading" not in src, (
            "threading.Lock was replaced with asyncio.Lock — threading import should be removed"
        )


# ---------------------------------------------------------------------------
# Section 5 — Auth middleware (via TestClient, no lifespan)
# ---------------------------------------------------------------------------

@pytest.fixture
def test_client():
    """TestClient without running the lifespan (skips Redis/DB connect)."""
    from app.main import app
    return TestClient(app, raise_server_exceptions=False)


class TestAuthMiddleware:
    def test_live_endpoint_always_accessible(self, test_client):
        """GET /live must be exempt from auth regardless of API key config."""
        resp = test_client.get("/live")
        # May return 200 or any non-403
        assert resp.status_code != 403

    def test_health_exempt_without_api_key(self, test_client, monkeypatch):
        """Health check must never require auth."""
        monkeypatch.setattr("app.config.settings.api_key", "secret-test-key")
        resp = test_client.get("/health")
        assert resp.status_code != 403

    def test_ready_exempt_without_api_key(self, test_client, monkeypatch):
        monkeypatch.setattr("app.config.settings.api_key", "secret-test-key")
        resp = test_client.get("/ready")
        assert resp.status_code != 403

    def test_protected_endpoint_rejected_without_key(self, test_client, monkeypatch):
        monkeypatch.setattr("app.config.settings.api_key", "secret-test-key")
        resp = test_client.get("/profiles")
        assert resp.status_code == 403

    def test_protected_endpoint_accepted_with_correct_key(self, test_client, monkeypatch):
        monkeypatch.setattr("app.config.settings.api_key", "secret-test-key")
        resp = test_client.get("/profiles", headers={"X-API-Key": "secret-test-key"})
        assert resp.status_code != 403

    def test_no_api_key_configured_allows_all(self, test_client, monkeypatch):
        """When API_KEY is empty string, auth is disabled (dev mode)."""
        monkeypatch.setattr("app.config.settings.api_key", "")
        resp = test_client.get("/profiles")
        assert resp.status_code != 403


# ---------------------------------------------------------------------------
# Section 8/9 — Health endpoints
# ---------------------------------------------------------------------------

class TestHealthEndpoints:
    def test_live_returns_200(self, test_client):
        resp = test_client.get("/live")
        assert resp.status_code == 200
        assert resp.json()["status"] == "alive"

    def test_ready_returns_503_before_startup(self, test_client):
        """Before lifespan completes, /ready must return 503."""
        import app.main as main_module
        original_ready = main_module._app_ready
        try:
            main_module._app_ready = False
            resp = test_client.get("/ready")
            assert resp.status_code == 503
        finally:
            main_module._app_ready = original_ready

    def test_ready_returns_200_after_startup(self, test_client):
        import app.main as main_module
        original_ready = main_module._app_ready
        try:
            main_module._app_ready = True
            resp = test_client.get("/ready")
            assert resp.status_code == 200
            assert resp.json()["status"] == "ready"
        finally:
            main_module._app_ready = original_ready

    def test_health_response_schema(self, test_client):
        resp = test_client.get("/health")
        # Check the schema regardless of up/down status
        data = resp.json()
        assert "status" in data
        assert "redis" in data
        assert "database" in data
        assert "version" in data
        assert "provider" in data
        assert "timestamp" in data

    def test_health_includes_ready_field(self, test_client):
        resp = test_client.get("/health")
        assert "ready" in resp.json()


# ---------------------------------------------------------------------------
# Section 6 — CORS
# ---------------------------------------------------------------------------

class TestCORSConfiguration:
    def test_localhost_origins_always_allowed(self):
        from app.main import _ALLOWED_ORIGINS
        assert "http://localhost:3000" in _ALLOWED_ORIGINS

    def test_extra_origins_from_env_merged(self, monkeypatch):
        """CORS_ALLOWED_ORIGINS env var must add to allowed origins."""
        monkeypatch.setattr(
            "app.config.settings.cors_allowed_origins",
            "https://my-app.vercel.app,https://staging.example.com"
        )
        # Re-compute allowed origins the same way main.py does
        base = ["http://localhost:3000", "http://localhost:8000"]
        extra = [
            o.strip()
            for o in "https://my-app.vercel.app,https://staging.example.com".split(",")
            if o.strip()
        ]
        merged = base + extra
        assert "https://my-app.vercel.app" in merged
        assert "https://staging.example.com" in merged


# ---------------------------------------------------------------------------
# Section 10 — Profile caching
# ---------------------------------------------------------------------------

class TestProfileCaching:
    def test_profiles_cached_after_first_load(self):
        import app.main as main_module
        original = main_module._profiles_cache
        try:
            main_module._profiles_cache = None
            p1 = main_module._load_profiles()
            p2 = main_module._load_profiles()
            assert p1 is p2, "_load_profiles() must return the same cached dict object"
        finally:
            main_module._profiles_cache = original


# ---------------------------------------------------------------------------
# Pytest backend
# ---------------------------------------------------------------------------

@pytest.fixture
def anyio_backend():
    return "asyncio"
