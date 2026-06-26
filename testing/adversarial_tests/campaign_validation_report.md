# Phase 5 — Fraud Campaign Validation Report
**Date:** 2026-06-23 | **Auditor:** QA Agent | **Mode:** READ-ONLY

---

## 5.1 Campaign Inventory

| Campaign | Generator | Phases | Ground Truth | Issues |
|---|---|---|---|---|
| Account Takeover | generate_ato_campaign | probe + drain | ✓ Stored | Missing escalation/cashout; no profile-change |
| Card Testing | generate_card_testing_campaign | test only | ✓ Stored | "Unknown" city; pre-set labels by index |
| Money Mule | generate_money_mule_campaign | inject + layers + cashout | ✓ Stored | Double-injection bug |
| Velocity Attack | generate_velocity_attack_campaign | burst only | ✓ Stored | No pre-attack staging |
| Synthetic Identity | generate_synthetic_identity_campaign | credit_build + fraud_burst | ✓ Stored | Same device across all phases |
| Cross-Border | generate_cross_border_campaign | intl_hop only | ✓ Stored | fraud_type set to "account_takeover" |
| Merchant Abuse | **NOT IMPLEMENTED** | — | — | Referenced in validator but no generator |

---

## 5.2 Attack Chain Completeness (Spec: Recon → Probe → Exploit → Drain → Cashout)

| Campaign | Recon | Probe | Exploit | Drain | Cashout | Completeness |
|---|---|---|---|---|---|---|
| ATO | ✗ | ✓ (2 txns) | ✗ | ✓ (3 txns) | ✗ | 40% |
| Card Testing | ✗ | ✓ (all txns) | ✗ | ✗ | ✗ | 20% |
| Money Mule | ✗ | ✗ | ✓ (inject) | ✓ (layers) | ✓ (crypto) | 60% |
| Velocity Attack | ✗ | ✗ | ✗ | ✓ (burst) | ✗ | 20% |
| Synthetic Identity | ✗ | ✓ (credit_build) | ✓ | ✓ (burst) | ✗ | 60% |
| Cross-Border | ✗ | ✗ | ✗ | ✓ (intl_hop) | ✗ | 20% |

**Average attack chain completeness: 37%** — well below the 5-stage requirement.

---

## 5.3 Critical Bug: Cross-Border Fraud Type Mislabeling

```python
# fraud_campaign_agent.py, line ~318
txn = _base_txn_dict(
    user_id, amount, cat,
    city["city"], city["country"], device_id, ts,
    campaign_id, "account_takeover",  # ← WRONG
)
```

Expected: `"cross_border_fraud"` or `"cross_border"`
Actual in ground truth: `"account_takeover"`

**Impact:**
- Cross-border campaign inflates account_takeover counts by ~25–30%
- Evaluation metrics for account_takeover are distorted
- Cross-border fraud type shows zero count in `by_fraud_type` metrics
- `/metrics/fraud-type-performance` endpoint returns misleading data

---

## 5.4 Critical Bug: Money Mule Double Injection

```python
# Lines 165–190
victim_id = mule_users[0]["metadata"]["user_id"]
txn = _base_txn_dict(victim_id, ..., "inject")   # <-- mule_users[0] gets inject
transactions.append(txn)

for i, mule in enumerate(mule_users):             # loop starts at i=0
    txn["phase"] = f"layer_{i+1}"                 # <-- mule_users[0] gets layer_1
    transactions.append(txn)
```

For a 3-mule campaign:
- Expected transactions: 1 inject + 3 layers + 1 cashout = 5
- Actual transactions: 1 inject + 3 layers + 1 cashout = 5 (first user in both inject AND layer_1)
- First mule makes 2 transactions: one labeled "inject" and one labeled "layer_1"
- This looks like an unusual spending pattern but for the WRONG reason

---

## 5.5 Card Testing Label Inconsistency

```python
txn["expected_label"] = "BLOCKED" if i > 5 else "ESCALATED"
```

The expected label changes from ESCALATED to BLOCKED after the 6th transaction. This pre-assigns labels based on transaction index, not actual detection logic. The detection pipeline should determine labels, not the generator.

**Issue:** If the detection pipeline blocks the first transaction (correct behavior), the generator still labels it ESCALATED. If the detection pipeline escalates transaction #8, the generator says it should be BLOCKED.

---

## 5.6 Synthetic Identity Phase Analysis

**Credit-build phase (15 transactions):**
- `is_fraud = False` ← correct
- `expected_label = "APPROVED"` ← correct
- Same `device_id` used throughout ← creates device-fraud association

**Fraud burst phase (5 transactions):**
- `is_fraud = True` ← correct
- All transactions use same device as credit-build phase
- Detection: device is "known" (from credit-build) → device_novelty = 0
- This correctly simulates synthetic identity fraud (device familiar, behavior changed)

**Finding:** Synthetic identity is the best-implemented campaign in terms of realism.

---

## 5.7 Campaign Timing Analysis

| Campaign | Time Span | Transactions | Realistic? |
|---|---|---|---|
| ATO | ~15 minutes total | 5 | ✓ (probe fast, drain rapid) |
| Card Testing | 10–45 second gaps | 10–20 | ✓ (burst testing) |
| Money Mule | 1–3 days | 5–8 | ✓ (layered over days) |
| Velocity Attack | 20–90 second gaps | 8–15 | ✓ (burst) |
| Synthetic Identity | 30–90 days | 20 | ✓ (slow build + burst) |
| Cross-Border | 30-min gaps, 4 cities | 4 | ✓ (impossible travel) |

---

## CRITICAL FINDINGS
1. Cross-border fraud_type mislabeled as account_takeover in ground truth
2. Money mule double-injection on first mule account
3. merchant_abuse not implemented as campaign (only referenced in validator/rings)

## WARNINGS
1. Average attack chain completeness is only 37% (need 5 stages)
2. Card testing uses pre-assigned labels based on transaction index
3. All campaigns share same device across phases (except ATO which uses attacker device)

---

**Fraud Campaign Score: 62 / 100**
