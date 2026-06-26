# Phase 1 — Population Realism Report
**Date:** 2026-06-23 | **Auditor:** QA Agent | **Mode:** READ-ONLY

---

## 1.1 Persona Coverage

| Persona | Defined | Income Range (INR/mo) | Avg Txn | Txn/Day | Night Active | Status |
|---|---|---|---|---|---|---|
| Student | ✓ | 5K–15K | ₹350 | 2.1 | Yes | ✓ PASS |
| Salaried Employee | ✓ | 25K–100K | ₹1,800 | 3.2 | No | ✓ PASS |
| Business Owner | ✓ | 150K–1M | ₹18,000 | 5.8 | No | ✓ PASS |
| Frequent Traveler | ✓ | 80K–500K | ₹5,000 | 4.5 | Yes | ✓ PASS |
| Senior Citizen | ✓ | 10K–40K | ₹900 | 1.4 | No | ✓ PASS |
| Gig Worker | ✓ | 8K–35K | ₹500 | 2.8 | Yes | ✓ PASS |
| HNW Individual | ✓ | 500K–10M | ₹50,000 | 3.0 | No | ✓ PASS |
| Crypto Trader | ✓ | 20K–500K | ₹8,000 | 6.5 | Yes | ✓ PASS |

**All 8 personas present.** ✓

---

## 1.2 Population Weight Validation

| Persona | persona_agent weight | population_simulator weight | Delta | Status |
|---|---|---|---|---|
| salaried_employee | 0.35 | 0.40 | +0.05 | ⚠️ MISMATCH |
| student | 0.18 | 0.20 | +0.02 | ⚠️ MISMATCH |
| senior_citizen | 0.10 | 0.05 | −0.05 | ⚠️ MISMATCH |
| high_net_worth | 0.04 | 0.02 | −0.02 | ⚠️ MISMATCH |
| business_owner | 0.10 | 0.10 | 0 | ✓ |
| frequent_traveler | 0.10 | 0.10 | 0 | ✓ |
| gig_worker | 0.10 | 0.10 | 0 | ✓ |
| crypto_trader | 0.03 | 0.03 | 0 | ✓ |

**FINDING:** Dual weight system — standalone calls use persona_agent weights; population generation uses different weights. This causes inconsistent distributions across call paths.

---

## 1.3 Income Distribution Realism

**Method:** `random.lognormvariate(0, 0.4)` then clamped via `lo + (hi-lo) * (sample/(sample+1))`

**Issue:** The transform is biased toward lower-income values within each range. P50 estimated at ~35% of range (not center).

| Persona | Stated Range | Estimated P50 | Realistic P50 | OK? |
|---|---|---|---|---|
| Student | 5K–15K | ~7.5K | ~9K | ⚠️ Low |
| Salaried | 25K–100K | ~46K | ~55K | ⚠️ Low |
| Business | 150K–1M | ~375K | ~450K | ⚠️ Low |
| HNW | 500K–10M | ~2.5M | ~3M | ⚠️ Low |

---

## 1.4 Spending Behavior Alignment

| Persona | Weekend Mult | Night Activity | Travel Freq | Device Types | OK? |
|---|---|---|---|---|---|
| Student | 1.5× | Yes | Rare | 90% mobile | ✓ Realistic |
| Salaried | 1.8× | No | Occasional | 75% mobile | ✓ Realistic |
| Business | 0.6× (weekends low) | No | Occasional | 50% mobile / 45% desktop | ✓ Realistic |
| Traveler | 2.0× | Yes | Very Frequent | 80% mobile | ✓ Realistic |
| Senior | 1.1× | No | Rare | 55% mobile / 40% desktop | ✓ Realistic |
| Gig Worker | 1.3× | Yes | Occasional | 95% mobile | ✓ Realistic |
| HNW | 1.6× | No | Frequent | 60% mobile / 30% desktop | ✓ Realistic |
| Crypto Trader | 1.2× | Yes (24/7 markets) | Occasional | 55% mobile / 40% desktop | ✓ Realistic |

---

## 1.5 Device Count Realism

| Persona | Device Range | Realistic? |
|---|---|---|
| Student | 1–2 | ✓ |
| Salaried | 1–3 | ✓ |
| Business Owner | 2–5 | ✓ |
| Traveler | 2–4 | ✓ |
| Senior | 1–2 | ✓ |
| Gig Worker | 1–2 | ✓ |
| HNW | 2–6 | ✓ |
| Crypto Trader | 2–5 | ✓ |

---

## 1.6 Active Hours Realism

| Persona | Active Hours | Realistic? |
|---|---|---|
| Student | 10–13, 18–23 | ✓ (late morning + evenings) |
| Salaried | 8–9, 12–13, 18–21 | ✓ (pre/post work) |
| Business Owner | 9–12, 14–17 | ✓ (business hours only) |
| Senior | 9–16 | ✓ (daytime only) |
| Crypto Trader | 0–2, 8–10, 14–15, 20–23 | ✓ (night active) |
| Gig Worker | 7–9, 12–13, 17–22 | ✓ (delivery hours) |

---

## 1.7 Geographic Diversity

- 100+ cities across 20+ countries ✓
- 30 domestic (India) cities across 3 tiers ✓
- Tier-1 weight 0.55, Tier-2 0.35, Tier-3 0.10 ✓
- International cities for travelers/HNW/business ✓

---

## 1.8 Merchant Preference Coverage

- 30 merchant categories defined ✓
- 500+ merchant pool ✓
- Each persona has 5–7 preferred categories ✓
- Overlap between business_owner and HNW: wire_transfer, travel ⚠️

---

## CRITICAL FINDINGS
1. **Dual population weight system** — inconsistent distributions
2. **Crypto trader 10% fraud_history=True** — systematic label encoding
3. **Gig worker UserType = working_professional** — cohort collision with salaried

## WARNINGS
1. Income distribution biased toward lower-end of range
2. HNW and business_owner merchant preferences overlap significantly
3. Account age uses uniform distribution (30–2500 days) — not realistic

---

**Population Realism Score: 74 / 100**
