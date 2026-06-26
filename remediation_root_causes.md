# FraudGuard AI — Remediation Root Cause Analysis
**Date:** 2026-06-23 | **Sprint:** Remediation Sprint 1

---

## Failing Areas and Root Causes

---

### 1. Security (35/100) — Root Causes

| # | Root Cause | Module | Impact | Score Gain |
|---|---|---|---|---|
| SEC-1 | `generate_cross_border_campaign()` hardcodes `fraud_type="account_takeover"` | fraud_campaign_agent.py:316 | Corrupts ground truth, contaminates ATO metrics | +8 |
| SEC-2 | `generate_card_testing_campaign()` hardcodes `location_city="Unknown"` | fraud_campaign_agent.py:134 | Trivial detection leakage, 100% lift on Unknown city | +7 |
| SEC-3 | `generate_ip_cluster_ring()` calls `_shared_subnet_ip()` twice — graph IP ≠ transaction IP | fraud_ring_agent.py:158,164 | IP cluster detection always misses; ring undetectable | +6 |
| SEC-4 | `generate_ip_cluster_ring()` uses `192.168.x.x` private subnet | fraud_ring_agent.py:151 | Private IPs impossible on internet; trivial leakage | +5 |
| SEC-5 | `generate_multi_vector_ring()` builds no FraudRingGraph | fraud_ring_agent.py:271-294 | Most complex ring type completely undetectable | +6 |
| SEC-6 | CORS `allow_origins=["*"]` — unrestricted cross-origin access | main.py:127 | Any origin can call all API endpoints | +4 |

**Total estimated security score gain: +36 → target 71/100**

---

### 2. Red Team (32/100) — Root Causes

| # | Root Cause | Module | Impact | Score Gain |
|---|---|---|---|---|
| RT-1 | Gen4 mutations (trusted_device + location + amount + velocity) reduce pre_risk below 35 | fast_screening + adversarial_agent | 72% bypass rate for all Gen4 attacks | +12 |
| RT-2 | Agent score fallback defaults to 50.0 silently | consensus_engine.py:40-45 | Agent failures lower blended_risk, missing fraud | +8 |
| RT-3 | Auto-approve path injects fake agreement=100/confidence=85 | fraud_pipeline.py:386-390 | Analytics corrupted; no real signal for bypasses | +5 |
| RT-4 | Money mule double-injection on mule_users[0] | fraud_campaign_agent.py:177 | First mule gets inject + layer_1, corrupting campaign | +3 |

**Total estimated red team score gain: +28 → target 60/100**

---

### 3. Chaos (28/100) — Root Causes

| # | Root Cause | Module | Impact | Score Gain |
|---|---|---|---|---|
| CHAOS-1 | `_update_feature_store()` swallows all exceptions silently (`except Exception: pass`) | fraud_pipeline.py:459-460 | Feature data silently lost; behavioral models stale | +10 |
| CHAOS-2 | All LLM agent failures → default 50.0 → perfect consensus at 50% — may approve fraud | consensus_engine.py | Full API outage produces dangerously wrong decisions | +12 |
| CHAOS-3 | No error logging or metrics for agent/component failures | pipeline + agents | Ops team cannot detect degradation | +8 |

**Total estimated chaos score gain: +30 → target 58/100**

---

### 4. Model Monitoring (22/100) — Root Causes

| # | Root Cause | Module | Impact | Score Gain |
|---|---|---|---|---|
| MON-1 | `/metrics/evaluation` uses `expected_label` as both ground truth and prediction | main.py:808 | Always 100% accuracy — monitoring completely blind | +20 |
| MON-2 | No Precision, Recall, F1, ROC-AUC, or PR-AUC computed anywhere | evaluation_engine.py | Cannot measure actual detection performance | +15 |
| MON-3 | No drift alert thresholds or monitoring triggers | N/A | Degradation goes undetected for weeks | +8 |

**Total estimated monitoring score gain: +43 → target 65/100**

---

### 5. Scalability (38/100) — Root Causes

| # | Root Cause | Module | Impact | Score Gain |
|---|---|---|---|---|
| SCALE-1 | `FraudGraph._account_txns` grows unbounded in RAM | graph_intelligence.py | OOM at 100k users; 3GB+ at 10k users | +12 |
| SCALE-2 | SQLite single-writer serializes all ground truth writes | ground_truth_store.py | Saturates at 200 writes/sec | +8 |
| SCALE-3 | IP cluster threshold (≥3) static regardless of population size | graph_intelligence.py | 100% FP rate at 10k users | +10 |
| SCALE-4 | Population weight mismatch between two modules | population_simulator.py vs persona_agent.py | PSI=0.623 internal inconsistency | +5 |

**Total estimated scalability score gain: +35 → target 73/100**

---

### 6. Regression (38/100) — Root Causes

| # | Root Cause | Module | Impact | Score Gain |
|---|---|---|---|---|
| REG-1 | Zero automated test coverage for any core formula | All | Any code change can silently break detection | +15 |
| REG-2 | Core thresholds hardcoded across 7 files with no central config | Multiple | Cannot validate threshold changes | +8 |
| REG-3 | `attack_version` field in ground_truth.db never populated | ground_truth_store.py | Cannot correlate bugs to versions | +5 |
| REG-4 | No regression baselines stored | N/A | No comparison point for change detection | +10 |

**Total estimated regression score gain: +38 → target 76/100**

---

### 7. Load Testing (42/100) — Root Causes

| # | Root Cause | Module | Impact | Score Gain |
|---|---|---|---|---|
| LOAD-1 | SQLite cannot handle > 200 writes/sec | ground_truth_store.py | System fails at 1k TPS | +8 |
| LOAD-2 | Fire-and-forget `_update_feature_store` accumulates tasks without bound | fraud_pipeline.py | Memory leak under high load | +5 |
| LOAD-3 | No rate limiting or backpressure on API | main.py | Queue overflow under load | +5 |
| LOAD-4 | 6+ sequential LLM calls cannot meet 1.5s SLA | fraud_pipeline.py | Deep investigation path too slow | +8 |

**Total estimated load score gain: +26 → target 68/100**

---

### 8. Evolution (48/100) — Root Causes

| # | Root Cause | Module | Impact | Score Gain |
|---|---|---|---|---|
| EVOL-1 | `_GEN_DIFFICULTY` dict only has 4 keys; Gen5+ falls to default band | fraud_evolution_agent.py | Cannot test Gen 5–10000 | +12 |
| EVOL-2 | `detection_rate` field defined but never populated | fraud_evolution_agent.py | Evolution is scripted not adaptive | +8 |
| EVOL-3 | API enforces `min(req.num_generations, 4)` hard cap | main.py:872 | API blocks any evolution beyond 4 gens | +5 |
| EVOL-4 | Module-level singleton accumulates lineage without reset | fraud_evolution_agent.py | State drift in long-running sessions | +5 |

**Total estimated evolution score gain: +30 → target 78/100**

---

### 9. Drift (52/100) — Root Causes

| # | Root Cause | Module | Impact | Score Gain |
|---|---|---|---|---|
| DRIFT-1 | Population weights in population_simulator.py ≠ persona_agent.py | Both modules | PSI=0.623 between internal modules | +12 |
| DRIFT-2 | `_income_for_persona()` uses `x/(x+1)` bias transform | population_simulator.py | Income distribution systematically underestimated | +8 |
| DRIFT-3 | Gauss-Poisson approximation for low-λ personas (senior: λ=1.4) | temporal_simulator.py | Zero-day inflation for seniors (35% vs expected 25%) | +5 |
| DRIFT-4 | No PSI/drift monitoring infrastructure | N/A | Drift never detected | +5 |

**Total estimated drift score gain: +30 → target 82/100**

---

## Summary — Estimated Score Impact

| Area | Current | Expected After Fixes | Gain |
|---|---|---|---|
| Security | 35 | 71 | +36 |
| Red Team | 32 | 60 | +28 |
| Chaos | 28 | 58 | +30 |
| Model Monitoring | 22 | 65 | +43 |
| Scalability | 38 | 73 | +35 |
| Regression | 38 | 76 | +38 |
| Load Testing | 42 | 68 | +26 |
| Evolution | 48 | 78 | +30 |
| Drift | 52 | 82 | +30 |
| **Overall (Weighted)** | **46** | **~75** | **+29** |

---

## Fix Priority Order

1. `main.py` — metrics evaluation bug (10 min fix, +20 monitoring score)
2. `consensus_engine.py` — all-agent failure mode (+12 chaos score)
3. `fraud_pipeline.py` — bare except fix (+10 chaos score)
4. `fraud_campaign_agent.py` — cross-border label, card testing city, mule injection (+21 security)
5. `fraud_ring_agent.py` — IP consistency, private IPs, multi-vector graph (+17 security)
6. `main.py` — evolution cap removal, CORS restriction
7. `population_simulator.py` — weight synchronization (+12 drift)
8. Create regression baselines + monitoring plan (+38 regression, +43 monitoring)
