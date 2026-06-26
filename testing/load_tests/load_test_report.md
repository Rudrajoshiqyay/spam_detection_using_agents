# Phase 16 — Load Testing Report
**Date:** 2026-06-23 | **Auditor:** QA Agent | **Mode:** READ-ONLY

---

## 16.1 Load Testing Framework

**Method:** Code-path analysis (no live execution)
**Targets:** 100, 1,000, 10,000 transactions/second
**Focus:** Bottleneck identification, scalability limits, failure modes

---

## 16.2 System Architecture Under Load

### FastAPI + Uvicorn Threading Model
```python
# main.py — standard FastAPI with async endpoints
@app.post("/detect")
async def detect_fraud(request: FraudDetectionRequest):
    result = await pipeline.process_transaction(...)
```

FastAPI uses asyncio event loop (single thread) + uvicorn workers.
Default workers: typically 1–4 per process.

**Throughput ceiling (single process):** depends on I/O-bound vs CPU-bound ratio.
- Pure I/O (LLM API calls): can multiplex many concurrent requests
- CPU-bound (fast screening math): limited by GIL for heavy parallel use

---

## 16.3 Load Test: 100 Transactions/Second

### Stage 1 Only (Auto-Approve)
- Fast screening: ~2ms per transaction
- Ground truth write: ~10ms per transaction (SQLite)
- **Bottleneck: SQLite single-writer at 100 writes/sec = 1,000ms of write time**

**Analysis:**
- SQLite write serialization: 100 txns × 10ms = 1,000ms write load per second
- If ground truth writes block: queue builds up
- If fire-and-forget: writes succeed but lag by 1–2 seconds

**Expected behavior at 100 TPS:**
- If 60% auto-approve: 60 fast (2ms) + 40 LangGraph (1.5–6s)
- 40 concurrent LangGraph requests = 40 × 5 concurrent LLM calls = 200 concurrent LLM API calls
- **LLM API rate limits: most APIs limit to 60–100 RPM per key**
- 200 concurrent calls → immediate rate limit throttling

**Status at 100 TPS: ⚠️ WARNING — LLM API rate limits hit within seconds**

---

## 16.4 Load Test: 1,000 Transactions/Second

### Database Bottleneck (Critical)
```
1,000 TPS × 10ms write = 10,000ms = 10 seconds of write queued per second
SQLite cannot handle this: queue grows without bound
```

**SQLite write queue at 1000 TPS:** completely saturated
**aiosqlite ThreadPoolExecutor default workers:** 10–20
**Effective write throughput: ~100–200 writes/sec**
**At 1,000 TPS: 800+ writes/sec dropped or queued indefinitely**

### LLM API Bottleneck (Critical)
```
1,000 TPS × 40% escalation = 400 LangGraph runs/sec
400 × 6 LLM calls = 2,400 LLM API calls/sec
Most LLM APIs: 1,000–10,000 tokens/min limit (not calls/sec)
```

**Status at 1,000 TPS: FAIL — SQLite saturated, LLM API far exceeded**

---

## 16.5 Load Test: 10,000 Transactions/Second

### All Bottlenecks Hit Simultaneously

| Bottleneck | Limit | At 10,000 TPS | Status |
|---|---|---|---|
| SQLite writes | ~200 writes/sec | 10,000/sec needed | FAIL (50× over) |
| LLM API calls | varies | 24,000/sec needed | FAIL (completely impractical) |
| Graph singleton | In-memory dict | Memory explosion | FAIL |
| FastAPI event loop | ~10,000 async tasks | Queue overflow | CRITICAL |
| Feature store | depends | Fire-and-forget accumulation | CRITICAL |

**Status at 10,000 TPS: COMPLETE FAILURE — System cannot function at this scale**

---

## 16.6 Memory Growth Under Load

### FraudGraph Memory Growth

```python
self._account_txns[user_id].append(txn_data)
# keeps ALL transactions in memory, no eviction
```

At 10,000 TPS for 1 hour:
- 10,000 × 3,600 = 36,000,000 transactions in memory
- At 300 bytes each = 10.8 GB
- **Memory exhaustion: ~30–60 minutes at 10,000 TPS**

At 1,000 TPS for 1 hour:
- 1,080,000 transactions = 324MB → manageable
- But grows indefinitely

---

## 16.7 Connection Pool Analysis

### aiosqlite Connection Pattern
```python
async with aiosqlite.connect(self.db_path) as db:
    await db.execute(...)
    await db.commit()
```

Each call opens+closes a connection. SQLite doesn't have a connection pool.
- Connection overhead: ~1–5ms per transaction
- At high throughput: connection overhead dominates

**Recommendation (not actionable in audit mode):** Connection pooling or batch writes would help.

---

## 16.8 Queue and Backpressure Analysis

### No Backpressure Mechanism

FastAPI has no built-in rate limiting for `/detect`. Under overload:
1. Request queue grows without bound
2. asyncio task queue fills
3. Eventually: OOM or connection timeouts

**Estimated queue overflow at:** ~500–1,000 concurrent requests (depending on memory limits)

### Fire-and-Forget Task Accumulation
```python
asyncio.create_task(_update_feature_store(state))
```

Each failed task stays in the task pool until GC. At high load:
- 10,000 tasks/sec × tasks not completing → task pool grows
- Each pending task holds state dictionary (~10KB) in memory
- 10,000 tasks × 10KB = 100MB/sec accumulation rate

---

## 16.9 Load Test Summary

| Target | Auto-Approve | LangGraph | Ground Truth | Status |
|---|---|---|---|---|
| 100 TPS | ✓ (~2ms) | ⚠️ rate limit risk | ⚠️ near SQLite limit | MARGINAL |
| 1,000 TPS | ✓ | ✗ rate limited | ✗ saturated | FAIL |
| 10,000 TPS | ⚠️ (memory) | ✗ completely blocked | ✗ unusable | CRITICAL FAIL |

**Practical throughput limit: ~100–200 TPS (auto-approve only) or ~5–10 TPS (full LangGraph pipeline)**

---

## CRITICAL FINDINGS
1. SQLite single-writer bottleneck: saturates at ~200 writes/sec
2. LLM API calls dominate at any sustained load above 10 TPS (full pipeline)
3. No memory eviction for FraudGraph: OOM possible at sustained high TPS

## WARNINGS
1. No rate limiting or backpressure mechanism in FastAPI
2. Fire-and-forget tasks accumulate without bound under load
3. Connection opens per write (no connection pooling)
4. No horizontal scaling mechanism for single-process singletons (FraudGraph)

---

**Load Test Score: 42 / 100**
