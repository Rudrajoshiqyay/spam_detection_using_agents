"""
Fraud Ring Agent — generates interconnected fraud rings with shared graph structures.

Rings have:
  - Shared devices (device_id reused across user_ids)
  - Shared IPs (same subnet)
  - Shared merchants (same mule merchant repeatedly)
  - Mule account chains (linked user_ids)
  - NetworkX-compatible edge list for graph analysis
"""

import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional, Tuple
import networkx as nx

from app.simulation.persona_agent import PersonaType, create_persona_user, create_persona_batch
from app.simulation.world_builder import get_merchant_by_category, DOMESTIC_CITIES


# ── Ring Types ────────────────────────────────────────────────────────────────

RING_TYPES = [
    "shared_device_ring",    # multiple accounts → same physical device
    "ip_cluster_ring",       # multiple accounts → same IP subnet
    "merchant_ring",         # funnel purchases through same mule merchant
    "mule_chain_ring",       # layered money mule chain
    "multi_vector_ring",     # combination of above
]


# ── Ring Graph Builder ────────────────────────────────────────────────────────

class FraudRingGraph:
    """Builds and exposes a NetworkX graph representing a fraud ring."""

    def __init__(self, ring_id: str, ring_type: str):
        self.ring_id = ring_id
        self.ring_type = ring_type
        self.G = nx.DiGraph()
        self.members: List[str] = []          # user_ids
        self.shared_devices: List[str] = []
        self.shared_ips: List[str] = []
        self.mule_merchants: List[str] = []
        self.transactions: List[Dict] = []

    def add_member(self, user_id: str, role: str = "member"):
        self.G.add_node(user_id, node_type="user", role=role, ring_id=self.ring_id)
        self.members.append(user_id)

    def link_device(self, user_id: str, device_id: str):
        self.G.add_node(device_id, node_type="device")
        self.G.add_edge(user_id, device_id, edge_type="uses_device")
        if device_id not in self.shared_devices:
            self.shared_devices.append(device_id)

    def link_ip(self, user_id: str, ip: str):
        self.G.add_node(ip, node_type="ip")
        self.G.add_edge(user_id, ip, edge_type="from_ip")
        if ip not in self.shared_ips:
            self.shared_ips.append(ip)

    def link_merchant(self, user_id: str, merchant_id: str):
        self.G.add_node(merchant_id, node_type="merchant")
        self.G.add_edge(user_id, merchant_id, edge_type="transacts_at")
        if merchant_id not in self.mule_merchants:
            self.mule_merchants.append(merchant_id)

    def link_transfer(self, sender_id: str, receiver_id: str, amount: float):
        self.G.add_edge(sender_id, receiver_id, edge_type="transfer", amount=amount)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ring_id": self.ring_id,
            "ring_type": self.ring_type,
            "member_count": len(self.members),
            "members": self.members,
            "shared_devices": self.shared_devices,
            "shared_ips": self.shared_ips,
            "mule_merchants": self.mule_merchants,
            "node_count": self.G.number_of_nodes(),
            "edge_count": self.G.number_of_edges(),
            "edges": [
                {"source": u, "target": v, **d}
                for u, v, d in self.G.edges(data=True)
            ],
        }


def _shared_subnet_ip(subnet: str) -> str:
    parts = subnet.split(".")
    return f"{parts[0]}.{parts[1]}.{parts[2]}.{random.randint(1, 254)}"


# ── Ring Generators ───────────────────────────────────────────────────────────

def generate_shared_device_ring(size: int = None) -> Dict[str, Any]:
    """Multiple accounts used from the same physical device."""
    ring_id = f"ring_sd_{uuid.uuid4().hex[:8]}"
    size = size or random.randint(3, 8)
    users = create_persona_batch(size, PersonaType.gig_worker)

    # 1-2 shared devices
    shared_devices = [f"dev_shared_{uuid.uuid4().hex[:8]}" for _ in range(random.randint(1, 2))]
    ring = FraudRingGraph(ring_id, "shared_device_ring")
    start_time = datetime.now(timezone.utc) - timedelta(days=random.randint(1, 14))

    for i, user in enumerate(users):
        uid = user["metadata"]["user_id"]
        ring.add_member(uid, role="controller" if i == 0 else "mule")
        device = random.choice(shared_devices)
        ring.link_device(uid, device)

    # Generate transactions — all from shared devices
    txns = []
    for user in users:
        uid = user["metadata"]["user_id"]
        device = random.choice(shared_devices)
        for j in range(random.randint(2, 6)):
            ts = start_time + timedelta(hours=random.randint(0, 336))
            m = get_merchant_by_category("ecommerce")
            txns.append({
                "transaction_id": f"txn_{uuid.uuid4().hex[:12]}",
                "user_id": uid,
                "amount": round(random.uniform(500, 20_000), 2),
                "merchant_id": m["merchant_id"],
                "merchant_name": m["merchant_name"],
                "merchant_category": "ecommerce",
                "device_id": device,
                "timestamp": (start_time + timedelta(hours=j * 6)).isoformat(),
                "is_fraud": True,
                "fraud_type": "account_takeover",
                "ring_id": ring_id,
                "campaign_id": None,
                "expected_label": "BLOCKED",
            })

    ring.transactions = txns
    result = ring.to_dict()
    result["transactions"] = txns
    return result


def generate_ip_cluster_ring(size: int = None) -> Dict[str, Any]:
    """Multiple accounts operating from the same IP subnet."""
    ring_id = f"ring_ip_{uuid.uuid4().hex[:8]}"
    size = size or random.randint(4, 10)
    users = create_persona_batch(size)

    # Use realistic public IP subnet (not RFC-1918 private range)
    subnet = f"103.{random.randint(1, 254)}.{random.randint(1, 254)}"
    ring = FraudRingGraph(ring_id, "ip_cluster_ring")
    start_time = datetime.now(timezone.utc) - timedelta(days=random.randint(1, 7))

    # Assign one persistent IP per user so graph and transactions use the same IP
    user_ips = {user["metadata"]["user_id"]: _shared_subnet_ip(subnet) for user in users}

    for i, user in enumerate(users):
        uid = user["metadata"]["user_id"]
        ring.add_member(uid, role="node")
        ring.link_ip(uid, user_ips[uid])

    txns = []
    for user in users:
        uid = user["metadata"]["user_id"]
        ip = user_ips[uid]
        for j in range(random.randint(1, 5)):
            m = get_merchant_by_category(random.choice(["gambling", "gaming", "cryptocurrency"]))
            txns.append({
                "transaction_id": f"txn_{uuid.uuid4().hex[:12]}",
                "user_id": uid,
                "amount": round(random.uniform(1_000, 50_000), 2),
                "merchant_id": m["merchant_id"],
                "merchant_name": m["merchant_name"],
                "merchant_category": m["merchant_category"],
                "device_id": f"dev_{uuid.uuid4().hex[:10]}",
                "ip_address": ip,
                "timestamp": (start_time + timedelta(hours=j * 4)).isoformat(),
                "is_fraud": True,
                "fraud_type": "card_testing",
                "ring_id": ring_id,
                "campaign_id": None,
                "expected_label": "BLOCKED",
            })

    ring.transactions = txns
    result = ring.to_dict()
    result["transactions"] = txns
    return result


def generate_merchant_ring(size: int = None) -> Dict[str, Any]:
    """Multiple users funnel money through a single mule merchant."""
    ring_id = f"ring_mch_{uuid.uuid4().hex[:8]}"
    size = size or random.randint(3, 7)
    users = create_persona_batch(size)

    mule_merchant = get_merchant_by_category("gambling")
    ring = FraudRingGraph(ring_id, "merchant_ring")
    ring.link_merchant("__ring__", mule_merchant["merchant_id"])

    start_time = datetime.now(timezone.utc) - timedelta(days=random.randint(2, 10))

    txns = []
    for user in users:
        uid = user["metadata"]["user_id"]
        ring.add_member(uid)
        for j in range(random.randint(3, 8)):
            txns.append({
                "transaction_id": f"txn_{uuid.uuid4().hex[:12]}",
                "user_id": uid,
                "amount": round(random.uniform(2_000, 30_000), 2),
                "merchant_id": mule_merchant["merchant_id"],
                "merchant_name": mule_merchant["merchant_name"],
                "merchant_category": mule_merchant["merchant_category"],
                "device_id": f"dev_{uuid.uuid4().hex[:10]}",
                "timestamp": (start_time + timedelta(hours=j * 8)).isoformat(),
                "is_fraud": True,
                "fraud_type": "merchant_abuse",
                "ring_id": ring_id,
                "campaign_id": None,
                "expected_label": "BLOCKED",
            })

    ring.transactions = txns
    result = ring.to_dict()
    result["transactions"] = txns
    return result


def generate_mule_chain_ring(chain_length: int = None) -> Dict[str, Any]:
    """Money moves sequentially through a chain of mule accounts."""
    ring_id = f"ring_mc_{uuid.uuid4().hex[:8]}"
    chain_length = chain_length or random.randint(3, 6)
    users = create_persona_batch(chain_length, PersonaType.gig_worker)

    ring = FraudRingGraph(ring_id, "mule_chain_ring")
    start_time = datetime.now(timezone.utc) - timedelta(days=random.randint(3, 14))
    amount = random.uniform(100_000, 500_000)

    txns = []
    for i, user in enumerate(users):
        uid = user["metadata"]["user_id"]
        ring.add_member(uid, role="mule")
        if i > 0:
            ring.link_transfer(users[i-1]["metadata"]["user_id"], uid, amount * (0.9 ** i))

        ts = start_time + timedelta(days=i * random.randint(1, 3))
        current_amount = amount * (0.9 ** i)
        m = get_merchant_by_category("p2p_transfer")
        txns.append({
            "transaction_id": f"txn_{uuid.uuid4().hex[:12]}",
            "user_id": uid,
            "amount": round(current_amount, 2),
            "merchant_id": m["merchant_id"],
            "merchant_name": m["merchant_name"],
            "merchant_category": "p2p_transfer",
            "device_id": f"dev_{uuid.uuid4().hex[:10]}",
            "timestamp": ts.isoformat(),
            "is_fraud": True,
            "fraud_type": "money_mule",
            "ring_id": ring_id,
            "campaign_id": None,
            "expected_label": "BLOCKED",
        })

    ring.transactions = txns
    result = ring.to_dict()
    result["transactions"] = txns
    return result


def generate_multi_vector_ring(size: int = None) -> Dict[str, Any]:
    """Combines device sharing, IP clustering, and mule merchant in one ring."""
    ring_id = f"ring_mv_{uuid.uuid4().hex[:8]}"
    size = size or random.randint(5, 12)

    sd = generate_shared_device_ring(size=size // 2)
    ip = generate_ip_cluster_ring(size=size // 2)

    # Build a combined FraudRingGraph merging both sub-rings
    ring = FraudRingGraph(ring_id, "multi_vector_ring")

    for uid in sd.get("members", []):
        ring.add_member(uid, role="device_member")
    for dev in sd.get("shared_devices", []):
        for uid in sd.get("members", []):
            ring.link_device(uid, dev)

    for uid in ip.get("members", []):
        ring.add_member(uid, role="ip_member")
    for ip_addr in ip.get("shared_ips", []):
        for uid in ip.get("members", []):
            ring.link_ip(uid, ip_addr)

    # Merge transactions under combined ring_id
    all_txns = []
    for txn in sd.get("transactions", []) + ip.get("transactions", []):
        txn = dict(txn)
        txn["ring_id"] = ring_id
        all_txns.append(txn)

    ring.transactions = all_txns
    result = ring.to_dict()
    result["transactions"] = all_txns
    return result


# ── Ring Factory ──────────────────────────────────────────────────────────────

RING_GENERATORS = {
    "shared_device_ring": generate_shared_device_ring,
    "ip_cluster_ring":    generate_ip_cluster_ring,
    "merchant_ring":      generate_merchant_ring,
    "mule_chain_ring":    generate_mule_chain_ring,
    "multi_vector_ring":  generate_multi_vector_ring,
}


def generate_ring(ring_type: str = None) -> Dict[str, Any]:
    if ring_type is None:
        ring_type = random.choice(RING_TYPES)
    gen_fn = RING_GENERATORS.get(ring_type)
    if not gen_fn:
        raise ValueError(f"Unknown ring type: {ring_type}")
    return gen_fn()
