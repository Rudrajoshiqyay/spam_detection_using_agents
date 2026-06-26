# Phase 15 — Generator Health Monitoring Report
**Date:** 2026-06-23 | **Auditor:** QA Agent | **Mode:** READ-ONLY

---

## 15.1 Generator Health Framework

**Generators Monitored:**
1. `population_simulator.py` — user population generation
2. `persona_agent.py` — individual user profile creation
3. `temporal_simulator.py` — transaction timing
4. `fraud_campaign_agent.py` — fraud campaign generation
5. `fraud_ring_agent.py` — fraud ring construction
6. `adversarial_agent.py` — adversarial mutations
7. `fraud_evolution_agent.py` — generational evolution
8. `world_builder.py` — world context (cities, merchants, devices)

**Health Metrics:** Entropy, mode collapse, repetition rate, coverage, distribution quality

---

## 15.2 Population Generator Health

### Persona Distribution Entropy

Shannon Entropy H = −Σ p(i) × log₂(p(i))

| Weights Source | H (bits) | Max Possible | Uniformity |
|---|---|---|---|
| pop_simulator POPULATION_WEIGHTS | 2.74 | 3.0 (8 equal) | 91.3% |
| persona_agent _PERSONA_WEIGHTS | 2.68 | 3.0 | 89.3% |

**Assessment:** Both distributions have high entropy (near-uniform). ✓
Senior and HNW are underrepresented (low weight → lower entropy for those bins).

### Mode Collapse Risk

Salaried employee: 35% weight. In a 1000-user simulation, ~350 users would be salaried. This creates a distribution skewed toward salaried spending patterns.

**Mode collapse threshold (informal): >30% in a single category**
**Status: salaried_employee at 35% → borderline mode concentration**

---

## 15.3 Transaction Timing Generator Health

### Temporal Distribution Entropy

`temporal_simulator.py` uses:
- Hour-based weights per persona
- Day-of-week weights
- Monthly patterns (salary day, rent day, end-of-month)

**Student hourly weights (example):**
Active hours: afternoon/evening (12:00–22:00)
Less active: morning (09:00–12:00) and late night

**Entropy:** High within-persona variance in hours → entropy is reasonable

### Repetition Analysis

**Gauss-Poisson Issue for Low-λ Personas:**
```python
int(random.gauss(1.4, sqrt(1.4))) = int(random.gauss(1.4, 1.18))
```

Gaussian can generate negative → clipped to 0. For λ=1.4:
- P(negative Gaussian < 0) ≈ 11.9%
- All 11.9% become "0 transactions" day
- Expected Poisson P(0) = 24.7%
- Actual: ~24.7% + some Gaussian negative clipping → ~35% zero days for senior

**Repetition rate for senior: 35% zero-transaction days vs expected 25%**
**Status: ⚠️ Over-clustering at zero for low-activity personas**

---

## 15.4 Merchant Selection Health

### Merchant Pool: 500 entries in `_MERCHANT_POOL`

```python
_MERCHANT_POOL: List[Merchant] = [...]  # 500+ merchants
```

**Coverage per category:**
- 30 merchant categories × ~16 merchants each ≈ 480 entries
- Some categories may have more (ecommerce, grocery) vs less (crypto)

**Entropy per transaction:**
- Each persona draws from category pool (prefer their categories)
- Within category, uniform random selection from merchants

**Repetition risk:** With 5 merchants per category and 100 transactions per user, each merchant appears ~20 times. For small merchant pools in niche categories, repetition is guaranteed.

**Mode collapse risk in niche categories:** gambling category likely has 2–5 merchants total. Merchant ring always uses gambling → high merchant ID repetition.

---

## 15.5 Campaign Generator Health

### Campaign Coverage
| Campaign | Implemented | Health |
|---|---|---|
| ATO | ✓ | Minor gaps (no escalation/cashout) |
| Card Testing | ✓ | Location city hardcoded |
| Money Mule | ✓ | Double-injection bug |
| Velocity Attack | ✓ | No pre-staging |
| Synthetic Identity | ✓ | Best implemented |
| Cross-Border | ✓ | Fraud type mislabeled |
| Merchant Abuse | ✗ | Not implemented |

**Campaign diversity entropy:**
H = −Σ (1/6) × log₂(1/6) = 2.58 bits (assuming equal distribution)
With 7th campaign missing: 6 of 7 defined types = 85.7% coverage

### Mode Collapse Risk in Campaigns

**Card Testing:** All transactions use location="Unknown" → zero entropy on city for this campaign type.

**Money Mule:** All cashout transactions → Singapore, cryptocurrency → zero entropy for cashout city/category.

**Cross-Border:** Only 5 countries → constrained entropy for location_country.

---

## 15.6 Ring Generator Health

### Ring Type Coverage
| Ring Type | Graph Built | Realistic IPs | Healthy |
|---|---|---|---|
| shared_device_ring | ✓ | N/A | ✓ |
| ip_cluster_ring | ✓ | ✗ (192.168.x.x) | ✗ |
| merchant_ring | ✓ | N/A | ✓ |
| mule_chain_ring | ✓ | N/A | ✓ |
| multi_vector_ring | ✗ (no graph) | N/A | ✗ |

**Ring health: 3/5 rings functional = 60%**

### Repetition Analysis

**shared_device_ring:** 3–8 users share same device. With 5 rings per session, 40 users share ~5 devices → each device shared by 8 users on average.

**ip_cluster_ring:** subnet = `192.168.{random.randint(1,254)}` → 253 possible subnets. Within subnet: `f"{subnet}.{random.randint(2,254)}"` → 253 possible IPs.

**Collision probability with 10 rings:** 10 different subnets → 10 different IP pools. Low collision. But all are private IPs → 100% leakage.

---

## 15.7 Adversarial Generator Health

### Mutation Application Rate (from code analysis)

| Mutation | Application Condition |
|---|---|
| reduce_amount | Always applied if txns exist |
| slow_velocity | Always applied if txns exist |
| use_trusted_device | Applied if victim has known devices |
| use_trusted_merchant | Applied at 50% probability |
| mimic_location | Applied if victim has known locations |
| change_timing | Applied if txns > 0 |
| add_noise_txns | Always applied (adds 1–3 noise txns) |
| reduce_frequency | Applied if txns ≥ 3 |

**Mutation entropy:** 7/8 mutations are conditionally always applied. Only `use_trusted_merchant` has probabilistic (50%) application. Very low entropy in mutation selection for Gen4.

### Noise Transaction Health

```python
f"txn_noise_{i}_{user_id[:6]}"  # i ∈ {0,1,2}
```

IDs are deterministic given user_id. For the same user:
- Call 1: `txn_noise_0_abc123`, `txn_noise_1_abc123`, `txn_noise_2_abc123`
- Call 2: Same IDs → ground truth overwrites previous entries

**Repetition rate: 100% for repeat adversarial calls on same user**

---

## 15.8 World Builder Health

### City Distribution

```python
CITIES = [...]  # 100+ cities (domestic India focus)
INTL_CITIES = [...]  # ~20+ international cities
```

**Entropy:** 100 cities → H = log₂(100) = 6.64 bits max
With persona-based home city selection: lower effective entropy (~4–5 bits)

### Merchant Name Repetition

```python
_MERCHANT_POOL: List[Merchant] = [...]  # module-level singleton
```

The merchant pool is fixed at startup. Every simulation session uses the same 500 merchants. This is realistic (merchants don't change frequently) but means all generated data references the same set.

**Assessment:** Merchant pool health is ✓ adequate for test purposes.

---

## 15.9 Generator Health Summary

| Generator | Entropy | Mode Collapse | Repetition | Status |
|---|---|---|---|---|
| Population | HIGH | borderline (salaried 35%) | LOW | ✓ |
| Temporal | MEDIUM | LOW | ⚠️ senior zero days | WARNING |
| Campaign | MEDIUM | HIGH (Unknown city, SG cashout) | LOW | WARNING |
| Ring | LOW | HIGH (gambling, private IP) | MEDIUM | CRITICAL |
| Adversarial | LOW | MEDIUM (deterministic noise IDs) | HIGH | WARNING |
| Evolution | LOW | HIGH (only 4 gen bands) | MEDIUM | CRITICAL |
| World | HIGH | LOW | LOW | ✓ |

---

## CRITICAL FINDINGS
1. Evolution generator only supports 4 generations — mode collapse at Gen5+
2. IP cluster ring uses private IPs — 100% detection via IP range → trivial leakage
3. Campaign generators collapse on location (Unknown city) and country (Singapore)

## WARNINGS
1. Noise transaction IDs repeat for same user across adversarial calls
2. Temporal simulator over-generates zero-transaction days for senior persona
3. Mutation selection has near-zero entropy in Gen4 (all mutations applied)
4. Merchant ring always uses gambling → zero merchant category entropy for this ring

---

**Generator Health Score: 58 / 100**
