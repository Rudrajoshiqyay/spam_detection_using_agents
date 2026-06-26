# FraudGuard AI — Model Monitoring Plan
**Date:** 2026-06-23 | **Sprint:** Remediation Sprint 1

---

## Problem Statement

The current `/metrics/evaluation` endpoint always returns 100% accuracy because it uses `expected_label` as both ground truth and prediction. This was fixed this sprint to return honest ground truth composition. True live-detection metrics require pipeline predictions to be stored alongside decisions.

---

## Monitoring Architecture

### Step 1: Store Pipeline Predictions in Ground Truth DB

Add `pipeline_decision` column to ground_truth DB:

```sql
ALTER TABLE ground_truth ADD COLUMN pipeline_decision TEXT;
ALTER TABLE ground_truth ADD COLUMN pipeline_risk_score REAL;
ALTER TABLE ground_truth ADD COLUMN pipeline_confidence REAL;
ALTER TABLE ground_truth ADD COLUMN pipeline_timestamp TEXT;
```

When `/detect` is called for a transaction that has a ground truth record:
```python
# In detect_fraud endpoint:
await update_ground_truth_prediction(
    transaction_id=txn.transaction_id,
    pipeline_decision=result.final_decision.value,
    pipeline_risk_score=result.consensus.risk_score,
    pipeline_confidence=result.consensus.confidence_score,
)
```

### Step 2: Real Metrics Calculation

Once `pipeline_decision` is stored:

```python
def compute_detection_metrics(records: List[GroundTruthRecord]) -> dict:
    # Only score records that have both ground truth AND pipeline prediction
    evaluable = [r for r in records if r.pipeline_decision is not None]

    tp = sum(1 for r in evaluable if r.is_fraud and r.pipeline_decision in ("BLOCKED", "ESCALATED"))
    fp = sum(1 for r in evaluable if not r.is_fraud and r.pipeline_decision in ("BLOCKED", "ESCALATED"))
    fn = sum(1 for r in evaluable if r.is_fraud and r.pipeline_decision == "APPROVED")
    tn = sum(1 for r in evaluable if not r.is_fraud and r.pipeline_decision == "APPROVED")

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "total_evaluated": len(evaluable),
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "true_negatives": tn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1, 4),
        "false_positive_rate": round(fp / (fp + tn), 4) if (fp + tn) > 0 else 0.0,
        "false_negative_rate": round(fn / (fn + tp), 4) if (fn + tp) > 0 else 0.0,
    }
```

---

## Metric Definitions and Alert Thresholds

### Core Detection Metrics

| Metric | Formula | Green | Yellow | Red |
|---|---|---|---|---|
| Precision | TP/(TP+FP) | ≥ 0.80 | 0.70–0.79 | < 0.70 |
| Recall | TP/(TP+FN) | ≥ 0.75 | 0.60–0.74 | < 0.60 |
| F1 Score | 2×P×R/(P+R) | ≥ 0.77 | 0.65–0.76 | < 0.65 |
| False Positive Rate | FP/(FP+TN) | ≤ 0.05 | 0.05–0.10 | > 0.10 |
| False Negative Rate | FN/(FN+TP) | ≤ 0.20 | 0.20–0.35 | > 0.35 |

### Operational Metrics

| Metric | Green | Yellow | Red |
|---|---|---|---|
| Auto-Approve Rate | 40–60% | 20–39% or 61–80% | < 20% or > 80% |
| Average Agent Agreement Score | ≥ 70 | 50–69 | < 50 |
| Agent Failure Rate (defaulted to 50) | ≤ 5% | 5–15% | > 15% |
| Daily Fraud Rate | 5–15% | 2–4% or 16–25% | < 2% or > 25% |
| Avg Stage 1 Latency | < 20ms | 20–50ms | > 50ms |
| Avg Stage 2 Latency | < 1.5s | 1.5–3s | > 3s |

---

## Drift Detection Definitions

### PSI (Population Stability Index)

Run weekly using `app/simulation/label_leakage_detector.py` infrastructure:

```python
# Compare current week vs 4-week rolling baseline
psi_persona = compute_psi(current_persona_dist, baseline_persona_dist)
psi_amount = compute_psi(current_amount_hist, baseline_amount_hist)
psi_fraud_rate = compute_psi(current_fraud_by_type, baseline_fraud_by_type)

def compute_psi(actual: dict, expected: dict) -> float:
    psi = 0.0
    for key in expected:
        a = actual.get(key, 0.001)
        e = expected.get(key, 0.001)
        psi += (a - e) * math.log(a / e)
    return round(psi, 4)
```

| PSI Range | Status | Action |
|---|---|---|
| < 0.10 | Stable | Monitor |
| 0.10–0.25 | Moderate drift | Investigate |
| > 0.25 | Significant drift | Retrain/alert |

### KL Divergence Alert
- Run monthly on full population distribution
- Alert if KL(current || baseline) > 0.05 nats

---

## Monitoring Schedule

| Metric Set | Frequency | Owner | Alert Channel |
|---|---|---|---|
| Precision/Recall/F1 | Daily | ML Team | PagerDuty P2 |
| False Positive Rate | Daily | Fraud Ops | PagerDuty P1 if > 0.10 |
| Agent Failure Rate | Hourly | DevOps | Slack #fraud-alerts |
| Auto-Approve Rate | Hourly | Fraud Ops | Slack #fraud-alerts |
| PSI — Persona Distribution | Weekly | ML Team | Email |
| PSI — Fraud Type Distribution | Weekly | ML Team | Email |
| KL Divergence | Monthly | ML Team | Report |
| Latency percentiles (p50/p95/p99) | Continuous | DevOps | PagerDuty P1 |

---

## Dashboard Requirements (Not Built — Reference Only)

| Panel | Data Source | Refresh |
|---|---|---|
| Fraud Rate Trend (30d) | ground_truth.db | 1h |
| Precision/Recall/F1 (7d rolling) | Detection results | 1h |
| Auto-Approve vs Escalate ratio | Pipeline metrics | 5m |
| Agent Agreement Distribution | consensus_result | 5m |
| Agent Failure Rate by Agent | Defaulted agents log | 5m |
| Fraud Type Breakdown | ground_truth.db | 1h |
| PSI Trend (12 weeks) | Weekly PSI snapshots | Weekly |
| Latency p50/p95/p99 | Pipeline timing | 1m |

---

## Current State vs Target State

| Metric | Current State | Target State | Gap |
|---|---|---|---|
| Accuracy endpoint | Always 100% (BUG) | Honest composition | ✅ FIXED |
| Precision | Not computed | Computed daily | Pipeline prediction storage needed |
| Recall | Not computed | Computed daily | Pipeline prediction storage needed |
| F1 | Not computed | Computed daily | Pipeline prediction storage needed |
| Drift (PSI) | Not computed | Weekly report | Infrastructure needed |
| Agent failure tracking | Not tracked | Hourly alert | Logger changes needed |
| Latency monitoring | Not tracked | p95 < 1.5s | APM tool needed |

---

**Model Monitoring Score Estimate After Implementation: 68 / 100** (up from 22)
**Current score after /metrics fix only: 35 / 100**
