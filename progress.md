# FraudGuard AI — Project Progress

## Last Updated: 2026-06-26 (Frontend Sprint COMPLETE)

---

## Project Structure
```
fraud-detection-system/
├── app/
│   ├── agents/          ← All 10 LLM agents (behavior, device, geo, merchant, graph, investigation, counterfactual, explainability, analyst, storytelling)
│   ├── feedback/        ← feedback_store, pattern_evolution, reputation_updater
│   ├── models/          ← transaction, user_profile, evidence, fraud_decision
│   ├── pipeline/        ← fraud_pipeline (main orchestrator)
│   ├── scenario/        ← scenario_builder
│   ├── services/        ← 15 core services (fast_screening, feature_store, behavioral_similarity, fraud_patterns, sequence_intelligence, kill_chain, cohort_analysis, risk_delta, device/merchant/geo reputation engines, negative_signals, graph_intelligence, evidence_builder, consensus_engine)
│   ├── simulation/      ← synthetic data generation layer
│   │   ├── persona_agent.py          — 8 persona types
│   │   ├── fraud_campaign_agent.py   — 6 campaign types
│   │   ├── fraud_ring_agent.py       — 5 ring types
│   │   ├── adversarial_agent.py      — 8 mutation types
│   │   ├── fraud_evolution_agent.py  — 4 generations (EvolutionTracker)
│   │   ├── population_simulator.py   — correlated population generator
│   │   ├── world_builder.py          — 100+ cities, 30 merchant categories, 500+ merchant pool
│   │   ├── temporal_simulator.py     — persona-aware timestamps
│   │   ├── ground_truth_store.py     — SQLite label store
│   │   ├── label_leakage_detector.py — leakage detection
│   │   ├── dataset_validator.py      — 9-dimension quality scorer
│   │   └── evaluation_engine.py      — confusion matrix + stratified metrics
│   └── synthetic/       ← original generators (user, merchant, device, geo, transaction, fraud_injector)
├── audit_reports/       ← Forensic audit outputs (ACTIVE)
├── reports/
├── ARCHITECTURE.md
├── requirements.txt
├── docker-compose.yml
├── dashboard.html
└── frontend.html
```

---

## Completion Status

### ✅ DONE (Core Components)
- [x] All 8 persona types (persona_agent.py)
- [x] Population Simulator with correlated distribution
- [x] World Builder (100+ cities, 30 merchant categories, 500+ merchants)
- [x] Temporal Simulator with salary/weekend/monthly patterns
- [x] 6 fraud campaign types (ATO, card_testing, money_mule, velocity, synthetic_identity, cross_border)
- [x] 5 fraud ring types (shared_device, ip_cluster, merchant_ring, mule_chain, multi_vector)
- [x] 8 adversarial mutation types
- [x] 4-generation fraud evolution tracker
- [x] Ground Truth Store (SQLite)
- [x] Label Leakage Detector
- [x] Dataset Quality Validator (9 dimensions)
- [x] Evaluation Engine (stratified metrics)
- [x] All 15 detection services
- [x] All 10 LLM agents
- [x] Consensus Engine
- [x] Feedback Store + Pattern Evolution + Reputation Updater
- [x] Main fraud pipeline

### ⚠️ KNOWN ISSUES (from 2026-06-23 audit)
See: `audit_reports/synthetic_audit_2026-06-23.md`

CRITICAL:
- Card testing always sets `location_city = "Unknown"` → label leakage
- Cross-border campaign labels fraud_type as "account_takeover" (wrong label)
- Money mule: double-injection bug (first mule gets inject + layer_1)
- Multi-vector ring loses graph structure (no FraudRingGraph built)
- Evolution only supports 4 generations (no gen 5-10000)
- No PSI/KL drift detection infrastructure

WARNINGS:
- Dual population weight systems (persona_agent vs population_simulator)
- Gig worker and salaried_employee share UserType
- All ring types use fixed-cadence timestamps (6h, 8h)
- 192.168.x.x private IPs in ip_cluster rings (unrealistic)

### ✅ MASTER AUDIT COMPLETE (2026-06-23)

**22-Phase Framework:** ALL PHASES COMPLETE
**Final Verdict: FAIL — NOT PRODUCTION READY (46/100)**

Phase reports:
- Phase 1: testing/realism_tests/realism_report.md (71/100)
- Phase 2: testing/distribution_tests/distribution_report.md (68/100)
- Phase 3: testing/cross_validation/cross_validation_report.md (65/100)
- Phase 4: testing/cross_validation/leakage_report.md (55/100)
- Phase 5: testing/adversarial_tests/campaign_validation_report.md (62/100)
- Phase 6: testing/graph_tests/graph_report.md (65/100)
- Phase 7: testing/adversarial_tests/adversarial_report.md (72% bypass rate)
- Phase 8: testing/evolution_tests/evolution_report.md (48/100)
- Phase 9: testing/drift_tests/drift_report.md (52/100)
- Phase 10: testing/benchmark_tests/benchmark_report.md (61/100)
- Phase 11: testing/regression_tests/regression_report.md (38/100)
- Phase 12: testing/golden_dataset_tests/golden_dataset_report.md (60/100)
- Phase 13: testing/consensus_tests/consensus_report.md (68/100)
- Phase 14: testing/explainability_tests/explainability_report.md (58/100)
- Phase 15: testing/generator_health/generator_health_report.md (58/100)
- Phase 16: testing/load_tests/load_test_report.md (42/100)
- Phase 17: testing/scalability_tests/scalability_report.md (38/100)
- Phase 18: testing/security_tests/security_report.md (35/100)
- Phase 19: testing/chaos_tests/chaos_report.md (28/100)
- Phase 20: testing/model_monitoring/model_monitoring_report.md (22/100)
- Phase 21: testing/red_team/red_team_report.md (32/100)
- Phase 22: audit/history/audit_history_2026-06-23.md

**FINAL DELIVERABLE:** testing/reports/master_audit_report.md
- 20 bugs documented (7 critical)
- Top 50 Findings | Top 50 Risks | Top 50 Recommendations
- Overall: 46/100 — FAIL

### ✅ REMEDIATION SPRINT 1 COMPLETE (2026-06-23)

**Score: 46/100 → ~63/100 (estimated)**

**Code fixes applied (6 files):**
- [x] REC-01: /metrics/evaluation fixed (returns honest composition, not 100% accuracy)
- [x] REC-03: All-agent LLM failure → agreement=0.0 (not 100 — was dangerous)
- [x] REC-04: Multi-vector ring now builds FraudRingGraph with proper edges
- [x] REC-05: IP cluster ring — IP per user assigned once, consistent graph+transaction
- [x] REC-06: Cross-border campaign fraud_type = "cross_border_fraud" (was "account_takeover")
- [x] REC-10: Feature store failure now logs WARNING (not silent pass)
- [x] Card testing city uses real DOMESTIC_CITIES (not "Unknown")
- [x] Money mule double-injection fixed (loop starts at mule_users[1:])
- [x] IP cluster ring uses 103.x.x.x public IPs (not 192.168.x.x private)
- [x] Auto-approve consensus is now graduated (not hardcoded 100/85)
- [x] Population weights: POPULATION_WEIGHTS = _PERSONA_WEIGHTS (single source)
- [x] Evolution API cap raised: min(n, 4) → min(n, 10)
- [x] CORS restricted to localhost origins (not "*")

**Documents created:**
- remediation_root_causes.md
- security_fixes.md
- red_team_hardening.md
- scalability_improvements.md
- testing/regression_baselines/baseline_metrics.md
- regression_plan.md
- monitoring_plan.md
- remediation_report.md

### ✅ REMEDIATION VALIDATION COMPLETE (2026-06-23)

**Result: 58/100** (was 46/100, target 75/100)

- Validated all 13 fixes confirmed present in 6 source files
- Security: 35 → 66 (+31)
- Red Team: 32 → 52 (+20) — bypass rate 68.3% → ~49%
- Scalability: 38 → 50 (+12) — PSI 0.623 → 0.000 confirmed
- Regression: 38 → 55 (+17) — 13/13 baselines pass
- Monitoring: 22 → 37 (+15) — no more 100% fake accuracy

**4 minor issues found during validation (not blocking):**
- V-01 LOW: `explainability.confidence_score` still hardcoded 85.0 at `fraud_pipeline.py:398`
- V-02 LOW: Multi-vector ring IP partition over-connected (cosmetic)
- V-03 INFO: `/metrics/confusion-matrix` still uses expected_label as prediction
- V-04 INFO: money_mule cashout user also receives last layer txn

**Report:** `post_remediation_validation.md`

### ✅ MODELS + SCENARIO AUDIT & FIXES COMPLETE (2026-06-26)

**Modules fixed: app/models/ and app/scenario/**
**New test coverage: tests/test_models.py (49 tests), tests/test_scenario.py (35 tests) — 84/84 passing**

Models score: 46/100 → **82/100**
Scenario score: 51/100 → **84/100**

**app/models/ — all files updated:**
- transaction.py: DeviceType/TransactionType/Channel enums, Field(gt=0) on amount, Field(ge/le) on lat/lon, timezone-aware timestamp, Dict[str,Any] typing, model_config use_enum_values=True
- user_profile.py: TravelFrequency enum, AccountStatus enum, Field bounds on SpendingProfile/AdaptiveThresholds, hour validator on typical_transaction_hours
- evidence.py: EvidenceType constants, Field bounds on all 11 score fields in InvestigationPackage with documented scales
- fraud_decision.py: Field(ge=0, le=100) on ExplainabilityResult.risk_score + confidence_score, CounterfactualResult.contribution_score, FraudDetectionResult.pre_risk_score; timezone-aware timestamp

**app/scenario/ — scenario_builder.py updated:**
- seed: Optional[int] added to ScenarioConfig → deterministic execution
- ScenarioConfig.__post_init__ validates all fields (fraud_rate, span_days, counts, fraud_types)
- O(n²) user_meta lookup replaced with O(1) dict index
- Silent except: pass removed → replaced with _logger.warning (failures never increment injected_count)
- ring partition skips rings < 2 members with explicit warning
- stress_test + fraud_heavy presets added (was missing from spec)
- card_testing_wave: span_days 7→14; mule_network: span_days 7→30
- Summary stats computed from actual data (not from targets)
- run_config snapshot included in output (seed, all config values)

### ✅ PIPELINE AUDIT & FIXES COMPLETE (2026-06-26)

**Module fixed: app/pipeline/fraud_pipeline.py**
**New test coverage: tests/test_pipeline.py (26 tests) — 110/110 passing total**

Pipeline score: 63/100 → **87/100** (estimated)

**P0 fixes (all done):**
- C-5: node_feature_retrieval wraps feature_store calls in try-except with empty-feature fallback
- C-1: asyncio.wait_for(timeout=30s) on all 5 parallel LLM agents (node_parallel_agents)
- C-1: asyncio.wait_for(timeout=30s) on investigation + counterfactual gather (node_investigation)
- C-2: asyncio.create_task(_update_feature_store) stored in _background_tasks set to prevent GC cancellation
- C-3 / V-01: confidence_score=85.0 replaced with computed screening_confidence in node_auto_approve
- C-4: txn.user_id != profile.user_id guard in run_fraud_detection raises ValueError

**P1 fixes (all done):**
- M-6: return_exceptions=True on deterministic service gather + _svc_fallback per-result handler
- M-1: except Exception now logs _logger.warning with prev_ts_str, user, error (not silent)
- M-2: dead import `from app.models.fraud_decision import AgentRisk` removed
- M-3: threading.Lock (_graph_lock) serialises fraud_graph.analyze() and add_transaction()
- M-4: asyncio.wait_for(timeout=120s) wraps full pipeline ainvoke in run_fraud_detection
- M-5: node_explainability, node_analyst, node_storytelling all get asyncio.wait_for(30s)

**P2 fixes (all done):**
- mn-1: Module-level fraud_pipeline = build_pipeline() replaced with lazy _get_pipeline()
- mn-3: _ENABLE_STORYTELLING flag controls storytelling node wiring in build_pipeline()
- mn-4: In-memory dedup (bounded _DEDUP_MAX_SIZE=10_000) rejects duplicate transaction_ids

**Also added:**
- _logger = logging.getLogger(__name__) and all warning calls use it
- import threading + import logging + from datetime import datetime at top level
- _background_tasks: set module-level to hold fire-and-forget task refs

### ✅ AI AGENTS AUDIT & IMPROVEMENT SPRINT COMPLETE (2026-06-26)

**Modules fixed: app/agents/ (10 agents + 2 new shared modules)**
**New test coverage: tests/test_agents.py (103 tests) — 213/213 passing total**

Agents score: 60/100 → **91+/100** (estimated)

**New shared infrastructure (S1, S4):**
- `app/agents/_llm_clients.py` (NEW): Lazy-initialized shared `get_fast_llm()` / `get_deep_llm()` — eliminates 10 module-level `ChatAnthropic(...)` constructors that failed at import if no API key
- `app/agents/_agent_base.py` (NEW): All shared utilities — `sanitize()`, `sanitize_list()`, `parse_llm_json()`, `build_parallel_output()`, `compute_fallback_confidence()`, `geo_risk_score()`, `graph_risk_score()`, `ParallelAgentOutput` (Pydantic validated contract), verdict sets

**All 10 agents rewritten (S1–S8):**
- `behavior_agent.py`, `device_agent.py`, `geo_agent.py`, `merchant_agent.py`, `graph_agent.py`: parallel analysis agents with fast LLM
- `investigation_agent.py`, `explainability_agent.py`: deep LLM agents with `get_deep_llm()`
- `counterfactual_agent.py`: `_deterministic_counterfactual()` fallback with `_SIGNAL_WEIGHTS`
- `analyst_agent.py`: full LLM→fallback chain, `_fallback_action()` with 6 thresholds
- `storytelling_agent.py`: narrative generation with sanitized inputs
- `mock_llm.py`: `mock_geo()` and `mock_graph()` now use `geo_risk_score()` / `graph_risk_score()` (unified formulas)

**Sprint fixes per category:**
- S1 (Silent failures): All `except Exception: pass` → `_logger.warning(name, elapsed_ms, txn_id, exc_type, exc)`
- S1 (System prompt): All agents use `[SystemMessage(content=_SYSTEM), HumanMessage(content=prompt)]` (was `config={"system": ...}` — wrong)
- S2 (Consistency): Unified scoring formulas as module-level functions shared between mock and fallback paths
- S3 (Prompt hardening): All evidence_summary/signal lists go through `sanitize()` / `sanitize_list()` with injection regex
- S4 (Typed contracts): `ParallelAgentOutput` Pydantic model validates/clamps all 5 parallel agent outputs before consensus
- S5 (Observability): `t0 = time.perf_counter()` timing in all agents; fallback reason logging; verdict/score in debug logs
- S6 (Testing): 103-test suite covering base utilities, LLM client lazy-init, all mock paths, fallback paths, threshold boundaries, injection security
- S7 (Performance): All imports at top level; no `import json, re` inside try blocks
- S8 (Security): `_INJECTION_RE` redacts known injection patterns; evidence items capped (5–8) per agent

### ✅ SERVICES REMEDIATION SPRINT COMPLETE (2026-06-26)

**Score: 76.3/100 → ~91/100 (estimated)**
**Audit report:** `SERVICES_AUDIT.md`
**New test coverage:** `tests/test_services.py` (70 tests) — **283/283 total passing**

#### Sprint 1 — Critical Production Fixes (all resolved)

**`graph_intelligence.py`** (was 56/100 — F):
- [x] Replaced all 4 unbounded `defaultdict`s with `_BoundedLookup` (LRU, `OrderedDict`-backed, max 10,000 keys each)
- [x] Per-user `_account_txns` now uses `deque(maxlen=100)` ring buffer; user keys also LRU-evicted at 10,000
- [x] `except Exception: pass` → `_logger.error(...)` with user_id, device_id, exception type and message
- [x] `fraud_ring_detected` now catches IP-only rings: `fraud_assoc AND (shared_device≥2 OR shared_ip≥3)`
- [x] `get_metrics()` method exposes eviction counts and memory footprint for health-check endpoints
- [x] `_BoundedLookup.get()` refreshes LRU order on reads (correct LRU semantics)

**`feature_store.py`** (was 67/100):
- [x] `get_recent_events()`: `json.loads(e)` wrapped in `try/except json.JSONDecodeError` — corrupted entries skipped with warning log
- [x] All 3 `print()` calls replaced with `_logger.info()` / `_logger.warning()` — no more stdout noise

**`consensus_engine.py`** (was 78/100):
- [x] Missing agent sentinel 50.0 replaced with **weight redistribution** — present agents' weights scaled proportionally so relative weighting is preserved
- [x] All-agents-missing fallback uses `pre_risk_score` (not 50.0)
- [x] Missing agents displayed in `agent_risks` with `key_findings=["agent_unavailable"]` and `risk_score=pre_risk_score`
- [x] `_logger.warning()` on partial failure; `_logger.error()` on total failure
- [x] Added `logging` import

**Data file loading — `fraud_patterns.py`, `kill_chain.py`, `cohort_analysis.py`**:
- [x] All 3 `load_*()` functions wrapped in `try/except FileNotFoundError` + `json.JSONDecodeError`
- [x] `cohort_analysis.py`: fallback to `_DEFAULT_COHORT` on file failure (pipeline continues)
- [x] `fraud_patterns.py` + `kill_chain.py`: fallback to `{}` (matching disabled, pipeline continues)
- [x] `_normal_cdf()` extracted to module level in cohort_analysis (now unit-testable)
- [x] Unknown user_type logs debug warning instead of silently using wrong cohort

#### Sprint 2 — Logic Improvements (all resolved)

**`sequence_intelligence.py`** (was 69/100):
- [x] `merchant_abuse` removed from `_SEQUENCES` — cross-account detection belongs to graph layer (comment explains why)
- [x] ATO scoring: `_check_account_takeover()` now weights by signal count (`min(1.0, ato_signals_found * 0.25)`) — no longer flat 0.7
- [x] Velocity burst: current transaction included in count (was excluded — off-by-one)
- [x] `_check_account_takeover()` extracted as named function (was inline)

**`negative_signals.py`** (was 75/100):
- [x] `evaluate_signals()` gains optional `sequence_result` and `cohort_result` parameters (backwards compatible)
- [x] `micro_transaction_burst` now triggers when `card_testing` is in `sequence_result.active_sequences`
- [x] `night_transaction_high_amount` now triggers: `hour < 5 AND amount > avg*2`
- [x] `first_time_merchant` now triggers when `merchant_frequencies[merchant_id] == 0`
- [x] `new_merchant_high_risk_cat` compounded with `first_time_merchant` for high-risk categories
- [x] `recurring_payment_pattern` triggers at 10+ merchant visits
- [x] `salary_credit_pattern` triggers for accounts >180 days with amount ≤ 2×avg
- [x] `within_cohort_normal` triggers when `cohort_deviation_score < 25` (requires `cohort_result` param)

**`fast_screening.py`** (was 72/100):
- [x] Hardcoded `/ 0.3` replaced with named constant `_DEVICE_NOVELTY_BASELINE = 0.3`
- [x] Device novelty score capped at 50.0 (was uncapped for extreme threshold values)
- [x] `import logging` + `_logger` added

**`evidence_builder.py`** (was 83/100):
- [x] `_safe_str()` sanitizes free-text fields (merchant_name, location, geo verdict) against prompt injection using `_INJECTION_RE` regex
- [x] `_fmt_signals()` renders signal lists as `"a, b, c"` (not Python `['a', 'b']` repr)
- [x] All 13 summary lines updated to use `_safe_str()` / `_fmt_signals()`

#### Sprint 3 — Additional Correctness Fixes

**`behavioral_similarity.py`** (was 74/100):
- [x] `TravelFrequency` enum/string key lookup: `travel_freq.value if hasattr(travel_freq, 'value') else str(travel_freq)` — no more silent 0.05 default on enum mismatch
- [x] `risk_proxy = 0.1` hardcoding removed — replaced with `fraud_proxy` using `profile.fraud_history` (consistent with profile_vector dimension 6)

**`risk_delta.py`** (was 85/100):
- [x] `velocity_delta` division by zero guarded: `if max_per_hour > 0 and txn_count_1h > max_per_hour`

**`device_reputation.py`** (was 79/100):
- [x] `feature_store.get_device_reputation()` wrapped in `try/except` with `_SAFE_DEVICE_DEFAULTS` fallback
- [x] `_logger.warning()` on feature_store failure

**`merchant_reputation.py`** (was 80/100):
- [x] `feature_store.get_merchant_reputation()` wrapped in `try/except` with `_SAFE_MERCHANT_DEFAULTS` fallback
- [x] `_logger.warning()` on feature_store failure

#### Test Coverage Added (`tests/test_services.py` — 70 tests)

| Test Class | Tests | Coverage |
|---|---|---|
| `TestBoundedLookup` | 6 | LRU eviction, add/get, len, capacity |
| `TestFraudGraph` | 12 | All detection paths, IP-only ring, NX exception, ring buffer, metrics |
| `TestFeatureStoreJsonSafety` | 3 | Corrupted entries, all-corrupted, all-valid |
| `TestConsensusEngine` | 5 | Weight redistribution, all-missing, per-agent report, agreement penalty |
| `TestSequenceIntelligence` | 6 | Velocity burst fix, ATO scaling, card testing, merchant_abuse absent |
| `TestNegativeSignals` | 10 | All newly-implemented signals, cohort_normal, no-fraud with trust signals |
| `TestFastScreening` | 4 | Baseline normalization, proportional scaling, cap at 50, known device |
| `TestEvidenceBuilder` | 3 | Injection redaction, clean list repr, signal presence |
| `TestBehavioralSimilarity` | 6 | Enum key, string key, unknown key, fraud_proxy, bounds |
| `TestRiskDelta` | 4 | ZeroDivisionError guard, velocity delta, location delta, keys |
| `TestDeviceReputation` | 2 | Feature store failure resilience, known vs unknown trust |
| `TestMerchantReputation` | 2 | Feature store failure resilience, category penalty |
| `TestCohortAnalysis` | 3 | Missing file, bad JSON, pipeline continues with default |
| `TestFraudPatternsFileLoad` | 2 | Missing file, bad JSON |
| `TestKillChainFileLoad` | 2 | Missing file, bad JSON |

### ✅ FEEDBACK LOOP AUDIT COMPLETE (2026-06-26)

**Pre-sprint audit report:** `FEEDBACK_AUDIT.md`  
**Pre-sprint scores:** feedback_store 65 · pattern_evolution 42 · reputation_updater 41 · **Overall 49/100 (F)**

### ✅ FEEDBACK LOOP SPRINT 4 COMPLETE (2026-06-26)

**Score: 49/100 → 92/100 (estimated)**  
**New test coverage:** `tests/test_feedback.py` (40 tests) — **323/323 total passing**

#### All C-1 through C-8 Critical Issues Resolved

**`feedback_store.py`** (was 65/100):
- [x] C-8: `UNIQUE INDEX ON feedback(transaction_id, COALESCE(reviewer_id, ''))` dedup constraint
- [x] C-7: F1 bug fixed — `if precision is not None and recall is not None and (precision + recall) > 0`
- [x] C-4: `processed_at TEXT` column + `get_unprocessed_feedback()` + `mark_feedback_processed()` high-watermark
- [x] `device_id TEXT` and `merchant_id TEXT` columns added to schema (trusted device/merchant source for reputation updater)
- [x] `record_pattern_update()` function added — writes to `pattern_updates` audit table
- [x] `feedback_id = f"fb_{uuid.uuid4().hex}"` — full 128-bit UUID (was 40-bit `hex[:10]`)
- [x] Notes truncated to 2000 chars at application layer
- [x] Indexes on `outcome_label`, `created_at`, `processed_at`
- [x] Migration: `ALTER TABLE ADD COLUMN` idempotently adds new columns to existing DBs
- [x] `import logging` + `_logger` added throughout

**`pattern_evolution.py`** (was 42/100):
- [x] C-2: Module-level `_llm = ChatAnthropic(...)` removed → replaced with `get_fast_llm()` lazy call
- [x] C-3: `boost` now applied to signal weights: `{k: round(min(1.0, v * boost), 4) for k, v in signals.items()}`
- [x] C-5: Atomic JSON write via `tempfile.NamedTemporaryFile` + `os.replace()` — no partial-write corruption
- [x] C-10: `record_pattern_update()` called for every threshold/weight change (full audit trail)
- [x] `_load_patterns()` extracted with `try/except FileNotFoundError` + `json.JSONDecodeError` — graceful fallback
- [x] Threshold recovery: patterns with 0 misses and threshold < 0.75 nudge up by 0.01/cycle (prevents permanent 0.45 floor)
- [x] `_safe_notes()` sanitizes analyst notes before LLM context (`_INJECTION_RE` redaction + truncation to 200 chars)
- [x] `except Exception: pass` → `_logger.warning(type, message)` with reason
- [x] `import re` moved to module top (was inside try block)
- [x] `SystemMessage` added to LLM invocation (same fix as agents sprint)
- [x] `_MAX_FEEDBACK_WINDOW = 200` cap on `feedback_window` parameter
- [x] LLM JSON validation: checks `isinstance(emerging, list)` before returning

**`reputation_updater.py`** (was 41/100):
- [x] C-1: **Reputation poisoning eliminated** — notes never parsed for IDs; `device_id`/`merchant_id` read from trusted feedback record fields
- [x] C-6: All `except Exception` replaced with `_logger.error(...)` (exception type + message logged)
- [x] C-4: `get_unprocessed_feedback()` + `mark_feedback_processed()` — each record processed exactly once
- [x] `_restore_merchant()` added — FP now restores merchant reputation symmetrically (+0.10)
- [x] FN penalty = 0.20 (higher than TP = 0.15; `is_miss` distinction now actually applied)
- [x] FP restoration delta equalized to 0.10 (matches TP penalty; was 0.05 — asymmetric)
- [x] Feature store failures wrapped in `try/except` with `_logger.warning()`
- [x] `import logging` + `_logger` added

**`fast_screening.py`** (feedback loop closure):
- [x] I-9: `risk_elevation` read from user features and applied as additive boost (`min(25.0, elevation * 0.25)`)
- [x] Flag added: `"feedback_risk_elevation:{boost:.1f}"` for observability
- [x] `feedback_elevation` included in `component_scores` dict

**`main.py`** (API updates):
- [x] `FeedbackSubmitRequest` gains `device_id: Optional[str]` and `merchant_id: Optional[str]` fields
- [x] Both forwarded to `submit_feedback()` call
- [x] `update_reputation_from_feedback(feedback_id=...)` → `update_reputation_from_feedback()` (high-watermark handles it)
- [x] `/feedback/update-reputation` gains `limit` query param (max 500)

#### Test Coverage Added (`tests/test_feedback.py` — 40 tests)

| Test Class | Tests | Coverage |
|---|---|---|
| `TestFeedbackStore` | 15 | UUID length, dedup, null-reviewer dedup, notes truncation, high-watermark, idempotent mark, pattern_updates table, F1 bug (0.0 falsy), F1 both nonzero, false_positive filter, empty DB |
| `TestPatternEvolution` | 12 | No import-time LLM init, safe_notes redaction/truncation, missing/bad JSON file, boost applied to signals, threshold lowering, threshold recovery, audit trail written, atomic write, insufficient FNs, LLM failure graceful |
| `TestReputationUpdater` | 10 | Notes NOT parsed (field used), TP penalizes both, FP restores both, FN higher delta, high-watermark marks all, no double-processing, exception logged+still-marked, feature_store failure, confirmed_fraud writes risk_elevation, false_positive noted |
| `TestFeedbackLoopClosure` | 3 | risk_elevation boosts score, zero elevation no effect, boost capped at 25 |

### ✅ FRONTEND SPRINT COMPLETE (2026-06-26)

**React/TypeScript/Vite production frontend — fully built and shipping**

**Stack:** React 19, TypeScript, Vite 6, Tailwind CSS v4, Framer Motion, TanStack Query, Recharts, React Router v6, Lucide React

**Experience 1 — Customer/Analyst Dashboard (`/dashboard`):**
- Hero cards: 6 real-time metrics with trend arrows
- Live transaction feed: streams a new transaction every 4-7s (real API or mock fallback), sortable/filterable/searchable, pagination
- Investigation panel: slide-out with transaction timeline, per-agent risk bars, positive/negative signals, explanation, counterfactual, narrative, analyst feedback buttons
- 4 Recharts charts: 24h transaction volume, risk score distribution, fraud type pie, 7-day trend
- System health grid (8 service metrics from feature store/Redis/LLM/graph)
- Feedback loop stats card (F1, precision, recall, outcome counts)

**Experience 2 — AI Pipeline Visualization (`/pipeline`):**
- SVG canvas with all 17 pipeline nodes at correct positions
- 22 animated directed edges (cubic Bezier, animated flow dot on active edges)
- 17-step walkthrough demo mode (Play/Pause/Step) with real fraud scenario narration and T+Nms latency callouts
- Click any node → slide-in detail panel: type, latency, audit score, test count, files, inputs, outputs, purpose
- Fully correct node IDs, edge pairs, and demo steps matched to actual backend source

**Experience 3 — Architecture Explorer (`/architecture`):**
- Module summary cards: 7 modules with LOC, test count, audit score, dependencies, status badge

**Secondary pages:** Alerts (mock alert feed), Analytics (4 charts), Feedback (F1 stats), Transactions, Investigations, Settings

**Deployment:**
- `frontend/Dockerfile` — multistage (node:22 build → nginx:1.27 serve), content-hashed assets cached 1y
- `frontend/nginx.conf` — SPA fallback, gzip, /api proxy to backend
- `docker-compose.override.yml` — backend + frontend + redis wired together
- `frontend/.env.example` — VITE_API_URL, VITE_MOCK_MODE

**Build:** `npm run build` → ✅ zero TypeScript errors, 6 chunks:
- vendor (react, router): 50KB gz
- motion (framer-motion): 43KB gz
- charts (recharts): 118KB gz
- index (app code): 93KB gz

**To run locally:**
```
cd frontend
npm install
npm run dev     # → http://localhost:3000 (proxies /api to :8000)
npm run build   # production build to dist/
```

### 🔲 TODO (remaining backlog)
- [ ] REC-02: Add API authentication (JWT or API key) → +8 Security
- [ ] Add circuit breakers for LLM API, feature store, graph → +6 Reliability
- [ ] FraudGraph persistence to SQLite (survive restarts) → +8 Reliability + Red Team
- [ ] Fix V-03: /metrics/confusion-matrix endpoint → +2
- [ ] Rate limiting on API endpoints → +3 Security

---

## Quick Reference — Key Files to Read

| Need to understand... | Read this file |
|---|---|
| Persona definitions | `app/simulation/persona_agent.py` |
| Fraud campaigns | `app/simulation/fraud_campaign_agent.py` |
| Fraud rings | `app/simulation/fraud_ring_agent.py` |
| Evasion mutations | `app/simulation/adversarial_agent.py` |
| Evolution | `app/simulation/fraud_evolution_agent.py` |
| Main pipeline | `app/pipeline/fraud_pipeline.py` |
| API endpoints | `app/main.py` |
| Config | `app/config.py` |
| Audit report (12-phase) | `audit_reports/synthetic_audit_2026-06-23.md` |
| Master audit report (22-phase) | `testing/reports/master_audit_report.md` |
| Audit history | `audit/history/audit_history_2026-06-23.md` |
