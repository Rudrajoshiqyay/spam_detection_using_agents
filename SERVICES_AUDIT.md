# FraudGuard AI — Services & Intelligence Layer Audit
**Date:** 2026-06-26  
**Scope:** `app/services/` — all 16 files  
**Method:** Full source read, red-team analysis, formula verification  
**Previous Score (agents):** 91/100  

---

## Scoring Rubric (Per Service)

| Category | Max |
|---|---|
| Correctness | 25 |
| Reliability | 20 |
| Security | 15 |
| Performance | 10 |
| Scalability | 10 |
| Maintainability | 10 |
| Testing | 10 |
| **Total** | **100** |

---

## Per-Service Audit

---

### 1. `fast_screening.py` — Score: **72/100**

**Purpose:** 7-component composite pre-screening score (velocity, amount, device novelty, merchant risk, location, rule match, behavioral similarity).

| Category | Score | Notes |
|---|---|---|
| Correctness | 18/25 | `device_novelty` uses hardcoded `0.3` denominator (`profile.thresholds.new_device_risk_weight / 0.3`) — wrong if threshold ≠ 0.3 |
| Reliability | 14/20 | No logging import; failures produce no trace; complex normalizer susceptible to division edge cases |
| Security | 12/15 | No direct user input into formulas; no sanitization needed at this layer |
| Performance | 8/10 | Pure computation, fast; normalizer is O(components) |
| Scalability | 8/10 | Stateless; scales horizontally |
| Maintainability | 6/10 | Magic numbers scattered; no logging module; complex normalizer is hard to audit |
| Testing | 6/10 | No dedicated tests; normalizer complexity makes regression risk high |

**Strengths:**
- Lightweight pre-screening correctly gates expensive LLM calls
- Graceful dict.get defaults throughout

**Critical Issues:**
- `device_novelty = 25.0 * profile.thresholds.new_device_risk_weight / 0.3` — hardcoded `0.3` means any threshold not equal to 0.3 produces an incorrect score. If threshold is 0.6 (doubled risk), the score doubles past the intended ceiling.
- No `import logging` — silent on failures

**Recommendations:**
1. Replace `/ 0.3` with `/ profile.thresholds.new_device_risk_weight_baseline` or normalize differently
2. Add `import logging; _logger = logging.getLogger(__name__)`

---

### 2. `feature_store.py` — Score: **67/100**

**Purpose:** Redis-backed feature cache with fallback chain (real Redis → fakeredis → `_DictRedis`).

| Category | Score | Notes |
|---|---|---|
| Correctness | 19/25 | Core correct; `_DictRedis.zcount` ignores upper bound (always called with `+inf`, so harmless now) |
| Reliability | 10/20 | `print()` x3 instead of `logging`; `json.loads()` without try/except crashes on corrupted data |
| Security | 11/15 | `print()` leaks cache state to stdout — in containerized envs this may go to log aggregators |
| Performance | 8/10 | Redis pipeline batching is good design |
| Scalability | 6/10 | `_DictRedis` grows unbounded; no TTL enforcement — memory leak over time |
| Maintainability | 7/10 | Fallback chain is clean; `print()` instead of `logging` is sloppy |
| Testing | 6/10 | Fallback chain testable but untested for corruption paths |

**Strengths:**
- Three-tier fallback chain is robust for test/dev environments
- Pipelined Redis reads for performance

**Critical Issues:**
- `json.loads(e)` at `get_recent_events()` has no try/except — one corrupted Redis entry crashes the call
- `_DictRedis` has no TTL; items never expire → unbounded memory growth in long-running dev environments
- Three `print()` calls (lines 32, 39, 42) — not production-safe; should use `_logger.info()` / `_logger.warning()`

**Recommendations:**
1. Wrap `json.loads(e)` in `try/except json.JSONDecodeError: continue`
2. Replace all `print()` with `logging.getLogger(__name__)`
3. Add simple time-based eviction to `_DictRedis` (check timestamps on write)

---

### 3. `behavioral_similarity.py` — Score: **74/100**

**Purpose:** 7-dimensional cosine similarity + z-score blend for behavioral matching.

| Category | Score | Notes |
|---|---|---|
| Correctness | 16/25 | `travel_map` keyed on strings but `TravelFrequency` enum values may not match; `risk_proxy = 0.1` always hardcoded |
| Reliability | 15/20 | Silent wrong-value returns on enum mismatch; won't crash |
| Security | 13/15 | Pure computation |
| Performance | 9/10 | Fast; O(dimensions) |
| Scalability | 9/10 | Stateless |
| Maintainability | 7/10 | String/enum mismatch is a type-safety hazard |
| Testing | 5/10 | Enum mismatch is the kind of bug that survives all manual testing |

**Strengths:**
- 7-dimensional cosine similarity is a sound approach
- Hour scoring via set lookup is O(1)

**Critical Issues:**
- `travel_map = {"rare": 0.05, "occasional": 0.30, ...}` — if callers pass `TravelFrequency.rare` (enum) instead of `TravelFrequency.rare.value` (string), `.get()` returns `None` → `travel_score = 0.05` default silently
- `risk_proxy = 0.1` is permanently hardcoded — this dimension never reflects actual transaction risk
- Binary hour scoring `1.0 if txn_hour in typical_hours else 0.0` — abrupt cliff at hour boundary

**Recommendations:**
1. Use `travel_freq.value if hasattr(travel_freq, 'value') else travel_freq` for safe lookup
2. Remove `risk_proxy` hardcoding or remove the dimension entirely if not implemented
3. Consider soft hour scoring: `max(0.0, 1.0 - min_distance_to_typical_hour / 6.0)`

---

### 4. `fraud_patterns.py` — Score: **75/100**

**Purpose:** Loads `app/data/fraud_patterns.json`; weighted signal matching against known fraud patterns.

| Category | Score | Notes |
|---|---|---|
| Correctness | 21/25 | Weighted matching logic correct; graph_signals enrichment sensible |
| Reliability | 12/20 | Crash on missing JSON file; `_PATTERNS` lazy-load has no lock — concurrent first calls could double-load |
| Security | 13/15 | Patterns from controlled file; no user input in matching logic |
| Performance | 8/10 | O(patterns × signals); acceptable |
| Scalability | 7/10 | Module-level mutable dict; concurrent writes theoretically possible |
| Maintainability | 8/10 | Clear structure; self-documenting weight system |
| Testing | 6/10 | File dependency makes pure unit testing require mocking or fixture files |

**Strengths:**
- Weighted signal matching with configurable JSON patterns is flexible
- Enrichment via graph signals adds context beyond transaction data

**Issues:**
- `load_patterns()` opens file without try/except — startup crash if file missing
- No thread lock on `_PATTERNS` lazy initialization — concurrent requests on first call could race

**Recommendations:**
1. Wrap file load in try/except with fallback to empty dict + warning log
2. Use `if not _PATTERNS:` check is not thread-safe; use `threading.Lock` or load at import time

---

### 5. `consensus_engine.py` — Score: **78/100**

**Purpose:** Weighted consensus of 5 agent risk scores, blended with pre_risk_score and signal_risk.

| Category | Score | Notes |
|---|---|---|
| Correctness | 17/25 | Missing agent sentinel 50.0 non-neutral — inflates legitimate transactions; `AgentRisk.confidence` stores agent weight, not LLM confidence |
| Reliability | 16/20 | Deterministic; won't crash |
| Security | 14/15 | Internal service |
| Performance | 9/10 | O(agents) |
| Scalability | 9/10 | Stateless |
| Maintainability | 7/10 | Misleading `confidence` field semantics; weights as magic numbers |
| Testing | 6/10 | Sentinel behavior needs explicit tests |

**Strengths:**
- Three-way blend (weighted_risk × 0.70 + pre_risk × 0.20 + signal_risk × 0.10) is well-designed
- Weights documented clearly

**Issues:**
- Missing agent sentinel = **50.0** is non-neutral. A transaction with only 2/5 agents responding gets `50.0` for the 3 missing agents. For a genuinely low-risk transaction, this inflates the final score toward 50 rather than reflecting actual evidence.
- `AgentRisk.confidence` field stores agent **weight** (0.15–0.25), not the agent's actual LLM confidence. Downstream consumers reading this field get wrong values.

**Recommendations:**
1. Missing agent sentinel should be `0.0` (neutral) or the pre_risk_score, not 50.0
2. Rename `AgentRisk.confidence` to `agent_weight` or add a separate `llm_confidence` field
3. Surface actual per-agent LLM confidence in consensus output

---

### 6. `graph_intelligence.py` — Score: **56/100** ⚠️

**Purpose:** NetworkX-based fraud ring detection; shared device/IP/merchant tracking.

| Category | Score | Notes |
|---|---|---|
| Correctness | 14/25 | `fraud_ring_detected` requires BOTH fraud association AND shared device — misses IP-only rings; mule detection has false positive risk |
| Reliability | 8/20 | **CRITICAL**: `except Exception: pass` (line 124) silently swallows all NetworkX errors |
| Security | 12/15 | No injection vectors; but silent failures mask security-relevant graph corruption |
| Performance | 7/10 | NetworkX overhead per call; unbounded dict growth increases memory pressure |
| Scalability | 3/10 | **CRITICAL**: `_device_accounts`, `_ip_accounts`, `_merchant_accounts`, `_account_txns` are unbounded `defaultdict`s — memory leak in production |
| Maintainability | 7/10 | HAS_NX conditional adds complexity |
| Testing | 5/10 | Module-level singleton makes test isolation extremely difficult |

**Strengths:**
- Optional NetworkX dependency with graceful fallback is good design
- Multi-dimensional ring detection (device, IP, merchant) is comprehensive

**Critical Issues:**
- **Memory leak:** `_device_accounts[device_id].add(user_id)`, `_ip_accounts[ip].add(user_id)`, `_account_txns[user_id].append(txn_id)` — no eviction, no TTL. In production with thousands of daily transactions, these dicts grow indefinitely → OOM.
- **Silent failure:** `except Exception: pass` at line 124 — if NetworkX graph corrupts or raises, the fraud ring check silently returns `False`. A fraud ring is missed with no warning.
- **Detection gap:** `fraud_ring_detected = fraud_assoc AND shared_device` — a fraud ring connected only via shared IP is not detected.
- **Mule detection:** `max(amounts) > sum(amounts[:-1]) * 0.8` — high-variance legitimate accounts (e.g., monthly salary + daily coffee) will false-positive.

**Recommendations:**
1. Replace `defaultdict` with LRU dicts (e.g., `functools.lru_cache` or a bounded `OrderedDict`)
2. Change `except Exception: pass` to `except Exception as exc: _logger.error("Graph error: %s", exc)`
3. Add IP-only ring detection: `fraud_ring_detected = fraud_assoc OR (shared_ip AND shared_device)`
4. Add FraudGraph persistence to SQLite on shutdown

---

### 7. `geo_velocity.py` — Score: **80/100**

**Purpose:** Haversine-based travel speed analysis; impossible/suspicious travel detection.

| Category | Score | Notes |
|---|---|---|
| Correctness | 18/25 | Haversine correct; elapsed=0 → infinite speed falsely flags legitimate same-second entries |
| Reliability | 16/20 | `elapsed_seconds <= 0` handled but choice of `float("inf")` is aggressive |
| Security | 14/15 | Pure computation |
| Performance | 9/10 | O(recent_txns) lookup is fast |
| Scalability | 9/10 | Stateless |
| Maintainability | 8/10 | Clear constants; 20-city coordinate list is maintainable |
| Testing | 6/10 | Same-second and same-location edge cases need explicit tests |

**Strengths:**
- Haversine implementation is mathematically correct
- Suspicious travel threshold (< impossible) catches high-speed legitimate travel as medium risk
- 900 km/h ceiling accounts for commercial air travel

**Issues:**
- `elapsed_seconds <= 0`: two transactions at the exact same Unix second get `required_speed = float("inf")` → classified as impossible travel. Legitimate: mobile payments during transit, payment processor batching.
- `_SPEED_IMPOSSIBLE = 900 km/h` is commercial aircraft cruise speed. Supersonic business jets exceed this. Consider 1100 km/h.
- Only 20 hardcoded city coordinates — most city pairs require Haversine on exact lat/lon, which requires caller to provide coordinates.

**Recommendations:**
1. For `elapsed_seconds <= 0`, use a minimum elapsed of 60 seconds (1 minute minimum travel window)
2. Raise `_SPEED_IMPOSSIBLE` to 1100 km/h
3. Accept lat/lon from transaction data instead of coordinate lookup table

---

### 8. `kill_chain.py` — Score: **79/100**

**Purpose:** Matches transaction behavior against known attack kill chains with stage-based amplification.

| Category | Score | Notes |
|---|---|---|
| Correctness | 21/25 | Stage amplification formula sensible; 0.3 similarity threshold appropriate |
| Reliability | 12/20 | Crash on missing `kill_chains.json`; no try/except |
| Security | 14/15 | File-loaded data; no user input in matching |
| Performance | 9/10 | O(chains × signals) |
| Scalability | 9/10 | Stateless |
| Maintainability | 8/10 | Clear structure |
| Testing | 6/10 | File dependency; stage amplification edge cases untested |

**Strengths:**
- Stage-based amplification (`1.0 + stage_idx * 0.2`) elegantly models progressive attack severity
- `min(100, ...)` cap prevents overflow

**Issues:**
- `load_kill_chains()` has no try/except — startup crash if file missing
- No lazy-load lock (same issue as `fraud_patterns.py`)
- Stage amplification starts at index 0 = 1.0x (no amplification for stage 0). Stage numbering may need to start at 1.

**Recommendations:**
1. Wrap file load in try/except with warning log and empty dict fallback
2. Document whether kill chain stages are 0-indexed or 1-indexed
3. Add file existence check at startup

---

### 9. `sequence_intelligence.py` — Score: **69/100**

**Purpose:** Sliding-window detection for card testing, refund fraud, velocity burst, ATO.

| Category | Score | Notes |
|---|---|---|
| Correctness | 14/25 | `merchant_abuse` defined in `_SEQUENCES` but has no implementation; ATO score hardcoded 0.7; velocity burst excludes current txn |
| Reliability | 15/20 | Won't crash; defaults safe |
| Security | 13/15 | No injection |
| Performance | 8/10 | O(n) sliding window |
| Scalability | 8/10 | Stateless per call |
| Maintainability | 6/10 | Dead code in `_SEQUENCES` dict creates false confidence in coverage |
| Testing | 5/10 | `merchant_abuse` has 0% test coverage by definition; ATO constant untested |

**Strengths:**
- Card testing pattern (micro amounts < 5.0 in burst) is well-calibrated
- Refund fraud detection (refund within 24h after purchase) is clever

**Issues:**
- `_SEQUENCES["merchant_abuse"]` is defined but `_check_merchant_abuse()` does not exist — this is dead code that misleads reviewers into thinking merchant abuse is detected
- `_ato_score = 0.7` — always 0.7 regardless of how many ATO signals are present (1 signal = same risk as all signals)
- Velocity burst check: current transaction is NOT counted in `recent_events` — a velocity burst of exactly `max_per_hour` transactions is not detected until the next transaction

**Recommendations:**
1. Implement `_check_merchant_abuse()` or remove the key from `_SEQUENCES`
2. Weight ATO score by number of signals triggered: `ato_score = min(1.0, len(ato_signals_found) * 0.25)`
3. Include current transaction in velocity check: `txn_count = int(features.get("txn_count_1h", 0)) + 1`

---

### 10. `cohort_analysis.py` — Score: **78/100**

**Purpose:** Compares user behavior against peer group averages using normal distribution approximation.

| Category | Score | Notes |
|---|---|---|
| Correctness | 20/25 | Normal CDF approximation is accurate; p99 fallback (avg × 10) is reasonable |
| Reliability | 12/20 | Crash on missing `cohort_profiles.json`; no try/except in `load_cohorts()` |
| Security | 14/15 | Pure computation; file-loaded cohort data |
| Performance | 9/10 | Fast; erf() is O(1) |
| Scalability | 9/10 | `_COHORTS` is read-only after load; concurrent reads are safe |
| Maintainability | 8/10 | Clear logic; self-documenting |
| Testing | 6/10 | File dependency; `normal_cdf` as nested function is untestable in isolation |

**Strengths:**
- `math.erf()` based normal CDF is the correct approach
- Category + time match adjustments (0.85×, 0.90×) reduce false positives elegantly

**Issues:**
- `load_cohorts()` has no try/except — crash if file missing
- `"high_risk"` user type maps to `"working_professional"` fallback — arguably should have its own cohort or flag separately
- `normal_cdf` nested inside `analyze_cohort` cannot be unit tested

**Recommendations:**
1. Wrap file load in try/except with fallback to minimal default cohorts
2. Move `normal_cdf` to module level for testability
3. Log a warning when `user_type` maps to fallback cohort

---

### 11. `risk_delta.py` — Score: **85/100**

**Purpose:** Measures deviation from behavioral baseline across 6 dimensions; produces weighted composite delta score.

| Category | Score | Notes |
|---|---|---|
| Correctness | 19/25 | `_safe_z()` correctly handles near-zero std; `velocity_delta` divides by `max_per_hour` — crashes if 0 |
| Reliability | 16/20 | Most edge cases handled; velocity_delta ZeroDivisionError if `max_per_hour = 0` |
| Security | 14/15 | Pure computation |
| Performance | 10/10 | O(1) |
| Scalability | 10/10 | Stateless |
| Maintainability | 9/10 | Well-documented weights; clear delta naming |
| Testing | 7/10 | Simple enough for thorough unit tests |

**Strengths:**
- `_safe_z()` with 1e-6 guard is the right pattern
- 24-hour wrap-around distance for time delta is correct
- Binary location delta (0.0 / 0.7 / 1.0) is defensible for the use case
- Human-readable `_summarize()` is a nice UX touch

**Issues:**
- `velocity_delta = ... / max_per_hour` — if `profile.thresholds.max_txn_per_hour = 0`, this divides by zero
- Location delta binary steps (0.7 for unknown city, 1.0 for unexpected international) — the jump from known to unknown country is only +0.3

**Recommendations:**
1. Guard: `if max_per_hour <= 0: velocity_delta = 0.0` (or use a sensible default like 10)
2. Consider a 3-level location scale: known_city=0.0, unknown_city=0.5, unexpected_international=1.0

---

### 12. `device_reputation.py` — Score: **79/100**

**Purpose:** Dynamic device trust score with age, fraud history, multi-account, and decay logic.

| Category | Score | Notes |
|---|---|---|
| Correctness | 20/25 | Trust formula is reasonable; `last_seen_ts=0 → 999 days` is conservative/safe |
| Reliability | 14/20 | `float()` coercions protect against type errors; depends on feature_store correctness |
| Security | 14/15 | No direct user input |
| Performance | 8/10 | One async feature_store call |
| Scalability | 9/10 | Stateless beyond feature_store |
| Maintainability | 8/10 | Formula steps are clearly commented |
| Testing | 6/10 | Requires feature_store mock; decay logic untested |

**Strengths:**
- Exponential fraud penalty `min(0.9, fraud_count * 0.3)` is well-calibrated
- Decay factor `1.0 - days_since_seen * 0.002` (0.2% per day) is gentle and appropriate
- `_build_signals()` separation is clean

**Issues:**
- `trust_score` computation can go negative before `max(0.0, ...)` clip — for a device with 3 fraud associations and 3 accounts on a new unknown device: `(0.1 - 0.9 - 0.2) * ~0.5 = -0.5` → clipped to 0.0 (correct behavior, but worth documenting)
- If `feature_store.get_device_reputation()` raises, no error handling in this module

**Recommendations:**
1. Add try/except around the feature_store call with safe defaults on failure
2. Document the worst-case trust formula value in comments

---

### 13. `evidence_builder.py` — Score: **83/100**

**Purpose:** Aggregates all service results into a single `InvestigationPackage` for LLM agents.

| Category | Score | Notes |
|---|---|---|
| Correctness | 21/25 | Comprehensive evidence collection; raw Python list repr in summary lines is slightly unclean |
| Reliability | 17/20 | `dict.get` defaults throughout; won't crash |
| Security | 12/15 | `txn.merchant_name` injected into LLM summary string without sanitization |
| Performance | 9/10 | O(evidence_items) |
| Scalability | 9/10 | Stateless |
| Maintainability | 8/10 | Clear strong/medium/weak categories; self-documenting |
| Testing | 7/10 | Pure function; highly testable |

**Strengths:**
- Single-pass aggregation is the correct architectural pattern (agents never query DB directly)
- `EvidenceStrength` tiers (strong/medium/weak) with explicit reliability scores are well-designed
- Token-efficient summary lines compress context for LLM calls

**Issues:**
- `f"SIGNALS: +{signal_result.get('positive_signals', [])} -{signal_result.get('negative_signals', [])}"` — Python list repr (`['a', 'b']`) is not clean for LLM context; should use `", ".join()`
- `f"USER: {profile.user_type.value}, ..."` includes user profile data in LLM prompt without sanitization — if `merchant_name` contains prompt injection (`"ignore previous instructions"`), it enters the LLM context
- Evidence duplicate risk: `shared_device` and `fraud_ring_detected` are separate evidence items, but `graph_result.get("graph_signals")` is the same value for both

**Recommendations:**
1. Sanitize `txn.merchant_name` before including in `evidence_summary`
2. Replace list repr with `", ".join(signals)` in summary lines
3. Consider deduplicating overlapping evidence items

---

### 14. `evidence_reliability.py` — Score: **92/100**

**Purpose:** Scores and weights evidence items; produces overall evidence verdict.

| Category | Score | Notes |
|---|---|---|
| Correctness | 22/25 | Blended reliability (base×0.4 + type×0.6) is sound; verdict ladder is sensible |
| Reliability | 18/20 | Handles empty evidence list correctly; `net_fraud_confidence` properly clipped |
| Security | 15/15 | Pure computation on internal models |
| Performance | 10/10 | O(evidence_items) |
| Scalability | 10/10 | Stateless |
| Maintainability | 9/10 | Constants well-named; verdict logic is readable |
| Testing | 8/10 | Pure function; highly testable |

**Strengths:**
- Two-table reliability system (`_STRENGTH_BASE` + `_TYPE_RELIABILITY`) with blending is elegant
- `weak_only` flag correctly prevents weak evidence from appearing as "moderate"
- `type_key = item.type.split(":")[0]` correctly handles `trust_signal:known_device` style keys

**Issues:**
- `net_fraud_confidence = min(1.0, max(0.0, total_fraud_weight - total_trust_weight * 0.5))` — the 0.5 discount on trust is arbitrary; should be documented or made configurable
- `evidence_verdict = "insufficient"` when `total_fraud_weight == 0` — correct, but the edge case where `total_fraud_weight > 0` but all items are weak produces `"weak"` which may still trigger action

**Recommendations:**
1. Document why trust weight is discounted by 0.5 in a comment
2. This is the most production-ready service in the codebase — good model for others

---

### 15. `merchant_reputation.py` — Score: **80/100**

**Purpose:** Dynamic merchant trust/risk score from chargeback rate, fraud associations, category, volume.

| Category | Score | Notes |
|---|---|---|
| Correctness | 21/25 | Formula reasonable; penalties and boosts well-calibrated |
| Reliability | 15/20 | `float()` coercions protect; no error handling for feature_store failure |
| Security | 13/15 | `merchant_category.lower()` comparison is safe; no injection vectors |
| Performance | 8/10 | One async call |
| Scalability | 9/10 | Stateless beyond feature_store |
| Maintainability | 8/10 | Clear penalty/boost breakdown |
| Testing | 6/10 | Requires feature_store mock; category penalty untested |

**Strengths:**
- `high_risk_cats` set lookup is O(1) and the category list is appropriate
- `min(0.5, chargeback_rate * 10)` correctly amplifies high chargeback rates
- Volume and diversity boosts are small (max 0.3 combined) — won't override fraud signals

**Issues:**
- If `feature_store.get_merchant_reputation()` raises, no error handling — caller gets exception
- `volume_boost = min(0.2, txn_volume / 10000)` — a merchant with 2000 transactions gets the same boost as one with 1,000,000
- `fraud_penalty = min(0.4, fraud_assoc * 0.1)` — caps at 4 associations (0.4 penalty max), but 100 associations still only gets 0.4

**Recommendations:**
1. Add try/except around feature_store call with safe defaults
2. Use logarithmic volume boost: `min(0.2, math.log10(max(1, txn_volume)) / 5)`

---

### 16. `negative_signals.py` — Score: **75/100**

**Purpose:** Evaluates positive (fraud) and negative (trust) signals; computes net signal risk score.

| Category | Score | Notes |
|---|---|---|
| Correctness | 15/25 | Six signals defined in weight dicts but never triggered in `evaluate_signals()` |
| Reliability | 16/20 | Won't crash; defaults safe |
| Security | 13/15 | Pure computation |
| Performance | 10/10 | O(1) |
| Scalability | 10/10 | Stateless |
| Maintainability | 6/10 | Dead signal definitions create false confidence in coverage |
| Testing | 5/10 | Dead signals imply 0% coverage for defined-but-unimplemented features |

**Strengths:**
- Bidirectional signal system (positive inflates, negative reduces) is architecturally sound
- `max_possible = sum(_POSITIVE_SIGNAL_WEIGHTS.values())` ensures signal_risk_score is always ≤ 100

**Critical Issues — Dead Signal Definitions:**

Defined in `_POSITIVE_SIGNAL_WEIGHTS` but never triggered:
- `"night_transaction_high_amount"` — no time+amount combined check exists
- `"micro_transaction_burst"` — not checked in `evaluate_signals()`
- `"first_time_merchant"` — not checked (there's a separate `features.get("merchant_frequency")` check in `evidence_builder.py`)

Defined in `_NEGATIVE_SIGNAL_WEIGHTS` but never triggered:
- `"recurring_payment_pattern"` — no recurring payment detection
- `"salary_credit_pattern"` — no salary detection logic
- `"within_cohort_normal"` — cohort result is not passed to this function

The function signature doesn't even accept `cohort_result`, so `within_cohort_normal` can *never* be triggered.

**Recommendations:**
1. Either implement the missing signal checks or remove their weight definitions
2. Add `cohort_result` parameter to enable `within_cohort_normal` signal
3. Add `"micro_transaction_burst"` check using `sequence_result` if available

---

## Overall Score Summary

| # | Service | Score | Grade |
|---|---|---|---|
| 1 | `fast_screening.py` | 72 | C |
| 2 | `feature_store.py` | 67 | D |
| 3 | `behavioral_similarity.py` | 74 | C |
| 4 | `fraud_patterns.py` | 75 | C |
| 5 | `consensus_engine.py` | 78 | C+ |
| 6 | `graph_intelligence.py` | **56** | **F** |
| 7 | `geo_velocity.py` | 80 | B- |
| 8 | `kill_chain.py` | 79 | C+ |
| 9 | `sequence_intelligence.py` | 69 | D |
| 10 | `cohort_analysis.py` | 78 | C+ |
| 11 | `risk_delta.py` | 85 | B |
| 12 | `device_reputation.py` | 79 | C+ |
| 13 | `evidence_builder.py` | 83 | B |
| 14 | `evidence_reliability.py` | **92** | **A** |
| 15 | `merchant_reputation.py` | 80 | B- |
| 16 | `negative_signals.py` | 75 | C |
| | **OVERALL AVERAGE** | **76.3** | **C+** |

---

## Top 10 Critical Issues

| Priority | Issue | File | Risk |
|---|---|---|---|
| C-1 | **Unbounded defaultdict growth** in `_device_accounts`, `_ip_accounts`, `_account_txns` — OOM in production | `graph_intelligence.py` | CRITICAL |
| C-2 | **Silent `except Exception: pass`** swallows all NetworkX errors — fraud rings missed with zero warning | `graph_intelligence.py` | HIGH |
| C-3 | **`json.loads()` without try/except** in `get_recent_events()` — one corrupted Redis key crashes all velocity checks | `feature_store.py` | HIGH |
| C-4 | **`print()` instead of `logging`** in feature_store — leaks connection state to stdout; not production-safe | `feature_store.py` | MEDIUM |
| C-5 | **Missing agent sentinel = 50.0** — non-neutral; inflates final risk score for partial agent responses (legitimate transactions skewed toward 50%) | `consensus_engine.py` | HIGH |
| C-6 | **Dead `merchant_abuse` signal** in sequence intelligence — defined, weighted, but never computed | `sequence_intelligence.py` | MEDIUM |
| C-7 | **6 dead signal definitions** in `negative_signals.py` — recurring payment, salary credit, within_cohort_normal cannot fire | `negative_signals.py` | MEDIUM |
| C-8 | **No file-load error handling** in fraud_patterns, kill_chain, cohort_analysis — missing JSON files cause startup crash | Multiple | HIGH |
| C-9 | **`device_novelty` hardcoded denominator** `/ 0.3` in fast_screening — wrong score for any profile with non-0.3 threshold | `fast_screening.py` | MEDIUM |
| C-10 | **`merchant_name` unsanitized in LLM summary** in evidence_builder — potential prompt injection vector | `evidence_builder.py` | MEDIUM |

---

## Top 10 Improvements

| Priority | Improvement | Impact |
|---|---|---|
| I-1 | Replace all unbounded `defaultdict`s in `graph_intelligence.py` with LRU dicts (max 50k entries) + periodic eviction | Prevents production OOM |
| I-2 | Change missing agent sentinel from 50.0 to 0.0 in consensus_engine; add `agents_missing` count to output | Fixes false risk inflation |
| I-3 | Wrap all JSON file loads (fraud_patterns, kill_chain, cohort_analysis) in try/except with fallback + startup health check | Prevents crash-on-deploy |
| I-4 | Replace all `print()` in feature_store with `logging.getLogger(__name__)` | Production log visibility |
| I-5 | Implement `_check_merchant_abuse()` in sequence_intelligence OR remove the dead definition | Closes fraud detection gap |
| I-6 | Add `cohort_result` parameter to `evaluate_signals()` in negative_signals.py; implement remaining 6 dead signals | Completes signal coverage |
| I-7 | Fix `TravelFrequency` enum key mismatch in behavioral_similarity.py using `.value` accessor | Fixes silent wrong scores |
| I-8 | Add try/except around feature_store calls in device_reputation.py and merchant_reputation.py with safe defaults | Resilience against cache failure |
| I-9 | Rename `AgentRisk.confidence` to `agent_weight` in consensus_engine; expose actual LLM confidence separately | Fixes API semantic confusion |
| I-10 | Sanitize `txn.merchant_name` in evidence_builder summary using `sanitize()` from `_agent_base.py` | Closes prompt injection vector |

---

## Architecture Assessment

### What Works Well
- **Single-pass evidence aggregation** (evidence_builder.py) is the right architecture — agents never query DB directly
- **Three-tier feature store fallback chain** (Redis → fakeredis → DictRedis) is operationally sound
- **Evidence reliability framework** (evidence_reliability.py) is the standout service — production-ready
- **Bidirectional signal system** (negative_signals.py concept) is architecturally sound even if implementation is incomplete
- **Kill chain stage amplification** correctly models progressive attack severity

### Architectural Debt
- **FraudGraph is a singleton with unbounded state** — this is the single biggest production risk. It needs either an external graph DB (Redis Graph, Neo4j) or bounded in-memory state with eviction.
- **No centralized error handling** — each service independently fails or crashes on missing data files. A startup health check / warm-up routine should validate all JSON data files.
- **Consensus engine conflates weight and confidence** — downstream consumers cannot distinguish "this agent is weighted 20%" from "this agent is 20% confident."
- **Dead code in signal detection** (merchant_abuse, 6 negative signals) creates false confidence in coverage completeness.

---

## Production Readiness Assessment

| Dimension | Status | Notes |
|---|---|---|
| Core fraud detection logic | READY | Formulas are sound; coverage is broad |
| Memory safety | NOT READY | FraudGraph OOM risk blocks production |
| Error handling | PARTIAL | 5+ crash-on-missing-file paths; silent exception in graph |
| Observability | PARTIAL | Agents log correctly; services use print() or nothing |
| False positive rate | AT RISK | Dead signals + non-neutral sentinel inflate risk scores |
| Security | PARTIAL | Prompt injection vector in evidence_builder; otherwise OK |
| Test coverage | PARTIAL | Core paths tested; edge cases and dead code uncovered |

**Overall Production Readiness: 65%**

---

## Remediation Effort Estimate

| Sprint | Focus | Effort | Target Score |
|---|---|---|---|
| Sprint 3 (1 week) | C-1 through C-4: FraudGraph LRU, silent exception, json.loads safety, print→logging | 5 days | 82/100 |
| Sprint 4 (1 week) | C-5 through C-8: sentinel fix, dead signals, file-load safety, missing implementations | 5 days | 88/100 |
| Sprint 5 (1 week) | I-7 through I-10: enum fix, feature_store resilience, field rename, sanitization | 3 days | 92/100 |

**Total to reach 90+: ~13 developer-days**

---

## Final Verdict

> **Services Layer: Architecturally Sound, Not Production Ready**
> 
> The services layer demonstrates strong design intent — evidence aggregation, bidirectional signals, three-tier caching, and a robust reliability framework are all correct patterns. However, `graph_intelligence.py` alone blocks production: its unbounded memory growth will cause an OOM event within days of real load, and its silent exception swallowing means fraud rings are missed without any alert. Combined with 6+ dead signal definitions, a non-neutral missing-agent sentinel, and three services that crash on missing JSON files, the layer needs one focused remediation sprint before it is safe to deploy.
> 
> **Score: 76/100 — Requires Sprint 3 Before Production**
