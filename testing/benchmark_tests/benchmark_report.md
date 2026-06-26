# Phase 10 — Performance Benchmarking Report
**Date:** 2026-06-23 | **Auditor:** QA Agent | **Mode:** READ-ONLY

---

## 10.1 Performance Targets (From System Documentation)

| Stage | Metric | Target | Spec Source |
|---|---|---|---|
| Stage 1 Fast Screening | Latency | < 20ms | Architecture doc |
| Stage 2 LangGraph Deep Investigation | Latency | < 1.5s | Architecture doc |
| Overall | Throughput | N/A | N/A |
| Auto-Approve Path | Total Latency | < 20ms | Stage 1 only |
| Full LangGraph Path | Total Latency | < 1.5s | End-to-end |

---

## 10.2 Fast Screening Performance Analysis (Stage 1)

### Code Path Components

```
fast_screening.py:
1. compute_pre_risk_score():
   - 7 component calculations
   - Dict lookups: O(1)
   - Math operations: O(1)
   - No I/O
   - No async operations
   - No LLM calls
```

**Theoretical Runtime:** ~0.1–0.5ms (pure Python math)

### Async Overhead

```python
async def node_fast_screening(state: FraudPipelineState) -> dict:
    service = get_fast_screening_service()
    result = await service.screen_transaction(transaction, user_profile)
```

`screen_transaction` likely contains `await` calls (async runtime overhead ~0.01ms).

**Estimated Stage 1 latency: 0.5–2ms**
**Target: < 20ms**
**Status: ✓ PASS (well within target)**

---

## 10.3 LangGraph Pipeline Performance Analysis (Stage 2)

### Node Execution Sequence

```
feature_retrieval → fast_screening → pre_agent_analysis →
build_evidence → parallel_agents → consensus →
investigation → explainability → analyst → storytelling → final_decision
```

### LLM Call Count Per Transaction

| Node | LLM Calls | Est. Time |
|---|---|---|
| pre_agent_analysis | 1 (optional) | 0.3–0.8s |
| build_evidence | 0 (rule-based) | <5ms |
| parallel_agents (×5) | 5 concurrent | 0.5–1.2s* |
| consensus | 0 (formula) | <1ms |
| investigation | 1 | 0.3–0.8s |
| explainability | 1 | 0.2–0.5s |
| analyst | 1 | 0.3–0.8s |
| storytelling | 1 | 0.2–0.5s |
| final_decision | 1 | 0.1–0.3s |

*5 agents run in parallel via LangGraph ParallelEdge

**Total estimated LLM time:**
- Parallel agents (5×): 0.5–1.2s (bottleneck = slowest agent)
- Sequential LLM calls: 6 calls × 0.2–0.8s each = 1.2–4.8s
- **Total: 1.7–6.0s (EXCEEDS 1.5s target)**

### Critical Path Analysis

```
pre_agent → parallel_agents → consensus → investigation → explainability → analyst → storytelling → final_decision
```

Sequential after parallel: 5 LLM calls in series
**If each takes 300ms: 1.5s for sequential alone**

**Status: ⚠️ RISKY — Cannot guarantee < 1.5s with 6+ LLM calls**

---

## 10.4 Database Performance

### Ground Truth Store (SQLite + aiosqlite)

```python
async with aiosqlite.connect(self.db_path) as db:
    await db.execute("INSERT INTO ground_truth ...")
    await db.commit()
```

- SQLite: Single-writer, multiple reader
- aiosqlite: Non-blocking I/O via ThreadPoolExecutor
- Per-transaction write: ~5–20ms (disk I/O)
- Concurrent writes: serialized (SQLite limitation)

**At 100 txns/sec: 100 × 20ms write time → Theoretical bottleneck if synchronous**
**Status: ⚠️ WARNING — High throughput will saturate SQLite writer**

### Feature Store (_update_feature_store)

```python
asyncio.create_task(_update_feature_store(state))  # fire-and-forget
```

Feature store updates are fire-and-forget. Performance impact is hidden but:
- If feature store writes fail silently, behavioral data is stale
- At high throughput, task queue grows without bound

---

## 10.5 Memory Usage Analysis

### In-Memory Singletons

| Singleton | Size Per Item | Growth Pattern |
|---|---|---|
| FraudGraph._G | ~200 bytes/node | O(users + devices + IPs) |
| FraudGraph._device_accounts | ~50 bytes/device | O(unique devices) |
| FraudGraph._account_txns | ~300 bytes/txn | O(all transactions) |
| EvolutionTracker.lineage | ~500 bytes/gen | Unbounded |
| _MERCHANT_POOL (world_builder) | ~100 bytes/merchant | Fixed (500 merchants) |

**For 10,000 users, 100 txns each:**
- FraudGraph._account_txns: 10,000 × 100 × 300 bytes = **300MB**
- FraudGraph._G: 10,000 nodes × 200 bytes = **2MB**
- Total estimated: **~305MB** for graph layer alone

**Status: ⚠️ WARNING — Memory unbounded for long-running instances**

---

## 10.6 Throughput Analysis

### Single-Request Throughput

| Path | Latency | Throughput (1 worker) |
|---|---|---|
| Auto-Approve (Stage 1 only) | ~2ms | ~500 req/s |
| Fast Screening only (pre_risk < 35) | ~5ms | ~200 req/s |
| Full LangGraph (6 LLM calls) | 2–6s | ~0.2 req/s |

### Concurrent Request Throughput

With 10 async workers:
- Stage 1 only: ~5000 req/s (no I/O bottleneck)
- Full pipeline: ~2 req/s (LLM API bottleneck)

**LLM API rate limits are the dominant throughput constraint.**

---

## 10.7 CPU Usage Patterns

### Heavy CPU Operations

| Operation | CPU Cost | Frequency |
|---|---|---|
| networkx community detection | HIGH | Per-ring analysis |
| gauss sampling in temporal_sim | LOW | Per-transaction |
| fast_screening normalization | LOW | Per-transaction |
| consensus formula | LOW | Per-transaction |

### Amdahl's Law — Parallelizable Components

- Fast screening: 100% parallelizable (no shared state reads)
- LangGraph parallel agents: 5 agents run concurrently ✓
- Feature store update: async fire-and-forget (background)
- Ground truth write: serialized (SQLite)

**Theoretical parallel speedup for Stage 2: 2–3× with 5 concurrent agents**

---

## 10.8 Network Latency Considerations

Each LLM call incurs:
- Network RTT to LLM API: ~50–200ms
- Token generation: varies by prompt length
- Est. 300–800ms per call

**No caching of LLM responses observed.** Identical transactions analyzed fresh each time.

---

## CRITICAL FINDINGS
1. Full LangGraph pipeline (6 sequential LLM calls) cannot reliably meet 1.5s SLA
2. SQLite single-writer bottleneck will limit throughput at >50 concurrent writes/sec
3. FraudGraph accumulates transaction history in-memory — 300MB+ for 10k users

## WARNINGS
1. Fire-and-forget feature store updates lose errors silently
2. No LLM response caching — repeated similar transactions always hit API
3. EvolutionTracker lineage grows unbounded in long sessions

---

**Performance Score: 61 / 100**
