"""
Graph Intelligence Layer — NetworkX-based fraud network analysis.

Detects: Fraud Rings, Shared Devices, Shared IPs, Mule Networks,
         Circular Transactions, Coordinated Campaigns.

Latency target: < 50 ms (in-memory graph, periodic refresh).
Memory: bounded by _MAX_GRAPH_KEYS (default 10,000) with LRU eviction per
        lookup table.  Evictions are counted and exposed via get_metrics().
"""

import logging
import time
from collections import OrderedDict, deque
from typing import Any, Dict

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False

_logger = logging.getLogger(__name__)

# Maximum distinct keys stored per lookup table before LRU eviction kicks in.
# Tune via FraudGraph(max_keys=...) or patch this for tests.
_MAX_GRAPH_KEYS: int = 10_000
# Ring buffer depth for per-user transaction history
_MAX_TXNS_PER_USER: int = 100


class _BoundedLookup:
    """
    Dict of sets with LRU eviction on the key space.

    Prevents unbounded memory growth from unseen devices / IPs / merchants.
    When `maxkeys` is reached the least-recently-used key is evicted.
    Thread-safety: not provided here — callers must hold an external lock
    if concurrent writes are expected.
    """

    def __init__(self, maxkeys: int, name: str = ""):
        self._data: OrderedDict[str, set] = OrderedDict()
        self._maxkeys = maxkeys
        self._eviction_count = 0
        self._name = name

    def add(self, key: str, value: str) -> None:
        if key in self._data:
            self._data.move_to_end(key)
        else:
            if len(self._data) >= self._maxkeys:
                evicted_key, _ = self._data.popitem(last=False)
                self._eviction_count += 1
                _logger.debug(
                    "GraphIntelligence._BoundedLookup[%s]: evicted key=%r "
                    "(total_evictions=%d size=%d)",
                    self._name, evicted_key, self._eviction_count, len(self._data),
                )
            self._data[key] = set()
        self._data[key].add(value)

    def get(self, key: str, default: Any = None) -> Any:
        if key in self._data:
            self._data.move_to_end(key)   # count reads as "recently used"
            return self._data[key]
        return default

    def __len__(self) -> int:
        return len(self._data)

    @property
    def eviction_count(self) -> int:
        return self._eviction_count


class FraudGraph:
    def __init__(
        self,
        max_keys: int = _MAX_GRAPH_KEYS,
        max_txns_per_user: int = _MAX_TXNS_PER_USER,
    ):
        self._max_keys = max_keys
        self._max_txns = max_txns_per_user

        if HAS_NX:
            self._G = nx.Graph()
        else:
            self._G = None

        # Bounded lookup tables: external-id → set of user_ids
        self._device_accounts = _BoundedLookup(max_keys, "device_accounts")
        self._ip_accounts = _BoundedLookup(max_keys, "ip_accounts")
        self._merchant_accounts = _BoundedLookup(max_keys, "merchant_accounts")

        # Per-user transaction ring buffer (bounded by max_txns_per_user)
        # Also LRU-bounded on the user_id key space to cap total users in memory.
        self._account_txns: OrderedDict[str, deque] = OrderedDict()
        self._txn_key_eviction_count = 0

        self._fraud_flags: set = set()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_user_txns(self, user_id: str) -> deque:
        """LRU-bounded lookup for per-user transaction ring buffer."""
        if user_id in self._account_txns:
            self._account_txns.move_to_end(user_id)
        else:
            if len(self._account_txns) >= self._max_keys:
                evicted, _ = self._account_txns.popitem(last=False)
                self._txn_key_eviction_count += 1
                _logger.debug(
                    "GraphIntelligence._account_txns: evicted user=%r "
                    "(total_evictions=%d)",
                    evicted, self._txn_key_eviction_count,
                )
            self._account_txns[user_id] = deque(maxlen=self._max_txns)
        return self._account_txns[user_id]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_transaction(
        self,
        user_id: str,
        device_id: str,
        ip_address: str,
        merchant_id: str,
        amount: float,
        timestamp: float,
        is_fraud: bool = False,
    ) -> None:
        self._device_accounts.add(device_id, user_id)
        self._ip_accounts.add(ip_address, user_id)
        self._merchant_accounts.add(merchant_id, user_id)
        self._get_user_txns(user_id).append({
            "merchant": merchant_id,
            "amount": amount,
            "ts": timestamp,
        })
        if is_fraud:
            self._fraud_flags.add(user_id)

        if not HAS_NX or self._G is None:
            return

        for node, ntype in [
            (user_id, "user"),
            (device_id, "device"),
            (merchant_id, "merchant"),
            (ip_address, "ip"),
        ]:
            if not self._G.has_node(node):
                self._G.add_node(node, node_type=ntype)

        self._G.add_edge(user_id, device_id, edge_type="uses_device")
        self._G.add_edge(user_id, ip_address, edge_type="uses_ip")
        self._G.add_edge(user_id, merchant_id, edge_type="transacts_at")

    def analyze(
        self, user_id: str, device_id: str, ip_address: str, merchant_id: str
    ) -> Dict[str, Any]:
        t0 = time.perf_counter()
        signals = []
        risk_score = 0.0

        # --- Shared device detection ---
        device_users = self._device_accounts.get(device_id, set())
        shared_device_count = len(device_users) - 1  # exclude current user
        if shared_device_count >= 2:
            signals.append(f"device_shared_by_{shared_device_count + 1}_accounts")
            risk_score += min(40.0, shared_device_count * 15)

        # --- Shared IP detection ---
        ip_users = self._ip_accounts.get(ip_address, set())
        shared_ip_count = len(ip_users) - 1
        if shared_ip_count >= 3:
            signals.append(f"ip_shared_by_{shared_ip_count + 1}_accounts")
            risk_score += min(25.0, shared_ip_count * 8)

        # --- Fraud association ---
        fraud_neighbors = (device_users or set()) | (ip_users or set())
        fraud_assoc = sum(1 for u in fraud_neighbors if u in self._fraud_flags)
        if fraud_assoc > 0:
            signals.append(f"connected_to_{fraud_assoc}_flagged_account(s)")
            risk_score += fraud_assoc * 20

        # --- Merchant concentration ---
        merchant_users = self._merchant_accounts.get(merchant_id, set())
        if len(merchant_users) > 5:
            signals.append(f"merchant_used_by_{len(merchant_users)}_accounts")
            risk_score += min(15.0, len(merchant_users) * 2)

        # --- Graph metrics (NetworkX) ---
        centrality_score = 0.0
        community_risk = 0.0
        if HAS_NX and self._G is not None and self._G.has_node(user_id):
            try:
                deg = self._G.degree(user_id)
                centrality_score = min(1.0, deg / 20.0)
                if centrality_score > 0.5:
                    signals.append(f"high_graph_centrality:{centrality_score:.2f}")
                    risk_score += centrality_score * 20

                neighbors = list(self._G.neighbors(user_id))
                user_neighbors = [
                    n for n in neighbors
                    if self._G.nodes[n].get("node_type") == "user"
                ]
                circular_count = sum(
                    1 for n in user_neighbors
                    if any(self._G.has_edge(n, m) for m in user_neighbors if m != n)
                )
                if circular_count > 2:
                    signals.append(f"circular_transaction_pattern:{circular_count}_links")
                    risk_score += min(30.0, circular_count * 10)
                    community_risk = min(1.0, circular_count / 5)

            except Exception as exc:
                _logger.error(
                    "GraphIntelligence: NetworkX analysis failed — "
                    "user=%r device=%r %s: %s",
                    user_id, device_id, type(exc).__name__, exc,
                )

        # --- Mule network detection ---
        txns = list(self._account_txns.get(user_id, deque()))
        if len(txns) >= 3:
            amounts = [t["amount"] for t in txns[-10:]]
            if max(amounts) > sum(amounts[:-1]) * 0.8:
                signals.append("mule_network_pattern:single_large_outflow")
                risk_score += 25.0

        elapsed_ms = (time.perf_counter() - t0) * 1000
        final_risk = round(min(100.0, risk_score), 2)

        # Fraud ring: fraud neighbors connected via device OR ip (not AND).
        # Previously required shared_device AND fraud_assoc, which missed IP-only rings.
        fraud_ring = fraud_assoc > 0 and (shared_device_count >= 2 or shared_ip_count >= 3)

        return {
            "graph_risk_score": final_risk,
            "graph_signals": signals,
            "shared_device_flag": shared_device_count >= 2,
            "multi_account_device": shared_device_count >= 2,
            "fraud_ring_detected": fraud_ring,
            "centrality_score": round(centrality_score, 3),
            "community_risk": round(community_risk, 3),
            "graph_latency_ms": round(elapsed_ms, 2),
        }

    def get_network_summary(self, user_id: str) -> Dict[str, Any]:
        if not HAS_NX or self._G is None or not self._G.has_node(user_id):
            return {"node_count": 0, "edge_count": 0, "connected_users": []}
        try:
            subgraph_nodes = list(nx.ego_graph(self._G, user_id, radius=2).nodes())
            return {
                "node_count": len(subgraph_nodes),
                "edge_count": self._G.subgraph(subgraph_nodes).number_of_edges(),
                "connected_users": [
                    n for n in nx.neighbors(self._G, user_id)
                    if self._G.nodes[n].get("node_type") == "user"
                ],
            }
        except Exception as exc:
            _logger.warning(
                "GraphIntelligence: network_summary failed for user=%r — %s: %s",
                user_id, type(exc).__name__, exc,
            )
            return {"node_count": 0, "edge_count": 0, "connected_users": []}

    def get_metrics(self) -> Dict[str, Any]:
        """Memory and eviction metrics for observability / health-check endpoints."""
        return {
            "device_keys": len(self._device_accounts),
            "ip_keys": len(self._ip_accounts),
            "merchant_keys": len(self._merchant_accounts),
            "user_txn_keys": len(self._account_txns),
            "fraud_flagged_users": len(self._fraud_flags),
            "device_evictions": self._device_accounts.eviction_count,
            "ip_evictions": self._ip_accounts.eviction_count,
            "merchant_evictions": self._merchant_accounts.eviction_count,
            "user_txn_key_evictions": self._txn_key_eviction_count,
            "nx_nodes": self._G.number_of_nodes() if HAS_NX and self._G else 0,
            "nx_edges": self._G.number_of_edges() if HAS_NX and self._G else 0,
            "max_keys": self._max_keys,
            "max_txns_per_user": self._max_txns,
        }


# Singleton graph instance
fraud_graph = FraudGraph()
