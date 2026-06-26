# Phase 11 — Regression Testing Report
**Date:** 2026-06-23 | **Auditor:** QA Agent | **Mode:** READ-ONLY

---

## 11.1 Regression Testing Framework

**Method:** Code-analysis-based regression audit (no prior version baseline available)
**Baseline:** Implied by naming conventions, constants, and docstrings in source
**Scope:** Identify regression risks from architectural decisions, silent failures, and hardcoded values

---

## 11.2 Baseline Assumptions (Derived from Code)

| Component | Current State | Version Indicator |
|---|---|---|
| Fast Screening | 7 components, weights sum to 1.0 | Stable |
| Consensus Formula | blended=0.70+0.20+0.10 | Stable |
| Agent Weights | behavior=0.25, device=0.20, geo=0.20, merchant=0.15, graph=0.20 | Stable |
| Fraud threshold | pre_risk < 35 → auto-approve | Assumed stable |
| LangGraph nodes | 12 nodes documented | May have been added to |
| Ground truth schema | ground_truth.db with attack_version field | Version-aware |

---

## 11.3 Silent Failure Regression Risks

### Risk 1 — Feature Store Silent Failure
```python
async def _update_feature_store(state):
    try:
        ...
    except Exception:
        pass  # completely silent
```

If feature store update regresses (API change, schema change, connection timeout):
- No error logged
- No metric incremented
- No alert triggered
- Behavioral data becomes stale silently

**Regression Impact:** Behavioral agent scores degrade to defaults without detection.

### Risk 2 — Auto-Approve Hardcoded Values
```python
ConsensusResult(
    agreement_score=100.0,    # hardcoded
    confidence_score=85.0,    # hardcoded
)
```

If the auto-approve threshold logic is refactored, these hardcoded values will not reflect the new confidence model. Any consumer of these fields will see stale values without an error.

### Risk 3 — Agent Fallback to 50.0
```python
float(behavior_risk.get("risk_score", 50))
```

If any agent's return schema changes (field renamed from `risk_score` to `score`), the consensus engine silently falls back to 50.0 for that agent — no error, no log.

---

## 11.4 Hardcoded Regression Points

| Location | Hardcoded Value | Regression Risk |
|---|---|---|
| consensus_engine.py | weights: 0.70, 0.20, 0.10 | If formula changes, no validation |
| fast_screening.py | pre_risk threshold 35.0 | Any threshold change would be silent |
| main.py:873 | `min(req.num_generations, 4)` | Cap not parameterized |
| fraud_evolution_agent.py | `_GEN_DIFFICULTY` dict (4 entries) | Gen 5+ behavior undefined |
| adversarial_agent.py | mutation difficulty scores | Not configurable |
| dataset_validator.py | minimum_score 60.0 | Not in config |
| label_leakage_detector.py | LIFT_THRESHOLD=3.0 | Not in config |

**Finding:** Core thresholds are scattered across modules with no central configuration file. A regression in any one threshold requires tracking down the specific file.

---

## 11.5 API Contract Regression

### /detect Endpoint
```python
@app.post("/detect")
async def detect_fraud(request: FraudDetectionRequest) -> FraudDetectionResponse:
```

**Breaking change risks:**
- If `FraudDetectionRequest` schema adds required fields → old clients break
- If `FraudDetectionResponse` removes fields → downstream consumers break
- CORS `allow_origins=["*"]` → any origin can call the API (security regression risk)

### /metrics/evaluation Endpoint (CRITICAL BUG)
```python
"accuracy": (correct / total) if total > 0 else 0
# where:
# correct = (result.prediction == result.expected_label)  ← uses expected_label as "prediction"
```

This means `/metrics/evaluation` always reports 100% accuracy because `result.prediction` IS the `expected_label`. This is not a new regression — it was always wrong — but it means any version that relied on this metric for regression comparison would see 100% → 100%, masking any real detection regression.

---

## 11.6 Database Schema Regression

### ground_truth.db Schema
```sql
CREATE TABLE IF NOT EXISTS ground_truth (
    transaction_id TEXT PRIMARY KEY,
    user_id TEXT,
    is_fraud INTEGER,
    fraud_type TEXT,
    attack_version TEXT,       -- version tracking field
    campaign_generation INTEGER  -- evolution generation tracking
    ...
)
```

`attack_version` field suggests version tracking is intended but the field is never populated from simulation code (always NULL or default).

**Regression Detection Capability: PARTIAL** — Schema supports it but population pipeline doesn't write version data.

---

## 11.7 LangGraph Node Regression

### Documented: 12 Nodes
```
feature_retrieval → fast_screening → [auto_approve | pre_agent_analysis →
build_evidence → parallel_agents → consensus → investigation →
explainability → analyst → storytelling → final_decision]
```

**Regression Risk Assessment:**

| Node | Risk If Removed | Detection Method |
|---|---|---|
| explainability | Explanations lost silently | Check output fields |
| storytelling | Narratives empty | Check narrative field |
| analyst | Analyst summary empty | Check summary field |
| auto_approve | All transactions escalated | Check approve rate |
| consensus | Undefined behavior | consensus_result is None |

No automated node presence test exists.

---

## 11.8 Performance Regression Thresholds

| Metric | Target | Regression Trigger |
|---|---|---|
| Stage 1 latency | < 20ms | > 25ms (25% degradation) |
| Stage 2 latency | < 1.5s | > 2.0s (33% degradation) |
| Auto-approve rate | ~40–60% | < 20% or > 80% |
| Memory per 1000 users | < 50MB | > 100MB |

**Status: No automated regression tests exist for any of these metrics.**

---

## 11.9 Regression Test Coverage

| System Layer | Coverage | Risk |
|---|---|---|
| Fast screening math | 0% automated | HIGH |
| Consensus formula | 0% automated | HIGH |
| LangGraph node order | 0% automated | HIGH |
| Ground truth write | 0% automated | MEDIUM |
| Population weights | 0% automated | HIGH |
| API schema | 0% automated | MEDIUM |
| Performance metrics | 0% automated | HIGH |

**Total estimated automated regression coverage: 0%**

---

## CRITICAL FINDINGS
1. `/metrics/evaluation` always returns 100% accuracy — masks all real detection regressions
2. Feature store failures are fully silent — behavioral score regression invisible
3. No automated regression test suite exists anywhere in the codebase

## WARNINGS
1. Core thresholds hardcoded across 7 files with no central config
2. Agent score fallback to 50.0 is silent — agent response schema changes go undetected
3. `attack_version` field defined but never populated — version tracking non-functional

---

**Regression Safety Score: 38 / 100**
