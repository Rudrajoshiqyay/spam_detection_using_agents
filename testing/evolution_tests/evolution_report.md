# Phase 8 — Fraud Evolution Testing Report
**Date:** 2026-06-23 | **Auditor:** QA Agent | **Mode:** READ-ONLY

---

## 8.1 Evolution Framework Overview

**Tool:** `app/simulation/fraud_evolution_agent.py`
**Class:** EvolutionTracker, FraudGeneration
**Generations Supported:** 1–4 (hardcoded bands)

---

## 8.2 Generation Definitions

| Generation | Difficulty Band | Mutations Available | Attack Level |
|---|---|---|---|
| 1 | 10.0–30.0 | None | Basic |
| 2 | 30.0–55.0 | reduce_amount, slow_velocity | Adapted |
| 3 | 55.0–75.0 | + use_trusted_device, change_timing | Sophisticated |
| 4 | 75.0–95.0 | All 8 mutations | APT-level |
| **5+** | **10.0–90.0 (default)** | **ALL (no additional logic)** | **Undefined** |

---

## 8.3 Generation Comparison (Required: Gen 1, 10, 100, 1000, 10000)

### Generation 1 vs Generation 4 (Only Implemented Range)

| Metric | Gen 1 | Gen 4 | Delta |
|---|---|---|---|
| Difficulty Score | 10–30 | 75–95 | +65 |
| Mutations Used | 0 | Up to 8 | +8 |
| Transactions Modified | 0% | ~90% | +90% |
| Est. Pre-Risk Score | 55–75 | 5–20 | −50 |
| Est. Detection Rate | 95% | 28% | −67% |
| Attack Sophistication | Basic | Complex | 5× increase |

### Generation 5–10 (THEORETICAL — beyond implementation)

| Metric | Gen 5 | Gen 10 | Expected |
|---|---|---|---|
| Difficulty Score | 10–90 (random) | Same | **No improvement** |
| New Mutations | None | None | System has no Gen5+ logic |
| Detection Rate | Same as Gen4 | Same | **No evolution beyond Gen4** |

### Generation 100, 1000, 10000 — IMPOSSIBLE

The system literally cannot generate Gen 100+ in any meaningful sense:
```python
_GEN_DIFFICULTY = {1: ..., 2: ..., 3: ..., 4: ...}
# get(100, (10, 90)) = (10, 90) — same as undefined
```

**CRITICAL:** The EvolutionTracker cannot model the required depth. Comparisons of Gen 100 vs Gen 10000 are impossible without architectural changes.

---

## 8.4 Evolution Arc Analysis

### Expected Arc: generate_full_evolution_arc(4 generations)

```
Gen 1: difficulty=15-25, 0 mutations, basic ATO campaign
Gen 2: difficulty=35-50, 2 mutations (reduce_amount, slow_velocity)
Gen 3: difficulty=60-70, 4 mutations (+ device + timing)
Gen 4: difficulty=80-90, 8 mutations (all)
```

**Assessment:** The 4-generation arc shows clear sophistication growth. ✓

**Gap:** The arc is pre-scripted, not adaptive. Real evolution would require:
1. Run Gen 1 → observe detection_rate
2. Add mutation that specifically defeated the most effective detector
3. Generate Gen 2 tailored to bypass that specific weakness

Current system: Gen 2 always adds `reduce_amount + slow_velocity` regardless of what Gen 1 detection results were.

---

## 8.5 detection_rate Field Analysis

```python
@dataclass
class FraudGeneration:
    ...
    detection_rate: Optional[float] = None  # if known from evaluation
```

**Status:** Field defined, never populated, never used in evolution logic.

**What it should do:** After running Gen N through the pipeline:
1. Record detection_rate for Gen N
2. If detection_rate > 0.80 → Gen N+1 needs different mutations
3. If detection_rate < 0.20 → Gen N was too successful; evolutionary pressure reached max

**What it actually does:** Nothing. Evolution is purely a scripted progression.

---

## 8.6 Module Singleton State Drift

```python
_default_tracker: Optional[EvolutionTracker] = None

def get_evolution_tracker() -> EvolutionTracker:
    global _default_tracker
    if _default_tracker is None:
        _default_tracker = EvolutionTracker()
    return _default_tracker
```

In a long-running API session, calling `/simulate/evolve` multiple times for `account_takeover`:
- Call 1: Gen 1 generated and registered → next is Gen 2
- Call 2: Gen 2 generated → next is Gen 3
- Call 3: Gen 3 → Gen 4
- Call 4: Gen 4 → Gen 5 (undefined behavior, difficulty 10-90)
- Call 5+: Gen 6, 7, 8... all identical behavior to Gen 5

No reset mechanism. Accumulated lineage grows without bound.

---

## 8.7 API Cap at 4 Generations

```python
# main.py:873
result = generate_evolved_campaign(
    campaign_type=req.campaign_type,
    num_generations=min(req.num_generations, 4),  # ← hard cap
)
```

The API endpoint enforces `num_generations = min(request, 4)`. Users cannot generate more than 4 generations via the API, even if they request 100.

---

## 8.8 Difficulty Growth Assessment

| Gen | Min Difficulty | Max Difficulty | Growth Factor |
|---|---|---|---|
| 1 | 10.0 | 30.0 | baseline |
| 2 | 30.0 | 55.0 | 1.8× |
| 3 | 55.0 | 75.0 | 1.4× |
| 4 | 75.0 | 95.0 | 1.3× |

**Diminishing returns pattern** — consistent with real-world evolution (first adaptation is biggest gain). ✓

---

## CRITICAL FINDINGS
1. Evolution capped at 4 generations — Gen 5–10000 impossible
2. API enforces min(request, 4) cap explicitly
3. detection_rate field unused — evolution is scripted, not adaptive
4. Module singleton with no reset accumulates state indefinitely

## WARNINGS
1. Gen 4 applies all 8 mutations simultaneously (may be unrealistic)
2. Evolution selection not intelligent (fixed mutation sets per generation)
3. No cross-campaign learning (each campaign type evolves independently)
4. Difficulty is randomly sampled within band, not progressed deterministically

---

**Evolution Quality Score: 48 / 100**
