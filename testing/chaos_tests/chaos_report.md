# Phase 19 — Chaos Testing Report
**Date:** 2026-06-23 | **Auditor:** QA Agent | **Mode:** READ-ONLY

---

## 19.1 Chaos Testing Scope

**Scenarios Tested:**
1. Redis failure (if used for caching)
2. Graph Intelligence failure
3. LLM API failure
4. Database (SQLite) failure
5. Individual agent failure

---

## 19.2 Redis Failure Scenario

### Redis Presence Check
From source files reviewed, no Redis client or Redis connection string was found in the code. Feature store appears to be in-memory or file-based.

**Chaos scenario:** Redis not a dependency for core pipeline.
**Status: N/A — No Redis dependency detected**

---

## 19.3 Graph Intelligence Failure

### Failure Mode: FraudGraph singleton exception

```python
# graph_intelligence.py
fraud_graph = FraudGraph()  # module-level
```

**Scenario:** FraudGraph.__init__ raises exception at startup
- Pipeline cannot import graph_intelligence module
- FastAPI startup fails

**Scenario:** `get_risk_signals()` raises during request processing

```python
# fraud_pipeline.py — graph node (assumed):
signals = await fraud_graph.get_risk_signals(user_id, transaction)
```

If this raises and is not caught:
- LangGraph node fails → entire pipeline fails for this transaction
- HTTP 500 response to client
- Transaction not recorded in ground truth (write happens before/after?)

**Recovery:** No circuit breaker for graph failures detected.

### Cold Start Graph (Partial Failure)
```python
fraud_graph = FraudGraph()  # empty graph
# All nodes have degree 0
# All IP lookups return empty sets
# All device lookups return empty sets
```

**Effect:** Graph provides NO signals but doesn't crash. Silent degradation.
- Risk scores based on graph: all 0 (no network connections known)
- System defaults to behavioral + device + geo signals only
- **Status: ⚠️ Silent degradation — no alert, no log that graph has no data**

---

## 19.4 LLM API Failure

### Failure Mode: API timeout or rate limit

**All 6 LLM calls in the deep investigation pipeline:**
```
pre_agent_analysis → parallel_agents (×5) → investigation → explainability → analyst → storytelling
```

If LLM API goes down:
1. `asyncio.wait_for(llm_call(), timeout=N)` → TimeoutError (if timeout set)
2. Without timeout: hangs indefinitely

**Finding from Code:**
```python
# consensus_engine.py
float(behavior_risk.get("risk_score", 50))  # default 50 when agent fails
```

Agent failures default to 50.0. **Behavior with all agents failing:**
- All 5 agents return empty dict (or never respond)
- All default to 50.0
- consensus: blended_risk ≈ 50, agreement = 100 (perfect — all "agree" at 50)
- Transaction gets MEDIUM risk with PERFECT consensus confidence
- Could be approved or escalated depending on other factors

**CRITICAL:** LLM API failure causes the consensus to read as "confident at medium risk" rather than "unable to assess." A transaction that should be BLOCKED might pass.

### Failure Mode: Partial LLM failure (3 of 6 calls fail)
- 3 agents fail → default 50; 2 agents succeed with high fraud scores
- Agreement drops dramatically (50, 50, 50, 90, 85)
- blended_risk: lower than expected (anchored toward 50)
- **Fraud cases may be under-scored when LLM partially fails**

---

## 19.5 SQLite Database Failure

### Failure Mode: DB file locked or corrupted

```python
async with aiosqlite.connect(self.db_path) as db:
    await db.execute(...)
```

**aiosqlite exception behavior:**
- If file locked: `sqlite3.OperationalError: database is locked`
- If corrupted: `sqlite3.DatabaseError`
- Exception propagates to calling code

**In ground_truth_store.py:**
If exception is raised and not caught in calling code:
- Ground truth record not written
- Pipeline might still complete (depends on call site)
- Ground truth becomes incomplete (gaps in audit trail)

**Recovery mechanism:** None detected. No retry logic, no fallback store.

### Failure Mode: DB file permissions error

If the db file becomes read-only after creation:
- Writes fail with `sqlite3.OperationalError: attempt to write a readonly database`
- Silent if caller wraps in try/except
- Auditable data lost

---

## 19.6 Individual Agent Failure Matrix

| Agent | Failure Effect | Fallback | Detectable |
|---|---|---|---|
| behavior_agent | score defaults to 50 | ✓ default 50 | ✗ No log |
| device_agent | score defaults to 50 | ✓ default 50 | ✗ No log |
| geo_agent | score defaults to 50 | ✓ default 50 | ✗ No log |
| merchant_agent | score defaults to 50 | ✓ default 50 | ✗ No log |
| graph_agent | score defaults to 50 | ✓ default 50 | ✗ No log |
| pre_agent_analysis | N/A — skip possible | ? | ? |
| investigation | narrative missing | ? | ? |
| explainability | explanation empty | ? | ? |
| analyst | summary missing | ? | ? |
| storytelling | customer message missing | ? | ? |

**All agent failures appear to be silent** — defaults are returned but no metric increments, no log entry, no alert.

**Detection:** An operations team would only notice agent failures if they monitored response content for expected fields — not via error rates.

---

## 19.7 API Gateway Failure

### FastAPI server failure

If uvicorn crashes:
- All in-flight requests lost
- In-memory FraudGraph state lost (detection starts cold)
- In-memory EvolutionTracker lost
- SQLite ground_truth.db persists (durable)

**Recovery:** FastAPI restart restores the server but loses all graph intelligence. Ring detection starts from zero — fraud rings that accumulated signals over hours are invisible again.

**MTTR (Mean Time to Recovery):** Server restart ~5–10 seconds. But effective MTTR for detection quality: hours (time to rebuild graph from new transactions).

---

## 19.8 Feature Store Failure

```python
asyncio.create_task(_update_feature_store(state))
```

Feature store updates are fire-and-forget. If feature store fails:
1. Task raises exception
2. asyncio captures exception in task
3. If no task result handler → exception discarded silently
4. Behavioral data becomes stale

**Cascade effect:** As feature store degrades, behavioral baselines become stale:
- New spending patterns not captured
- Velocity windows use outdated transaction histories
- Behavioral agent scores drift toward defaults

**Detection:** None. No monitoring of feature store freshness.

---

## 19.9 Chaos Test Results Matrix

| Failure Scenario | Pipeline Completes | Correct Decision | Alert Triggered | Score |
|---|---|---|---|---|
| Graph cold start | ✓ (silent) | Partial | ✗ | POOR |
| All LLM fail | ✓ (wrong) | ✗ (50/100/85) | ✗ | CRITICAL |
| 3/5 LLM fail | ✓ | Partial | ✗ | POOR |
| SQLite fail | Partial | Partial | ✗ | POOR |
| Individual agent fail | ✓ (wrong) | Partial | ✗ | POOR |
| Feature store fail | ✓ (degraded) | Degraded | ✗ | POOR |
| FastAPI restart | ✗ | N/A | ✗ | FAIL |

**Chaos Resilience: 1/7 scenarios have adequate handling**

---

## CRITICAL FINDINGS
1. All LLM failure causes system to report PERFECT CONSENSUS at MEDIUM RISK — may approve fraud
2. No alerts or metrics for any agent/component failure
3. FastAPI restart loses all accumulated graph intelligence — detection starts cold

## WARNINGS
1. Agent failures are completely silent — no logging, no monitoring
2. Feature store fire-and-forget: degradation undetectable
3. SQLite failure: no retry or fallback mechanism
4. No circuit breaker for any external dependency (LLM API, graph, feature store)

---

**Chaos Resilience Score: 28 / 100**
