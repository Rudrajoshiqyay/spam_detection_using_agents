# Phase 13 — Consensus Engine Testing Report
**Date:** 2026-06-23 | **Auditor:** QA Agent | **Mode:** READ-ONLY

---

## 13.1 Consensus Engine Overview

**File:** `app/services/consensus_engine.py`
**Formula:**
```
blended_risk = weighted_agents × 0.70 + pre_risk × 0.20 + signal_risk × 0.10
agreement_score = max(0.0, 100.0 − std_dev(scores) × 1.5)
confidence = agreement × verdict_boost × (0.5 + reliability × 0.5)
```

**Agent Weights:** behavior=0.25, device=0.20, geo=0.20, merchant=0.15, graph=0.20

---

## 13.2 Weighted Risk Calculation Tests

### Test C1: All Agents Agree (High Fraud)

| Agent | Weight | Score |
|---|---|---|
| behavior | 0.25 | 90 |
| device | 0.20 | 85 |
| geo | 0.20 | 88 |
| merchant | 0.15 | 82 |
| graph | 0.20 | 87 |

```
weighted_agents = 90×0.25 + 85×0.20 + 88×0.20 + 82×0.15 + 87×0.20
               = 22.5 + 17.0 + 17.6 + 12.3 + 17.4 = 86.8

pre_risk = 75 (example, above threshold)
signal_risk = 80 (example)

blended_risk = 86.8×0.70 + 75×0.20 + 80×0.10
             = 60.76 + 15.0 + 8.0 = 83.76

std_dev([90,85,88,82,87]) = √(Σ(xi−μ)²/n) where μ=86.4
  deviations: 3.6, −1.4, 1.6, −4.4, 0.6
  squared: 12.96, 1.96, 2.56, 19.36, 0.36
  variance = 37.2/5 = 7.44
  std_dev = 2.73

agreement_score = max(0, 100 − 2.73×1.5) = max(0, 95.9) = 95.9
```

**Expected verdict: FRAUD with high confidence** ✓

---

### Test C2: Disagreeing Agents

| Agent | Weight | Score |
|---|---|---|
| behavior | 0.25 | 85 |
| device | 0.20 | 20 |
| geo | 0.20 | 75 |
| merchant | 0.15 | 15 |
| graph | 0.20 | 80 |

```
weighted_agents = 85×0.25 + 20×0.20 + 75×0.20 + 15×0.15 + 80×0.20
               = 21.25 + 4.0 + 15.0 + 2.25 + 16.0 = 58.5

std_dev([85,20,75,15,80]):
  μ = 55.0
  deviations: 30, −35, 20, −40, 25
  squared: 900, 1225, 400, 1600, 625
  variance = 4750/5 = 950
  std_dev = 30.82

agreement_score = max(0, 100 − 30.82×1.5) = max(0, 53.77) = 53.77
```

**Result: blended_risk=58.5, agreement=53.77 → escalate for human review**
**Assessment:** Formula correctly reflects agent disagreement ✓

---

### Test C3: Agent Fallback to Default 50

All agents fail to return risk_score → each defaults to 50.0:
```
weighted_agents = 50×(0.25+0.20+0.20+0.15+0.20) = 50×1.0 = 50.0
std_dev([50,50,50,50,50]) = 0
agreement_score = max(0, 100−0×1.5) = 100
```

**Result: blended_risk=50, agreement=100 → MEDIUM risk with PERFECT agreement**

**CRITICAL FLAW:** When ALL agents fail, the system reports PERFECT agreement at 50% risk.
- A failing system appears to be unanimously confident at medium risk
- This is more dangerous than a random distribution
- A transaction that should be BLOCKED could be approved at exactly 50%

---

### Test C4: Single Agent Failure

Behavior agent fails → defaults to 50; others return fraud scores:
```
behavior: 50 (default)
device: 90
geo: 88
merchant: 85
graph: 87

weighted_agents = 50×0.25 + 90×0.20 + 88×0.20 + 85×0.15 + 87×0.20
               = 12.5 + 18.0 + 17.6 + 12.75 + 17.4 = 78.25

std_dev([50,90,88,85,87]):
  μ = 80
  std_dev = 15.25

agreement_score = max(0, 100 − 15.25×1.5) = max(0, 77.1) = 77.1
```

**Issue:** Behavior agent failure anchors blended_risk DOWN toward 50, creating false negatives.
Behavior has 0.25 weight — if it fails, fraud score drops from ~87 to ~78.
**Assessment: Agent fallback bias — failure hides fraud signals**

---

## 13.3 Agreement Score Tests

### Agreement Score Range Tests

| Scenario | Std Dev | Agreement |
|---|---|---|
| Perfect consensus | 0.0 | 100.0 |
| Low disagreement | 5.0 | 92.5 |
| Moderate disagreement | 20.0 | 70.0 |
| High disagreement | 40.0 | 40.0 |
| Extreme disagreement | 66.7 | 0.0 (clamped) |

**Maximum possible std_dev** (one agent=100, rest=0): std_dev ≈ 40 → agreement = 40
**Agreement never reaches 0** unless std_dev > 66.7 (impossible with 5 agents, scores 0–100)

---

## 13.4 Confidence Score Tests

```python
confidence = agreement_score × verdict_boost × (0.5 + reliability × 0.5)
```

Where `verdict_boost`:
- FRAUD verdict: 1.0 (no boost)
- LEGITIMATE: 0.95 (slight penalty for legitimate verdicts?)
- ESCALATE: 0.90 (lowest confidence on escalation)

**Test: High agreement, fraud verdict, reliability=1.0:**
```
confidence = 95.9 × 1.0 × (0.5 + 1.0 × 0.5) = 95.9 × 1.0 × 1.0 = 95.9
```

**Test: High agreement, legitimate verdict, reliability=0.5:**
```
confidence = 95.9 × 0.95 × (0.5 + 0.5 × 0.5) = 95.9 × 0.95 × 0.75 = 68.4
```

**Assessment:** Verdict boost structure makes legitimate verdicts systematically less confident than fraud verdicts. This biases toward fraud classification under uncertainty.

---

## 13.5 Auto-Approve Consensus Values

```python
# fraud_pipeline.py node_auto_approve:
ConsensusResult(
    agreement_score=100.0,
    confidence_score=85.0,
)
```

Auto-approved transactions are assigned:
- agreement_score = 100.0 (maximum possible)
- confidence_score = 85.0 (hardcoded)

These are FAKE values — auto-approve happens because pre_risk < 35, not because agents agreed.
Any analytics on `agreement_score` distribution would show a bimodal distribution:
- Group A: real agent agreements (varied)
- Group B: auto-approves (always exactly 100.0)

This pollutes the consensus model's reliability metrics.

---

## 13.6 Edge Cases

### Weights Sum Validation
Expected: behavior(0.25) + device(0.20) + geo(0.20) + merchant(0.15) + graph(0.20) = 1.00 ✓

If weights don't sum to 1.0, weighted_agents is not a true weighted average — it's a weighted sum. Current weights sum = 1.00. ✓

### Empty Agent Scores
If parallel_agents returns empty dict → all 5 agents default → Test C3 scenario applies.

---

## CRITICAL FINDINGS
1. All-agent failure scenario reports PERFECT consensus at 50% risk — most dangerous failure mode
2. Auto-approve hardcodes agreement=100/confidence=85 — corrupts consensus analytics
3. Agent fallback to 50.0 anchors fraud scores downward when agents partially fail

## WARNINGS
1. Legitimate verdicts have lower confidence than fraud verdicts by design (verdict_boost)
2. Bimodal distribution of agreement_score makes analytics misleading
3. No circuit breaker: if LLM API fails all agents, system continues with 50/100/85 values

---

**Consensus Engine Score: 68 / 100**
