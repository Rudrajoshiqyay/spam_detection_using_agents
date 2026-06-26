# Phase 6 — Graph Intelligence Testing Report
**Date:** 2026-06-23 | **Auditor:** QA Agent | **Mode:** READ-ONLY

---

## 6.1 Graph Architecture Overview

**Simulation Layer (fraud_ring_agent.py):** Directed graphs (nx.DiGraph) per ring
**Detection Layer (graph_intelligence.py):** Single in-memory undirected graph (nx.Graph)

**CRITICAL MISMATCH:** Simulation uses DiGraph; detection uses Graph. Edge direction information is lost when ring transactions are processed by the detection pipeline.

---

## 6.2 Ring Graph Metrics (Theoretical)

### Shared Device Ring (5 users, 2 shared devices)
| Metric | Value | Assessment |
|---|---|---|
| Nodes | 7 | OK |
| Edges | 5 (user→device) | Low |
| Density | 0.12 | Low (expected for ring) |
| Avg Degree | 1.4 | Very low |
| Community Count | 1 | OK |
| Ring Topology | Star (2 shared hubs) | ✓ Realistic |

### IP Cluster Ring (6 users, 6 IPs)
| Metric | Value | Assessment |
|---|---|---|
| Nodes | 12 | OK |
| Edges | 6 (user→ip) | Very low density |
| Density | 0.05 | Very sparse |
| **IP Graph-to-Transaction Match** | **BROKEN** | **CRITICAL** |

### Merchant Ring (5 users, 1 merchant)
| Metric | Value | Assessment |
|---|---|---|
| Nodes | 6 | OK |
| Edges | 5 (user→merchant) | OK |
| Density | 0.17 | OK |
| Topology | Perfect star | ✓ Easy to detect |

### Mule Chain Ring (4 users)
| Metric | Value | Assessment |
|---|---|---|
| Nodes | 4 | OK |
| Edges | 3 (user→user transfers) | OK |
| Topology | Linear chain | ✓ Realistic |
| Amount decay | 0.9^i | OK (realistic fee model) |

### Multi-Vector Ring
| Metric | Value | Assessment |
|---|---|---|
| Nodes | 0 (no graph built) | **CRITICAL** |
| Edges | 0 | **CRITICAL** |
| Graph Intelligence Detection | **IMPOSSIBLE** | **CRITICAL** |

---

## 6.3 Detection Graph Analysis (fraud_intelligence.py)

### Shared Device Detection
```python
device_users = self._device_accounts.get(device_id, set())
shared_device_count = len(device_users) - 1
if shared_device_count >= 2:
    risk_score += min(40.0, shared_device_count * 15)
```

- Threshold: ≥2 other accounts using same device
- Risk addition: 15 per extra account, max 40
- **Assessment:** Reasonable. Would catch shared_device_ring (3–8 users on same device).

### IP Cluster Detection
```python
ip_users = self._ip_accounts.get(ip_address, set())
if shared_ip_count >= 3:
    risk_score += min(25.0, shared_ip_count * 8)
```

- Threshold: ≥3 other accounts on same IP
- **Assessment:** Correct threshold, but the 192.168.x.x IPs in synthetic rings don't match public IPs. If detection uses the same IP from the transaction record (which is the graph IP that differs from the transaction IP), this detection fails.

### Mule Network Detection
```python
txns = self._account_txns.get(user_id, [])
if len(txns) >= 3:
    amounts = [t["amount"] for t in txns[-10:]]
    if max(amounts) > sum(amounts[:-1]) * 0.8:
        signals.append("mule_network_pattern:single_large_outflow")
        risk_score += 25.0
```

**Issue:** This condition `max(amounts) > sum(amounts[:-1]) * 0.8` checks if the largest transaction exceeds 80% of all other recent transactions combined. This only fires when there's one unusually large outflow relative to all others. This is a very specific pattern that would miss:
- Cases where multiple large transactions occur
- Mule chains where amounts are similar across hops

### Centrality Score
```python
deg = self._G.degree(user_id)
centrality_score = min(1.0, deg / 20.0)
```

Degree centrality proxy: score = degree/20, capped at 1.0. A user with 10 connections gets centrality 0.5. Risk added if > 0.5.

**Assessment:** Simple but effective for high-degree nodes. Legitimate users with many merchants/devices might have false positives here.

### Community Detection
No community detection algorithm (Louvain, Girvan-Newman) is implemented. The "circular transaction" check is a manual triangle count — not true community detection.

---

## 6.4 Bug Analysis

### BUG: IP Cluster Ring IP Mismatch
```python
# Ring graph:
ring.link_ip(uid, _shared_subnet_ip(subnet))  # IP = A

# Transaction dict:
txns.append({"ip_address": _shared_subnet_ip(subnet), ...})  # IP = B (new call)
```

Two independent calls to `_shared_subnet_ip(subnet)` generate different IPs. The graph edge `user→IP_A` exists but the transaction records `IP_B`. The detection graph's `_ip_accounts[IP_B]` will only contain one user (current), missing the ring signal.

**Expected:** Shared IP cluster detection fires
**Actual:** No cluster detected (IPs don't match)

### BUG: Multi-Vector Ring No Graph
```python
def generate_multi_vector_ring(size=None):
    sd = generate_shared_device_ring(size=size // 2)
    ip = generate_ip_cluster_ring(size=size // 2)
    return {
        "ring_id": ring_id,
        # Missing: edges, node_count, edge_count, FraudRingGraph
    }
```

No NetworkX graph constructed. When this ring data reaches the detection pipeline, no graph signals are available.

---

## 6.5 Connected Components Analysis

For a correctly-built multi-vector ring (theoretical):
- 6 users + 2 shared devices + 6 IPs = 14 nodes
- 6 (device edges) + 6 (IP edges) = 12 edges
- Expected: 1 connected component (fully connected ring)
- Actual (with bug): 0 graph nodes

---

## 6.6 Graph Persistence Issue

```python
fraud_graph = FraudGraph()  # module-level singleton, in-memory
```

**Issue:** Graph data is held entirely in RAM. On server restart:
- All accumulated graph intelligence is lost
- Fraud ring detection starts from zero
- Historical shared-device patterns are invisible to new sessions

**Impact:** In production, rings that operate across multiple days would be fully detectable on day 1 but completely invisible after each restart. This severely limits ring detection in persistent deployments.

---

## CRITICAL FINDINGS
1. Multi-vector ring generates no graph structure — most complex ring type is undetectable
2. IP cluster ring: graph IP ≠ transaction IP — cluster detection broken
3. Detection graph is undirected; simulation rings are directed — direction information lost
4. Graph is not persisted — ring detection resets on restart

## WARNINGS
1. Mule network detection formula too specific — misses multi-transaction mule patterns
2. No true community detection algorithm implemented
3. Shared device ring and mule chain hardcode gig_worker persona
4. Fixed 6h/8h timing cadences create artificial regularity

---

**Graph Integrity Score: 65 / 100**
