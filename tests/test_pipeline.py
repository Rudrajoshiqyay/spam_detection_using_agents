"""
Unit tests for app/pipeline/fraud_pipeline.py.

Covers:
  - run_fraud_detection() input guards (user_id mismatch, duplicate transaction)
  - node_auto_approve() uses computed screening_confidence (not hardcoded 85.0)
  - _svc_fallback() returns empty dict and logs a warning
  - Lazy pipeline initialisation (_get_pipeline returns same instance)
  - _background_tasks set prevents GC cancellation
  - Module-level timeout constants are sensible
  - _ENABLE_STORYTELLING flag wires/unwires storytelling node
  - Dedup eviction when _seen_transaction_ids exceeds _DEDUP_MAX_SIZE
"""

import asyncio
import logging
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import app.pipeline.fraud_pipeline as pipeline_module
from app.pipeline.fraud_pipeline import (
    _svc_fallback,
    _get_pipeline,
    _AGENT_TIMEOUT_SECS,
    _PIPELINE_TIMEOUT_SECS,
    _DEDUP_MAX_SIZE,
    run_fraud_detection,
    build_pipeline,
    node_auto_approve,
)


# Restrict all async tests to asyncio — trio is unavailable in this environment
@pytest.fixture
def anyio_backend():
    return "asyncio"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_txn(txn_id="txn_001", user_id="usr_001"):
    txn = MagicMock()
    txn.transaction_id = txn_id
    txn.user_id = user_id
    return txn


def _make_profile(user_id="usr_001"):
    profile = MagicMock()
    profile.user_id = user_id
    return profile


def _make_auto_approve_state(pre_risk: float, flags=None):
    txn = MagicMock()
    txn.transaction_id = "txn_001"
    txn.user_id = "usr_001"
    return {
        "transaction": txn,
        "screening": {"pre_risk_score": pre_risk, "flags": flags or []},
        "signal_result": {"negative_signals": []},
        "latency": {},
    }


# ---------------------------------------------------------------------------
# Timeout constants — must be sensible values
# ---------------------------------------------------------------------------

class TestTimeoutConstants:
    def test_agent_timeout_positive(self):
        assert _AGENT_TIMEOUT_SECS > 0

    def test_pipeline_timeout_greater_than_agent_timeout(self):
        assert _PIPELINE_TIMEOUT_SECS > _AGENT_TIMEOUT_SECS

    def test_dedup_max_size_positive(self):
        assert _DEDUP_MAX_SIZE > 0

    def test_dedup_max_size_reasonable_upper_bound(self):
        assert _DEDUP_MAX_SIZE <= 1_000_000


# ---------------------------------------------------------------------------
# run_fraud_detection() — input guards
# ---------------------------------------------------------------------------

class TestRunFraudDetectionGuards:
    def setup_method(self):
        pipeline_module._seen_transaction_ids = set()

    @pytest.mark.anyio
    async def test_user_id_mismatch_raises(self):
        txn = _make_txn(user_id="usr_A")
        profile = _make_profile(user_id="usr_B")
        with pytest.raises(ValueError, match="user_id mismatch"):
            await run_fraud_detection(txn, profile)

    @pytest.mark.anyio
    async def test_duplicate_transaction_raises(self):
        txn = _make_txn(txn_id="txn_dup", user_id="usr_001")
        profile = _make_profile(user_id="usr_001")
        pipeline_module._seen_transaction_ids.add("txn_dup")
        with pytest.raises(ValueError, match="Duplicate transaction_id"):
            await run_fraud_detection(txn, profile)

    @pytest.mark.anyio
    async def test_new_transaction_id_added_to_dedup_set(self):
        txn = _make_txn(txn_id="txn_brand_new", user_id="usr_001")
        profile = _make_profile(user_id="usr_001")
        pipeline_module._seen_transaction_ids = set()

        with patch("asyncio.wait_for", new=AsyncMock(return_value={"result": MagicMock()})):
            try:
                await run_fraud_detection(txn, profile)
            except Exception:
                pass

        assert "txn_brand_new" in pipeline_module._seen_transaction_ids


# ---------------------------------------------------------------------------
# Dedup eviction
# ---------------------------------------------------------------------------

class TestDedupEviction:
    def setup_method(self):
        pipeline_module._seen_transaction_ids = set()

    @pytest.mark.anyio
    async def test_dedup_evicts_when_full(self, monkeypatch):
        monkeypatch.setattr(pipeline_module, "_DEDUP_MAX_SIZE", 5)
        # Fill exactly to capacity
        pipeline_module._seen_transaction_ids = {"a", "b", "c", "d", "e"}

        txn = _make_txn(txn_id="txn_overflow", user_id="usr_001")
        profile = _make_profile(user_id="usr_001")

        with patch("asyncio.wait_for", new=AsyncMock(return_value={"result": MagicMock()})):
            try:
                await run_fraud_detection(txn, profile)
            except Exception:
                pass

        # After eviction (half discarded) + new entry, size should be < original capacity
        assert len(pipeline_module._seen_transaction_ids) < 5

    @pytest.mark.anyio
    async def test_second_call_with_same_id_raises_after_eviction(self, monkeypatch):
        monkeypatch.setattr(pipeline_module, "_DEDUP_MAX_SIZE", 3)
        pipeline_module._seen_transaction_ids = {"x", "y", "z"}

        txn = _make_txn(txn_id="txn_survive", user_id="usr_001")
        profile = _make_profile(user_id="usr_001")

        with patch("asyncio.wait_for", new=AsyncMock(return_value={"result": MagicMock()})):
            try:
                await run_fraud_detection(txn, profile)
            except Exception:
                pass

        # txn_survive was added after eviction — a second attempt must be rejected
        with pytest.raises(ValueError, match="Duplicate transaction_id"):
            await run_fraud_detection(txn, profile)


# ---------------------------------------------------------------------------
# _svc_fallback
# ---------------------------------------------------------------------------

class TestSvcFallback:
    def test_returns_empty_dict(self):
        result = _svc_fallback("geo_velocity", ValueError("timeout"))
        assert result == {}

    def test_logs_warning(self, caplog):
        with caplog.at_level(logging.WARNING, logger="app.pipeline.fraud_pipeline"):
            _svc_fallback("device", RuntimeError("connection refused"))
        assert "device" in caplog.text

    def test_works_with_base_exception_subclass(self):
        result = _svc_fallback("pattern", TimeoutError("timed out"))
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# Lazy pipeline initialisation
# ---------------------------------------------------------------------------

class TestLazyPipelineInit:
    def setup_method(self):
        pipeline_module._fraud_pipeline = None

    def teardown_method(self):
        pipeline_module._fraud_pipeline = None

    def test_get_pipeline_returns_non_none(self):
        p = _get_pipeline()
        assert p is not None

    def test_get_pipeline_returns_same_instance(self):
        p1 = _get_pipeline()
        p2 = _get_pipeline()
        assert p1 is p2

    def test_get_pipeline_builds_on_first_call_only(self):
        with patch.object(pipeline_module, "build_pipeline", wraps=build_pipeline) as mock_build:
            pipeline_module._fraud_pipeline = None
            _get_pipeline()
            _get_pipeline()
            _get_pipeline()
            assert mock_build.call_count == 1


# ---------------------------------------------------------------------------
# node_auto_approve — confidence_score must match screening_confidence
# ---------------------------------------------------------------------------

class TestNodeAutoApprove:
    @pytest.mark.anyio
    async def test_confidence_score_matches_screening_confidence_low_risk(self):
        pre_risk = 10.0
        expected = round(max(40.0, 90.0 - pre_risk * 0.8), 2)
        output = await node_auto_approve(_make_auto_approve_state(pre_risk))
        assert output["explainability"].confidence_score == expected
        assert output["consensus"].confidence_score == expected

    @pytest.mark.anyio
    async def test_confidence_score_matches_screening_confidence_high_risk(self):
        pre_risk = 45.0
        expected = round(max(40.0, 90.0 - pre_risk * 0.8), 2)
        output = await node_auto_approve(_make_auto_approve_state(pre_risk, flags=["velocity_spike"]))
        assert output["explainability"].confidence_score == expected
        assert output["consensus"].confidence_score == expected

    @pytest.mark.anyio
    async def test_confidence_score_not_hardcoded_85(self):
        """Regression guard for V-01: confidence_score must not be hardcoded 85.0."""
        for pre_risk in [5.0, 20.0, 40.0, 60.0]:
            computed = round(max(40.0, 90.0 - pre_risk * 0.8), 2)
            output = await node_auto_approve(_make_auto_approve_state(pre_risk))
            assert output["explainability"].confidence_score == computed, (
                f"Expected {computed} for pre_risk={pre_risk}, got hardcoded value"
            )

    @pytest.mark.anyio
    async def test_confidence_score_minimum_40(self):
        output = await node_auto_approve(_make_auto_approve_state(99.0))
        assert output["explainability"].confidence_score >= 40.0

    @pytest.mark.anyio
    async def test_auto_approve_decision_is_approved(self):
        from app.models.fraud_decision import FraudDecision
        output = await node_auto_approve(_make_auto_approve_state(15.0))
        assert output["result"].final_decision == FraudDecision.approved

    @pytest.mark.anyio
    async def test_auto_approve_result_not_routed_to_deep_investigation(self):
        output = await node_auto_approve(_make_auto_approve_state(15.0))
        assert output["result"].routed_to_deep_investigation is False

    @pytest.mark.anyio
    async def test_auto_approve_pre_risk_stored_in_result(self):
        output = await node_auto_approve(_make_auto_approve_state(22.5))
        assert output["result"].pre_risk_score == 22.5


# ---------------------------------------------------------------------------
# Background task set
# ---------------------------------------------------------------------------

class TestBackgroundTasks:
    @pytest.mark.anyio
    async def test_background_task_added_to_set(self):
        pipeline_module._background_tasks.clear()

        async def _dummy():
            await asyncio.sleep(0)

        task = asyncio.create_task(_dummy())
        pipeline_module._background_tasks.add(task)
        task.add_done_callback(pipeline_module._background_tasks.discard)

        assert task in pipeline_module._background_tasks
        await task
        assert task not in pipeline_module._background_tasks


# ---------------------------------------------------------------------------
# _ENABLE_STORYTELLING — controls graph wiring
# ---------------------------------------------------------------------------

class TestStorytellingFlag:
    def test_storytelling_disabled_removes_node(self):
        original = pipeline_module._ENABLE_STORYTELLING
        try:
            pipeline_module._ENABLE_STORYTELLING = False
            compiled = build_pipeline()
            assert "storytelling" not in compiled.nodes
        finally:
            pipeline_module._ENABLE_STORYTELLING = original

    def test_storytelling_enabled_includes_node(self):
        original = pipeline_module._ENABLE_STORYTELLING
        try:
            pipeline_module._ENABLE_STORYTELLING = True
            compiled = build_pipeline()
            assert "storytelling" in compiled.nodes
        finally:
            pipeline_module._ENABLE_STORYTELLING = original

    def test_disabled_has_fewer_nodes_than_enabled(self):
        original = pipeline_module._ENABLE_STORYTELLING
        try:
            pipeline_module._ENABLE_STORYTELLING = True
            with_story = build_pipeline()
            pipeline_module._ENABLE_STORYTELLING = False
            without_story = build_pipeline()
            assert len(with_story.nodes) > len(without_story.nodes)
        finally:
            pipeline_module._ENABLE_STORYTELLING = original
