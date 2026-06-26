"""
Unit tests for app/models/ — validates schema correctness, field bounds,
enum enforcement, and serialization/deserialization behaviour.
"""

import pytest
from datetime import datetime, timezone, timedelta
from pydantic import ValidationError

from app.models.transaction import Transaction, DeviceType, TransactionType, Channel
from app.models.user_profile import (
    UserProfile, UserType, RiskCategory, TravelFrequency, AccountStatus,
    SpendingProfile, TravelProfile, AdaptiveThresholds,
)
from app.models.evidence import EvidenceItem, EvidenceStrength, InvestigationPackage
from app.models.fraud_decision import (
    AgentRisk, ConsensusResult, ExplainabilityResult, CounterfactualResult,
    AnalystRecommendation, FraudDetectionResult, FraudDecision,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _valid_transaction(**overrides) -> dict:
    base = dict(
        transaction_id="txn_001",
        user_id="usr_001",
        amount=500.0,
        merchant_id="mrc_001",
        merchant_name="Test Store",
        merchant_category="groceries",
        device_id="dev_001",
        ip_address="103.1.2.3",
        latitude=19.076,
        longitude=72.878,
        location_city="Mumbai",
        location_country="India",
    )
    base.update(overrides)
    return base


def _valid_spending_profile(**overrides) -> dict:
    base = dict(avg_transaction_amount=1000.0, max_transaction_amount=50000.0, monthly_spend_limit=100000.0)
    base.update(overrides)
    return base


def _valid_user_profile(**overrides) -> dict:
    base = dict(
        user_id="usr_001",
        user_type=UserType.working_professional,
        risk_category=RiskCategory.low,
        spending_profile=SpendingProfile(**_valid_spending_profile()),
        travel_profile=TravelProfile(),
        thresholds=AdaptiveThresholds(),
    )
    base.update(overrides)
    return base


def _valid_investigation_package(**overrides) -> dict:
    base = dict(transaction_id="txn_001", user_id="usr_001", pre_risk_score=30.0)
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Transaction — amount validation
# ---------------------------------------------------------------------------

class TestTransactionAmount:
    def test_positive_amount_accepted(self):
        txn = Transaction(**_valid_transaction(amount=100.0))
        assert txn.amount == 100.0

    def test_zero_amount_raises(self):
        with pytest.raises(ValidationError):
            Transaction(**_valid_transaction(amount=0.0))

    def test_negative_amount_raises(self):
        with pytest.raises(ValidationError):
            Transaction(**_valid_transaction(amount=-50.0))

    def test_very_small_positive_accepted(self):
        txn = Transaction(**_valid_transaction(amount=0.01))
        assert txn.amount == pytest.approx(0.01)


# ---------------------------------------------------------------------------
# Transaction — latitude / longitude bounds
# ---------------------------------------------------------------------------

class TestTransactionGeo:
    def test_valid_lat_lon_accepted(self):
        txn = Transaction(**_valid_transaction(latitude=28.7, longitude=77.1))
        assert txn.latitude == pytest.approx(28.7)

    def test_latitude_too_high_raises(self):
        with pytest.raises(ValidationError):
            Transaction(**_valid_transaction(latitude=91.0))

    def test_latitude_too_low_raises(self):
        with pytest.raises(ValidationError):
            Transaction(**_valid_transaction(latitude=-91.0))

    def test_longitude_too_high_raises(self):
        with pytest.raises(ValidationError):
            Transaction(**_valid_transaction(longitude=181.0))

    def test_longitude_too_low_raises(self):
        with pytest.raises(ValidationError):
            Transaction(**_valid_transaction(longitude=-181.0))

    def test_boundary_values_accepted(self):
        txn = Transaction(**_valid_transaction(latitude=90.0, longitude=180.0))
        assert txn.latitude == 90.0
        assert txn.longitude == 180.0


# ---------------------------------------------------------------------------
# Transaction — enum enforcement
# ---------------------------------------------------------------------------

class TestTransactionEnums:
    def test_valid_device_type_string_coerced(self):
        txn = Transaction(**_valid_transaction(device_type="mobile"))
        assert txn.device_type == DeviceType.mobile

    def test_invalid_device_type_raises(self):
        with pytest.raises(ValidationError):
            Transaction(**_valid_transaction(device_type="laptop"))

    def test_valid_transaction_type_string_coerced(self):
        txn = Transaction(**_valid_transaction(transaction_type="refund"))
        assert txn.transaction_type == TransactionType.refund

    def test_invalid_transaction_type_raises(self):
        with pytest.raises(ValidationError):
            Transaction(**_valid_transaction(transaction_type="crypto"))

    def test_valid_channel_string_coerced(self):
        txn = Transaction(**_valid_transaction(channel="atm"))
        assert txn.channel == Channel.atm

    def test_invalid_channel_raises(self):
        with pytest.raises(ValidationError):
            Transaction(**_valid_transaction(channel="voice"))


# ---------------------------------------------------------------------------
# Transaction — timezone-aware timestamp
# ---------------------------------------------------------------------------

class TestTransactionTimestamp:
    def test_default_timestamp_is_timezone_aware(self):
        txn = Transaction(**_valid_transaction())
        assert txn.timestamp.tzinfo is not None

    def test_explicit_aware_timestamp_accepted(self):
        ts = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        txn = Transaction(**_valid_transaction(timestamp=ts))
        assert txn.timestamp == ts


# ---------------------------------------------------------------------------
# Transaction — serialization / deserialization
# ---------------------------------------------------------------------------

class TestTransactionSerialization:
    def test_model_dump_json_mode(self):
        txn = Transaction(**_valid_transaction())
        data = txn.model_dump(mode="json")
        assert data["amount"] == 500.0
        assert data["device_type"] == "mobile"
        assert "timestamp" in data

    def test_round_trip(self):
        txn = Transaction(**_valid_transaction())
        data = txn.model_dump(mode="json")
        restored = Transaction.model_validate(data)
        assert restored.transaction_id == txn.transaction_id
        assert restored.amount == txn.amount


# ---------------------------------------------------------------------------
# UserProfile — enum and field validation
# ---------------------------------------------------------------------------

class TestUserProfile:
    def test_valid_profile_accepted(self):
        profile = UserProfile(**_valid_user_profile())
        assert profile.account_status == AccountStatus.active

    def test_invalid_travel_frequency_raises(self):
        with pytest.raises(ValidationError):
            TravelProfile(travel_frequency="never")

    def test_valid_travel_frequency_coerced(self):
        tp = TravelProfile(travel_frequency="frequent")
        assert tp.travel_frequency == TravelFrequency.frequent

    def test_negative_avg_amount_raises(self):
        with pytest.raises(ValidationError):
            SpendingProfile(avg_transaction_amount=-1, max_transaction_amount=1000, monthly_spend_limit=5000)

    def test_invalid_hour_in_typical_hours_raises(self):
        with pytest.raises(ValidationError):
            SpendingProfile(
                avg_transaction_amount=500,
                max_transaction_amount=5000,
                monthly_spend_limit=20000,
                typical_transaction_hours=[8, 12, 25],
            )

    def test_valid_hours_accepted(self):
        sp = SpendingProfile(
            avg_transaction_amount=500,
            max_transaction_amount=5000,
            monthly_spend_limit=20000,
            typical_transaction_hours=[8, 12, 18, 23],
        )
        assert 23 in sp.typical_transaction_hours

    def test_adaptive_thresholds_invalid_multiplier_raises(self):
        with pytest.raises(ValidationError):
            AdaptiveThresholds(amount_multiplier=0)

    def test_adaptive_thresholds_invalid_weight_raises(self):
        with pytest.raises(ValidationError):
            AdaptiveThresholds(new_device_risk_weight=1.5)

    def test_account_status_defaults_active(self):
        profile = UserProfile(**_valid_user_profile())
        assert profile.account_status == AccountStatus.active

    def test_account_status_can_be_suspended(self):
        profile = UserProfile(**_valid_user_profile(account_status=AccountStatus.suspended))
        assert profile.account_status == AccountStatus.suspended


# ---------------------------------------------------------------------------
# Evidence models
# ---------------------------------------------------------------------------

class TestEvidenceModels:
    def test_evidence_item_reliability_max(self):
        item = EvidenceItem(
            type="fraud_ring", description="Test", value=1,
            strength=EvidenceStrength.strong, reliability_score=1.0,
        )
        assert item.reliability_score == 1.0

    def test_evidence_item_reliability_out_of_range_raises(self):
        with pytest.raises(ValidationError):
            EvidenceItem(
                type="fraud_ring", description="Test", value=1,
                strength=EvidenceStrength.strong, reliability_score=1.5,
            )

    def test_evidence_item_negative_reliability_raises(self):
        with pytest.raises(ValidationError):
            EvidenceItem(
                type="fraud_ring", description="Test", value=1,
                strength=EvidenceStrength.strong, reliability_score=-0.1,
            )

    def test_investigation_package_score_upper_bound(self):
        with pytest.raises(ValidationError):
            InvestigationPackage(**_valid_investigation_package(geo_velocity_score=101.0))

    def test_investigation_package_score_lower_bound(self):
        with pytest.raises(ValidationError):
            InvestigationPackage(**_valid_investigation_package(geo_velocity_score=-1.0))

    def test_investigation_package_similarity_upper_bound(self):
        with pytest.raises(ValidationError):
            InvestigationPackage(**_valid_investigation_package(pattern_similarity=1.1))

    def test_investigation_package_trust_score_upper_bound(self):
        with pytest.raises(ValidationError):
            InvestigationPackage(**_valid_investigation_package(device_trust_score=1.1))

    def test_investigation_package_pre_risk_upper_bound(self):
        with pytest.raises(ValidationError):
            InvestigationPackage(**_valid_investigation_package(pre_risk_score=101.0))

    def test_investigation_package_valid_defaults(self):
        pkg = InvestigationPackage(**_valid_investigation_package())
        assert pkg.device_trust_score == 0.5
        assert pkg.merchant_reputation_score == 0.5
        assert pkg.geo_velocity_score == 0.0


# ---------------------------------------------------------------------------
# FraudDecision models — score bounds
# ---------------------------------------------------------------------------

class TestFraudDecisionModels:
    def test_agent_risk_confidence_max_one(self):
        with pytest.raises(ValidationError):
            AgentRisk(agent="behavior", risk_score=50.0, confidence=1.5)

    def test_agent_risk_risk_score_max_100(self):
        with pytest.raises(ValidationError):
            AgentRisk(agent="behavior", risk_score=101.0, confidence=0.5)

    def test_consensus_result_agreement_score_max_100(self):
        with pytest.raises(ValidationError):
            ConsensusResult(risk_score=50.0, agreement_score=101.0, confidence_score=80.0)

    def test_consensus_result_confidence_score_max_100(self):
        with pytest.raises(ValidationError):
            ConsensusResult(risk_score=50.0, agreement_score=80.0, confidence_score=101.0)

    def test_explainability_risk_score_max_100(self):
        with pytest.raises(ValidationError):
            ExplainabilityResult(
                risk_score=101.0, confidence_score=80.0,
                contributing_factors=[], evidence_summary="",
                matched_fraud_pattern=None, human_explanation="ok",
                analyst_explanation="ok", executive_explanation="ok",
            )

    def test_explainability_confidence_score_max_100(self):
        with pytest.raises(ValidationError):
            ExplainabilityResult(
                risk_score=50.0, confidence_score=101.0,
                contributing_factors=[], evidence_summary="",
                matched_fraud_pattern=None, human_explanation="ok",
                analyst_explanation="ok", executive_explanation="ok",
            )

    def test_counterfactual_contribution_score_max_100(self):
        with pytest.raises(ValidationError):
            CounterfactualResult(primary_contributor="amount", contribution_score=101.0)

    def test_analyst_recommendation_confidence_max_one(self):
        with pytest.raises(ValidationError):
            AnalystRecommendation(
                recommended_action=FraudDecision.approved,
                reason="ok", confidence=1.5,
            )

    def test_fraud_detection_result_pre_risk_max_100(self):
        consensus = ConsensusResult(risk_score=30.0, agreement_score=80.0, confidence_score=70.0)
        explainability = ExplainabilityResult(
            risk_score=30.0, confidence_score=70.0,
            contributing_factors=[], evidence_summary="",
            matched_fraud_pattern=None, human_explanation="ok",
            analyst_explanation="ok", executive_explanation="ok",
        )
        recommendation = AnalystRecommendation(
            recommended_action=FraudDecision.approved, reason="ok", confidence=0.9,
        )
        with pytest.raises(ValidationError):
            FraudDetectionResult(
                transaction_id="txn_001", user_id="usr_001",
                pre_risk_score=101.0,           # <-- invalid
                routed_to_deep_investigation=False,
                consensus=consensus,
                explainability=explainability,
                analyst_recommendation=recommendation,
                final_decision=FraudDecision.approved,
            )

    def test_fraud_detection_result_timestamp_timezone_aware(self):
        consensus = ConsensusResult(risk_score=30.0, agreement_score=80.0, confidence_score=70.0)
        explainability = ExplainabilityResult(
            risk_score=30.0, confidence_score=70.0,
            contributing_factors=[], evidence_summary="",
            matched_fraud_pattern=None, human_explanation="ok",
            analyst_explanation="ok", executive_explanation="ok",
        )
        recommendation = AnalystRecommendation(
            recommended_action=FraudDecision.approved, reason="ok", confidence=0.9,
        )
        result = FraudDetectionResult(
            transaction_id="txn_001", user_id="usr_001",
            pre_risk_score=30.0,
            routed_to_deep_investigation=False,
            consensus=consensus,
            explainability=explainability,
            analyst_recommendation=recommendation,
            final_decision=FraudDecision.approved,
        )
        assert result.timestamp.tzinfo is not None
