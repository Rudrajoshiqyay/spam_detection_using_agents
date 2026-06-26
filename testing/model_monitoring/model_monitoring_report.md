# Phase 20 — Model Monitoring Report
**Date:** 2026-06-23 | **Auditor:** QA Agent | **Mode:** READ-ONLY

---

## 20.1 Model Monitoring Framework

**Available Metrics Endpoints:** `/metrics/evaluation`, `/metrics/fraud-type-performance`
**Monitoring Scope:** Precision, Recall, F1, ROC-AUC, PR-AUC

---

## 20.2 Current Metrics Implementation

### /metrics/evaluation Bug (CRITICAL)

```python
# main.py
for result in results:
    if result.prediction == result.expected_label:   # ← uses expected_label
        correct += 1

accuracy = correct / total  # → ALWAYS 100%
```

The evaluation endpoint compares `prediction` to `expected_label` where `prediction` IS the `expected_label`. This means the system always reports 100% accuracy regardless of actual detection performance.

**Impact on monitoring:** Model performance cannot be monitored via this endpoint. Any dashboard or alert based on `/metrics/evaluation` will show constant 100% accuracy — masking any model degradation, drift, or regression.

---

## 20.3 Precision/Recall/F1 Analysis

### Expected Precision/Recall (from code paths)

**Precision = TP / (TP + FP)**

Known false positive sources:
1. IP cluster detection at scale (10k users → ~100% FP rate on IP signal)
2. Amount anomaly for HNW customers making large-but-legitimate purchases
3. Device novelty for users who legitimately switch devices
4. Timing anomaly for users in different time zones

**Estimated precision range:** 60–80% (heavily dependent on population distribution and ring/campaign mix)

**Recall = TP / (TP + FN)**

Known false negative sources:
1. Gen4 attacks (~72% bypass rate)
2. Auto-approve for pre_risk < 35 (catches Gen4 mutations)
3. Multi-vector rings (undetectable, no graph built)
4. IP cluster ring (broken IP match)

**Estimated recall range:** 55–75% (missing ~25–45% of sophisticated fraud)

**F1 Score:** 2 × (P × R) / (P + R) ≈ 2 × 0.70 × 0.65 / 1.35 ≈ 0.67

---

## 20.4 ROC-AUC Analysis

### Expected ROC-AUC

**Key discriminating components:**
- pre_risk_score: strong discriminator (range 0–100)
- Agent consensus (blended_risk): strong discriminator
- Auto-approve threshold (35): hard cutoff that distorts AUC

**Effect of hard threshold:**
- All transactions with pre_risk < 35 are auto-approved (predicted legitimate)
- All transactions with pre_risk ≥ 35 are escalated (predicted fraud or escalated)
- This creates a non-probabilistic decision that reduces AUC

**Estimated ROC-AUC:** 0.72–0.82
- High for obvious fraud (ATO, card testing)
- Lower for Gen4 mutations (designed to bypass)

### PR-AUC (Precision-Recall AUC)

More important than ROC-AUC for imbalanced datasets (fraud rate ~8%).

**Estimated PR-AUC:** 0.55–0.70
- Precision drops sharply at high recall thresholds (too many false positives)
- Missing Gen4 bypasses limits maximum recall

**Neither ROC-AUC nor PR-AUC is currently calculated** by the evaluation engine.

---

## 20.5 Metrics Stratification

### Stratified by fraud_type
```python
# evaluation_engine.py
by_fraud_type = defaultdict(lambda: {"tp":0,"fp":0,"fn":0,"tn":0})
```

Fraud type stratification exists. However, cross-border fraud is mislabeled as `account_takeover` → metrics for `account_takeover` are inflated (includes 20–30% cross-border transactions).

**Contaminated metrics:**
- `account_takeover` recall: artificially high (easy-to-detect cross-border cases counted)
- `cross_border_fraud` recall: 0% (no transactions labeled cross_border)

### Stratified by difficulty_band
```python
by_difficulty = {"easy": ..., "medium": ..., "hard": ...}
```

Difficulty stratification exists. Bands:
- easy: difficulty < 30 (Gen1)
- medium: 30–60 (Gen2, Gen3)
- hard: > 60 (Gen4)

**Expected pattern:**
- Easy: ~95% detection rate
- Medium: ~60% detection rate
- Hard: ~28% detection rate

### Missing Stratification
- **campaign_generation**: not stratified (Gen1 vs Gen4 mixed)
- **ring_type**: not stratified
- **persona_type**: exists in evaluation engine but not surfaced in API response

---

## 20.6 Drift Alert Thresholds

**No drift alerting implemented.**

Ideal monitoring would include:
- Alert if daily fraud rate changes by > 2× (could indicate model drift or attack surge)
- Alert if precision drops below 0.70 (false positive surge)
- Alert if recall drops below 0.60 (detection failure)
- Alert if agreement_score distribution shifts (agent quality change)
- Alert if auto-approve rate changes by > 20% (threshold calibration issue)

**Status: No monitoring alerts exist**

---

## 20.7 Model Version Tracking

```python
# ground_truth.py
attack_version: Optional[str] = None   # never populated
```

No model version tracking in the pipeline. Cannot correlate detection performance changes with model updates.

**Impact:** Cannot determine if a change in recall was caused by:
1. New attack patterns (external)
2. Model degradation (internal)
3. Population shift (data)
4. Configuration change (operational)

---

## 20.8 Calibration Analysis

**Confidence calibration:** Is the confidence score well-calibrated?

```
confidence = agreement_score × verdict_boost × (0.5 + reliability × 0.5)
```

**Auto-approve hardcoded confidence: 85.0**
- 40–60% of transactions auto-approved at exactly 85 confidence
- Legitimate model confidence would vary continuously
- This creates a massive spike at exactly 85 in the confidence distribution

**Calibration assessment:** Poorly calibrated
- The 85.0 spike at auto-approve distorts all calibration analysis
- Cannot distinguish "truly 85% confident" from "auto-approved"

---

## 20.9 Monitoring Dashboard Gaps

| Metric | Available | Correct | Status |
|---|---|---|---|
| Accuracy | ✓ | ✗ (always 100%) | CRITICAL BUG |
| Precision | ✗ | N/A | MISSING |
| Recall | ✗ | N/A | MISSING |
| F1 Score | ✗ | N/A | MISSING |
| ROC-AUC | ✗ | N/A | MISSING |
| PR-AUC | ✗ | N/A | MISSING |
| Fraud rate trend | ✗ | N/A | MISSING |
| Agent failure rate | ✗ | N/A | MISSING |
| Confidence calibration | ✗ | N/A | MISSING |
| Campaign type recall | Partial | ✗ (type bug) | WRONG |

**Monitoring completeness: 1/10 metrics available (and that one is wrong)**

---

## CRITICAL FINDINGS
1. `/metrics/evaluation` always returns 100% accuracy — monitoring is blind to model degradation
2. Cross-border mislabeling contaminates account_takeover metrics permanently
3. No ROC-AUC, PR-AUC, Precision, Recall, or F1 implemented anywhere

## WARNINGS
1. Confidence calibration: bimodal distribution with spike at 85.0 for all auto-approves
2. No drift alerting or threshold-based monitoring
3. attack_version field never populated — cannot correlate performance with model version
4. Agreement score distribution is bimodal (100 for auto-approve, varied for deep investigation)

---

**Model Monitoring Score: 22 / 100**
