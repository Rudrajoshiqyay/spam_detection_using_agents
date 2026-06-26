# Phase 2 — Statistical Distribution Validation Report
**Date:** 2026-06-23 | **Auditor:** QA Agent | **Mode:** READ-ONLY

---

## 2.1 Transaction Amount Statistics (Derived from Persona Definitions)

| Persona | Mean (INR) | Std Dev | CV | Skew Est. | Distribution Health |
|---|---|---|---|---|---|
| Student | 350 | 280 | 0.80 | Right | ✓ Realistic |
| Salaried Employee | 1,800 | 1,500 | 0.83 | Right | ✓ Realistic |
| Business Owner | 18,000 | 25,000 | 1.39 | Right (B2B) | ✓ Realistic |
| Frequent Traveler | 5,000 | 6,000 | 1.20 | Right | ✓ Realistic |
| Senior Citizen | 900 | 500 | 0.56 | Slight right | ✓ Stable |
| Gig Worker | 500 | 400 | 0.80 | Right | ✓ Realistic |
| HNW Individual | 50,000 | 80,000 | 1.60 | Heavy right | ✓ Realistic |
| Crypto Trader | 8,000 | 15,000 | 1.88 | Very right | ✓ Volatile |

---

## 2.2 Transaction Frequency Statistics

| Persona | Mean Txn/Day | Poisson λ | Weekend Mult | Effective Weekend λ |
|---|---|---|---|---|
| Student | 2.1 | 2.1 | 1.5× | 3.15 |
| Salaried | 3.2 | 3.2 | 1.8× | 5.76 |
| Business Owner | 5.8 | 5.8 | 0.6× | 3.48 |
| Senior | 1.4 | 1.4 | 1.1× | 1.54 |
| Gig Worker | 2.8 | 2.8 | 1.3× | 3.64 |
| Crypto Trader | 6.5 | 6.5 | 1.2× | 7.8 |

---

## 2.3 Distribution Collapse Detection

### Amount Distribution
**Method used:** Linear ±30% scaling per user (`random.uniform(0.7, 1.3)`)
**Expected:** Log-normal distribution
**Actual:** Bounded uniform distribution per-user, then mixture across users

**Finding:** The per-user amount scale factor is uniform [0.7, 1.3] rather than log-normal. This creates an artificial rectangular distribution of user means within each persona class. True financial data exhibits much longer tails (a few users spend 10×–50× the average).

### Daily Spend Distribution
**Method:** Poisson approximated by Gaussian: `int(random.gauss(λ, √λ))`

For Senior (λ=1.4): Gaussian approximation is inaccurate.
- True Poisson P(X=0) = e^(-1.4) ≈ 0.247
- Gaussian approximation P(X≤0) = Φ(-√1.4) = Φ(-1.18) ≈ 0.119
- Zero-transaction days under-represented by ~50%

For Crypto Trader (λ=6.5): Gaussian is accurate (λ > 5).

### Device Count Distribution
- Range-based uniform selection: `random.randint(lo, hi)` 
- Discrete uniform, not reflecting real ownership power law
- In reality, device ownership follows power law (most users: 1 device; few: 5+)

### Merchant Count
- Derived from persona preferred_merchants list (5–7 categories)
- Monthly merchant diversity not independently modeled — follows spending frequency
- No explicit merchant repeat-visit probability

---

## 2.4 Synthetic Artifact Detection

| Artifact | Detected? | Severity | Details |
|---|---|---|---|
| Distribution Collapse | Partial | WARNING | Per-user scaling bounded uniform |
| Artificial Clustering | Yes | WARNING | Income clusters around persona midpoints |
| Extreme Skew | No | OK | CV values are realistic |
| Timestamp Regularity | Yes | CRITICAL | Ring generators use fixed 6h/8h cadences |
| Amount Uniformity | Partial | WARNING | Linear ±30% scale |
| Merchant Repetition Bias | Yes | WARNING | Card testing always "gaming" category |
| IP Artificiality | Yes | CRITICAL | 192.168.x.x range in ring transactions |

---

## 2.5 Income Distribution Validation

Using `_income_for_persona()`:
```
sample = lognormal(0, 0.4)
value = lo + (hi - lo) * (sample / (sample + 1))
```

For Student (lo=5000, hi=15000):
- sample/(sample+1) ∈ (0, 1) — correct
- Expected value of lognormal(0, 0.4) ≈ e^(0 + 0.08) ≈ 1.08
- Expected sample/(1+sample) ≈ 0.52
- Expected income ≈ 5000 + 10000 × 0.52 = 10,200 INR

**This is reasonable.** The distribution is not truly log-normal but approximates one.

**WARNING:** Kurtosis not computed. Extreme values (outlier salaries at 3× median) not modeled.

---

## 2.6 Statistical Tests Required but Not Run

| Test | Data Needed | Status |
|---|---|---|
| Shapiro-Wilk (normality) | Generated amounts | NOT POSSIBLE (no live data) |
| KS Test vs log-normal | Generated amounts | NOT POSSIBLE |
| Chi-square (temporal) | Timestamp distribution | NOT POSSIBLE |
| Levene's Test (variance equality) | Cross-persona amounts | NOT POSSIBLE |
| Anderson-Darling | Amount distribution | NOT POSSIBLE |

**Note:** Full statistical testing requires running the generators and collecting sample data. This report is code-path analysis only.

---

## CRITICAL FINDINGS
1. Ring transaction timestamps have artificial fixed cadence (6h, 8h grids) — distributions are not continuous
2. 192.168.x.x IPs create artificial clustering in network features

## WARNINGS
1. Amount distribution uses linear scaling not log-normal
2. Gaussian Poisson approximation under-samples zero-transaction days for low-frequency personas
3. Merchant diversity driven by persona definition lists, not organic repeat-visit modeling
4. No kurtosis/skewness validation built into dataset_validator

---

**Statistical Quality Score: 68 / 100**
