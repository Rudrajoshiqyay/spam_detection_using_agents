# Regression Baselines — FraudGuard AI
**Date:** 2026-06-23 | **Version:** Post-Remediation Sprint 1

---

## Baseline: Core Formula Behavior

### Fast Screening — Pre-Risk Scores

| Test Case | Expected Pre-Risk | Threshold | Decision |
|---|---|---|---|
| Normal salaried domestic txn (known device, home city, avg amount, business hours) | 3–15 | < 35 | AUTO-APPROVE |
| ATO probe (new device, small amount, wrong city) | 35–55 | ≥ 35 | ESCALATE |
| ATO drain (new device, large amount, intl location, 3am) | 70–90 | ≥ 35 | ESCALATE → FRAUD |
| Gen4 full mutations (trusted device, home city, avg amount, slow velocity) | 5–20 | < 35 | AUTO-APPROVE (known bypass) |
| Card testing burst (10 txns, 30sec intervals, gaming merchant) | 35–55 | ≥ 35 | ESCALATE |
| Velocity attack burst (15 txns, 20sec intervals, high amounts) | 55–75 | ≥ 35 | ESCALATE |

---

### Consensus Engine — Expected Agreement Scores

| Scenario | Agent Scores | Expected Agreement | Expected Confidence |
|---|---|---|---|
| All agents agree (fraud) | [90,85,88,82,87] | ≥ 90 | ≥ 70 |
| Moderate disagreement | [85,20,75,15,80] | 50–70 | 30–55 |
| Complete agent failure (all default) | [50,50,50,50,50] | 0.0 | 0.0 |
| 2 agents fail | [90,85,50,82,50] | 60–75 | 45–65 |
| Auto-approve (pre_risk=12) | N/A | 80–90 | 75–85 |
| Auto-approve (pre_risk=30) | N/A | 55–70 | 45–60 |

---

### Campaign Ground Truth Labels (After Fix)

| Campaign | Expected fraud_type | Previous (Broken) |
|---|---|---|
| account_takeover | account_takeover | account_takeover |
| card_testing | card_testing | card_testing |
| money_mule | money_mule | money_mule |
| velocity_attack | velocity_fraud | velocity_fraud |
| synthetic_identity | synthetic_identity | synthetic_identity |
| **cross_border_fraud** | **cross_border_fraud** | **account_takeover (BUG)** |

---

### Ring Graph Structure — Expected Minimums

| Ring Type | Min Nodes | Min Edges | Graph Built? |
|---|---|---|---|
| shared_device_ring (size=5) | 7 | 5 | ✅ |
| ip_cluster_ring (size=6) | 12 | 6 | ✅ |
| merchant_ring (size=5) | 6 | 5 | ✅ |
| mule_chain_ring (length=4) | 4 | 3 | ✅ |
| **multi_vector_ring (size=8)** | **≥ 10** | **≥ 8** | **✅ (FIXED)** |

---

### IP Ranges — Expected

| Generator | Expected IP Range | Previous (Broken) |
|---|---|---|
| ip_cluster_ring | 103.x.x.x (public Indian ISP) | 192.168.x.x (private RFC-1918) |
| _base_txn_dict (campaigns) | 103.x.x.x | 103.x.x.x ✅ |

---

### Population Weights — Canonical (After Fix)

Source of truth: `app/simulation/persona_agent._PERSONA_WEIGHTS`

| Persona | Weight |
|---|---|
| student | 0.18 |
| salaried_employee | 0.35 |
| business_owner | 0.10 |
| frequent_traveler | 0.10 |
| senior_citizen | 0.10 |
| gig_worker | 0.10 |
| high_net_worth | 0.04 |
| crypto_trader | 0.03 |

`population_simulator.POPULATION_WEIGHTS` must equal `persona_agent._PERSONA_WEIGHTS`. PSI between them = 0.000.

---

### Card Testing — Expected Cities (After Fix)

Card testing transactions must use a real `DOMESTIC_CITIES` city.
Valid values include: Mumbai, Delhi, Bangalore, Chennai, Kolkata, Hyderabad, Pune, etc.
**Invalid value after fix:** "Unknown" (was hardcoded before)

---

### Money Mule — Transaction Count

| Mule Count | Expected Transaction Count | Formula |
|---|---|---|
| 3 mules | 5 | 1 inject + 2 layers + 1 cashout |
| 4 mules | 6 | 1 inject + 3 layers + 1 cashout |
| 5 mules | 7 | 1 inject + 4 layers + 1 cashout |

**Rule:** inject always goes to mule_users[0]. layers go to mule_users[1], [2], ... No user should receive both inject and a layer transaction.

---

### Metrics Endpoint — Expected Response Structure

`GET /metrics/evaluation` must return:
```json
{
  "ground_truth_stats": {...},
  "dataset_composition": {
    "total_records": N,
    "fraud_count": X,
    "legitimate_count": Y,
    "fraud_rate": 0.08,
    "by_fraud_type": {
      "account_takeover": ...,
      "cross_border_fraud": ...,
      ...
    }
  },
  "note": "..."
}
```

**Must NOT contain:** `"accuracy": 1.0` or `"accuracy": 100%` (this was the bug)

---

## Regression Test Checklist

Run after every code change:

- [ ] `cross_border_fraud` campaign produces `fraud_type = "cross_border_fraud"` in all transactions
- [ ] `card_testing` campaign produces `location_city` in DOMESTIC_CITIES (never "Unknown")
- [ ] `money_mule` (3 mules) produces exactly 5 transactions (1+2+1)
- [ ] `money_mule` mule_users[0] receives exactly 1 transaction (inject only, no layer)
- [ ] `ip_cluster_ring` graph IP for each user == transaction ip_address for that user
- [ ] `ip_cluster_ring` IPs start with 103. (not 192.168.)
- [ ] `multi_vector_ring` returns `node_count ≥ 10` and `edge_count ≥ 8`
- [ ] `consensus_engine` with all-default agents produces `agreement_score = 0.0`
- [ ] `consensus_engine` with 2-default agents produces `agreement_score ≤ base - 20`
- [ ] `auto_approve` path produces `agreement_score < 100` and `confidence_score < 90`
- [ ] `/metrics/evaluation` does NOT contain `"accuracy": 1.0`
- [ ] `POPULATION_WEIGHTS` in population_simulator == `_PERSONA_WEIGHTS` in persona_agent
- [ ] Feature store failure produces WARNING log, not silent pass
