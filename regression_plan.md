# FraudGuard AI — Regression Protection Plan
**Date:** 2026-06-23 | **Sprint:** Remediation Sprint 1

---

## Current State

**Automated regression coverage: 0%** (no test suite exists)
**Manual regression coverage: 0%** (no baseline snapshots)

**Baseline created this sprint:** `testing/regression_baselines/baseline_metrics.md`

---

## Regression Test Structure

### Layer 1 — Unit Tests (Priority: CRITICAL)

Location: `tests/unit/`

#### Test: Consensus Engine Math
```
tests/unit/test_consensus_engine.py

test_all_agents_fail_agreement_zero:
    Given: all 5 agents return empty dict (no risk_score key)
    When: compute_consensus() called
    Then: result.agreement_score == 0.0
          result.confidence_score == 0.0

test_partial_agent_failure_penalised:
    Given: 2 agents return scores, 3 agents return empty dict
    When: compute_consensus() called
    Then: result.agreement_score <= (base_agreement - 30.0)

test_consensus_formula_exact:
    Given: scores=[90,85,88,82,87], pre_risk=75, signal=80
    When: compute_consensus()
    Then: risk_score == 83.76 ± 0.5

test_agreement_score_formula:
    Given: scores=[90,85,88,82,87]
    When: std_dev computed
    Then: agreement_score == 95.9 ± 0.1
```

#### Test: Fast Screening Threshold
```
tests/unit/test_fast_screening.py

test_normal_domestic_below_threshold:
    Given: known device, home city, avg amount, business hours
    When: compute_pre_risk_score()
    Then: pre_risk_score < 35

test_ato_above_threshold:
    Given: new device, intl location, 10× avg amount
    When: compute_pre_risk_score()
    Then: pre_risk_score >= 35

test_auto_approve_path_produces_graduated_confidence:
    Given: pre_risk = 12 → auto_approve fires
    When: node_auto_approve()
    Then: consensus.agreement_score < 100
          consensus.confidence_score < 90
          consensus.agreement_score > 50
```

#### Test: Campaign Ground Truth Labels
```
tests/unit/test_campaign_labels.py

test_cross_border_fraud_type_correct:
    When: generate_cross_border_campaign()
    Then: all txn["fraud_type"] == "cross_border_fraud"
          no txn["fraud_type"] == "account_takeover"

test_card_testing_no_unknown_city:
    When: generate_card_testing_campaign()
    Then: no txn["location_city"] == "Unknown"
          all txn["location_city"] in VALID_DOMESTIC_CITIES

test_money_mule_no_double_injection:
    When: generate_money_mule_campaign(mule_users=[u1, u2, u3])
    Then: len(transactions) == 5  # 1 inject + 2 layers + 1 cashout
          u1_txns = [t for t in txns if t["user_id"] == u1_id]
          len(u1_txns) == 1
          u1_txns[0]["phase"] == "inject"
```

#### Test: Ring Graph Structure
```
tests/unit/test_ring_graphs.py

test_ip_cluster_ring_ip_consistency:
    When: generate_ip_cluster_ring(size=5)
    Then: for each user_id in ring["members"]:
              graph_ip = [e["target"] for e in ring["edges"] if e["source"] == user_id][0]
              txn_ip = [t["ip_address"] for t in ring["transactions"] if t["user_id"] == user_id][0]
              assert graph_ip == txn_ip

test_ip_cluster_ring_public_ip:
    When: generate_ip_cluster_ring()
    Then: all IPs in ring["shared_ips"] start with "103."
          not any IP starts with "192.168."

test_multi_vector_ring_has_graph:
    When: generate_multi_vector_ring(size=8)
    Then: ring["node_count"] >= 10
          ring["edge_count"] >= 8
          len(ring["edges"]) >= 8
```

#### Test: Population Weights
```
tests/unit/test_population_weights.py

test_population_weights_identical_to_persona_weights:
    from app.simulation.population_simulator import POPULATION_WEIGHTS
    from app.simulation.persona_agent import _PERSONA_WEIGHTS
    assert POPULATION_WEIGHTS == _PERSONA_WEIGHTS

test_population_weights_sum_to_one:
    from app.simulation.population_simulator import POPULATION_WEIGHTS
    assert abs(sum(POPULATION_WEIGHTS.values()) - 1.0) < 0.001
```

#### Test: Metrics Endpoint
```
tests/unit/test_metrics_endpoint.py

test_evaluation_does_not_return_100_percent_accuracy:
    response = client.get("/metrics/evaluation")
    data = response.json()
    assert "accuracy" not in data or data.get("accuracy") != 1.0
    assert "dataset_composition" in data
    assert "note" in data
```

---

### Layer 2 — Integration Tests (Priority: HIGH)

Location: `tests/integration/`

#### Test: Full Pipeline Smoke Test
```
test_pipeline_ato_escalates:
    Given: ATO transaction (new device, intl, large amount)
    When: run_fraud_detection(txn, profile)
    Then: result.routed_to_deep_investigation == True
          result.final_decision in (BLOCKED, ESCALATED)

test_pipeline_normal_auto_approves:
    Given: Normal domestic transaction (known device, home city, avg amount)
    When: run_fraud_detection(txn, profile)
    Then: result.final_decision == APPROVED
          result.routed_to_deep_investigation == False

test_pipeline_feature_store_failure_logs_warning:
    Given: Feature store raises ConnectionError
    When: pipeline completes
    Then: WARNING log exists containing "Feature store update failed"
          pipeline result is still valid (no exception propagated)
```

---

### Layer 3 — Regression Snapshot Tests (Priority: MEDIUM)

Location: `tests/regression/`

Store expected outputs from known inputs. After each release:
1. Run all snapshot tests
2. Any change in output = regression flag
3. Review: intentional change → update snapshot; unintentional → investigate

#### Snapshot: Consensus Formula
```
Input: behavior=90, device=85, geo=88, merchant=82, graph=87, pre_risk=75, signal=80
Expected output (stored in tests/regression/snapshots/consensus_001.json):
{
    "risk_score": 83.76,
    "agreement_score": 95.9,
    "confidence_score": [range based on evidence reliability]
}
```

#### Snapshot: Fast Screening — Known Cases
```
Input: known device + home city + avg amount + business hours
Expected: pre_risk in range [3, 15]

Input: new device + intl location + 10× amount + 3am
Expected: pre_risk in range [70, 90]
```

---

## Regression Protection Schedule

| Test Layer | When to Run | Pass Criteria |
|---|---|---|
| Unit tests | Every commit | 100% pass |
| Integration tests | Every PR | 100% pass |
| Snapshot tests | Every release | No unexpected changes |
| Manual golden dataset | Monthly | ≥ 7/11 golden cases pass |

---

## Priority Implementation Order

1. **Week 1:** Write 10 unit tests covering consensus math + campaign labels (highest ROI)
2. **Week 2:** Write ring graph unit tests + population weight test
3. **Week 3:** Integration smoke test for pipeline
4. **Week 4:** Snapshot tests for regression

---

**Regression Safety Score Estimate After Test Suite: 72 / 100** (up from 38)
**Current score after baselines only: 52 / 100** (baselines created, no automated tests yet)
