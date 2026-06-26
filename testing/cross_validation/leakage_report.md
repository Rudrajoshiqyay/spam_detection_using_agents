# Phase 4 — Data Leakage Detection Report
**Date:** 2026-06-23 | **Auditor:** QA Agent | **Mode:** READ-ONLY

---

## 4.1 Leakage Detection Infrastructure

**Tool:** `app/simulation/label_leakage_detector.py`
**Method:** Per-feature: lift, information gain ratio, fraud concentration
**Thresholds:** Lift > 3.0 AND concentration > 50% = CRITICAL

**Status:** Infrastructure exists and is well-implemented. ✓

---

## 4.2 Systematic Leakage Patterns Found (Code Analysis)

### CRITICAL LEAKAGE #1 — Card Testing Location City

```python
# fraud_campaign_agent.py:133
txn = _base_txn_dict(user_id, amount, "gaming", "Unknown", "India", ...)
```

- `location_city = "Unknown"` on 100% of card testing transactions
- Legitimate transactions never have location_city="Unknown"
- A single rule `city == "Unknown" → fraud` achieves 100% recall on card testing
- **Lift on "Unknown" city: theoretically infinite**
- **Information Gain Ratio: ~1.0**

### CRITICAL LEAKAGE #2 — Merchant Ring Gambling Concentration

```python
# fraud_ring_agent.py:196
mule_merchant = get_merchant_by_category("gambling")
# 100% of merchant_ring transactions go to gambling
```

- Gambling merchant category receives 100% of merchant ring fraud
- Legitimate gambling transactions would need to be deliberately added to dilute this
- **Lift on gambling: very high (depends on population gambling rate)**

### CRITICAL LEAKAGE #3 — Private IP in IP Cluster Ring

```python
# fraud_ring_agent.py:152
subnet = f"192.168.{random.randint(1, 254)}"
```

- RFC 1918 private addresses (192.168.x.x) used for fraud ring IPs
- Real internet transactions use public IP addresses
- Any IP validation rule would flag 100% of ip_cluster ring transactions
- **Lift on 192.168.x.x: theoretically infinite**

---

## 4.3 High-Risk Leakage Patterns

### WARNING #1 — Money Mule Cashout Country

```python
# fraud_campaign_agent.py:193
txn = _base_txn_dict(..., "Singapore", "Singapore", ...)
```

All money mule cashout transactions: location_country = "Singapore", merchant_category = "cryptocurrency"
- Singapore cryptocurrency transactions: high fraud concentration
- **Estimated lift: 5–8×**

### WARNING #2 — Cross-Border Country Pool

```python
city_sequence = random.sample(
    [c for c in INTL_CITIES if c["country"] in ("UK", "USA", "Japan", "Australia", "Brazil")],
    k=4
)
```

Cross-border fraud restricted to exactly 5 countries. These countries will have disproportionate fraud rates vs. other international destinations.
- **Estimated lift: 3–5× for UK/USA/Japan/Australia/Brazil**

### WARNING #3 — Noise Transactions Carry Campaign Metadata

```python
noise.append({
    "campaign_id": txns[0].get("campaign_id"),   # populated
    "ring_id": txns[0].get("ring_id"),            # populated
    "_mutation": ["add_noise_txns"],              # present
})
```

Noise transactions labeled `is_fraud=False` but carry `campaign_id` and `ring_id` which would not exist on legitimate transactions. The `_mutation` field is also present.

### WARNING #4 — Velocity Attack Category Concentration

```python
cat = random.choice(["ecommerce", "electronics", "jewelry"])
```

Velocity attack transactions exclusively use 3 merchant categories. These 3 categories will have elevated fraud rates relative to others.

---

## 4.4 Features That Are Likely Clean (Low Leakage Risk)

| Feature | Assessment | Reason |
|---|---|---|
| transaction_amount | ✓ Clean | Varies across all fraud types |
| timestamp (hour) | ✓ Mostly Clean | Temporal simulator distributes across hours |
| persona_type | ⚠️ Partial | Crypto trader has 10% fraud_history |
| location_country (domestic) | ✓ Clean | All persona types transact in India |
| device_type | ✓ Clean | Varies across personas |
| payment_method | ✓ Mostly Clean | Varies across personas |

---

## 4.5 Leakage Severity Matrix

| Feature | Value | Fraud % | Lift | Severity |
|---|---|---|---|---|
| location_city | "Unknown" | ~100% of card_testing | ∞ | **CRITICAL** |
| ip_address | 192.168.x.x | ~100% of ip_cluster | ∞ | **CRITICAL** |
| merchant_category | gambling | ~100% of merchant_ring | Very High | **CRITICAL** |
| location_country | Singapore | ~80% of mule cashout | High | **WARNING** |
| merchant_category | cryptocurrency | High fraud conc. | High | **WARNING** |
| location_country | UK/USA/Japan/Aus/Brazil | 100% cross-border | Medium-High | **WARNING** |
| merchant_category | ecommerce/electronics/jewelry | Velocity fraud | Medium | **WARNING** |

---

## CRITICAL FINDINGS
1. Card testing "Unknown" city = trivial 100% detection shortcut
2. IP cluster private IP range = trivially detectable, not realistic
3. Merchant ring gambling concentration = high leakage

## WARNINGS
1. Noise transactions carry metadata that shouldn't exist on legitimate txns
2. Country concentration in specific fraud types
3. Velocity attack merchant concentration in 3 categories

---

**Leakage Risk Score: 55 / 100** (lower = more leakage detected)
