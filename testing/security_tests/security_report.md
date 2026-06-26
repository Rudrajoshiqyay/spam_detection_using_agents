# Phase 18 — Security Testing Report
**Date:** 2026-06-23 | **Auditor:** QA Agent | **Mode:** READ-ONLY

---

## 18.1 Security Testing Scope

**Method:** Code-path analysis for OWASP Top 10 and API security vulnerabilities
**Focus:** Input validation, injection risks, authentication, CORS, data exposure

---

## 18.2 CORS Configuration

```python
# main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # ← WILDCARD
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Vulnerability:** `allow_origins=["*"]` with `allow_credentials=True`

This combination is explicitly prohibited by the Fetch specification. Browsers will reject credentialed requests with wildcard origins. However, if credentials are sent from same-origin or CORS is bypassed (e.g., Postman, server-to-server), all endpoints are accessible without origin restrictions.

**Severity: HIGH**
**CVE-analogous pattern:** CORS misconfiguration enabling cross-origin data access

---

## 18.3 Input Validation Analysis

### /detect Endpoint Input

```python
class FraudDetectionRequest(BaseModel):
    transaction_id: str
    user_id: str
    amount: float
    ...
```

**Test V1: Negative Amount**
```json
{"amount": -50000.0}
```
No validator prevents negative amounts. In fast_screening:
```python
amount_ratio = txn.amount / max(avg, 1)
```
With negative amount: `amount_ratio = -50000 / 5000 = -10.0`
`abs(-10.0) > 3.0` → triggers amount_anomaly = 25
**Effect:** Negative amounts trigger fraud detection (correct behavior, wrong reason). No error returned.

**Test V2: Extremely Large Amount**
```json
{"amount": 1e18}
```
amount_ratio = 1e18 / 5000 = 2e14 → amount_anomaly = 25 (capped)
**Effect:** Handled gracefully by capping. ✓

**Test V3: Null transaction_id**
```json
{"transaction_id": null}
```
Pydantic would reject None for `str` type → 422 Unprocessable Entity
**Status: ✓ Protected by Pydantic**

**Test V4: SQL Injection in user_id**
```json
{"user_id": "'; DROP TABLE ground_truth; --"}
```
Ground truth store uses:
```python
await db.execute("INSERT INTO ground_truth VALUES (?,?,?,...)", (txn_id, user_id, ...))
```
Parameterized queries used → **SQL injection safe** ✓

**Test V5: XSS in transaction fields**
```json
{"merchant_name": "<script>alert('xss')</script>"}
```
Fields stored in SQLite and returned in API responses.
If responses are rendered in a browser without sanitization → XSS risk.
FastAPI returns JSON → browser won't execute scripts in JSON responses.
**Status: ✓ Protected (JSON responses)**

---

## 18.4 Corrupted Input Handling

### Test C1: Missing Required Fields
```json
{"transaction_id": "txn_001"}  # missing amount, user_id, etc.
```
Pydantic: raises `ValidationError` → 422 response ✓

### Test C2: Wrong Data Types
```json
{"amount": "five thousand"}  # string instead of float
```
Pydantic: raises `ValidationError` → 422 ✓

### Test C3: Infinity/NaN Amount
```json
{"amount": Infinity}
```
JSON doesn't support `Infinity` natively → JSON parse error ✓
If passed as Python float before serialization: `fast_screening` would compute NaN ratios.

```python
amount_ratio = float('inf') / 5000  # → inf
abs(inf) > 3.0  # → True → amount_anomaly = 25
```
Handled gracefully by inf comparison. ✓

### Test C4: Empty String user_id
```json
{"user_id": ""}
```
Pydantic accepts empty string (str type). An empty user_id would:
- Fail feature store lookup (no history for "")
- Return default behavioral scores
- Process without error (no validation for non-empty string)

**Status: ⚠️ WARNING — Empty user_id accepted, silently uses defaults**

---

## 18.5 Authentication & Authorization Analysis

**Finding: No authentication mechanism detected on any endpoint.**

```python
@app.post("/detect")
async def detect_fraud(request: FraudDetectionRequest):
    # No auth header check
    # No API key validation
    # No JWT verification
    result = await pipeline.process_transaction(...)
```

**Implication:**
- Any IP can call `/detect` with any user_id and receive risk scores
- Any IP can call `/simulate/full` to generate fraud patterns
- Any IP can call `/metrics/evaluation` to get system performance data
- System internal metrics exposed without authentication

**Severity: CRITICAL for production deployment**

**Note:** This may be intentional for development/demo purposes. The code doesn't indicate production hardening has been applied.

---

## 18.6 Data Exposure Analysis

### /metrics/evaluation Response
```python
return {
    "accuracy": ...,
    "precision": ...,
    "total_transactions": total,
    "fraud_count": fraud_count,
    ...
}
```

Exposes transaction volume and fraud rate to any caller. This could reveal business intelligence to competitors or attackers who want to understand detection sensitivity.

### Ground Truth DB Exposure

```python
# ground_truth.db stored on disk
# No encryption at rest
# accessible via SQLite browser if filesystem access obtained
```

Contains: transaction IDs, user IDs, fraud labels, campaign types, attack generations.
**Status: ⚠️ WARNING — PII-adjacent data stored unencrypted**

### LangGraph State Exposure

The LangGraph state dictionary contains full transaction context, all agent scores, consensus results. If any endpoint accidentally serializes the full state (debug endpoint), all internal scores are exposed.

---

## 18.7 Malicious Payload Testing

### Test M1: Payload Designed to Maximize Score
```json
{
  "user_id": "victim_001",
  "amount": 0.01,          # minimum amount → no amount anomaly
  "device_id": "known_device_001",  # known device → no device novelty
  "location_city": "Mumbai",        # known city → no location flag
  "transaction_type": "purchase",
  "timestamp": "2026-06-23T14:00:00"  # peak hours → no timing flag
}
```

**Effect:** Estimated pre_risk ≈ 5–15 → AUTO-APPROVE
**Finding:** A malicious actor who knows the system can craft transactions that will be auto-approved.

### Test M2: Payload Designed to Crash the Pipeline

```json
{
  "user_id": "a" * 10000,    # 10,000 character user_id
  "amount": 1.0
}
```

**Effect:** 
- SQLite parameter: string stored in DB (may cause performance issues but not crash)
- Feature store lookup: 10KB key (performance degradation)
- No validation for max string length

**Status: ⚠️ No max-length validation on string fields**

---

## 18.8 Simulation Endpoint Security

### /simulate/full endpoint
Generates entire fraud simulation populations with campaigns and rings.
- No authentication
- Can be called repeatedly to build knowledge of detection patterns
- Each call generates new `campaign_id` and `ring_id`

**Risk:** Adversary can call `/simulate/full` thousands of times to:
1. Study which parameters trigger what detection outcomes
2. Learn effective bypass mutations by testing different Gen levels
3. Map the detection decision boundaries

**Status: CRITICAL — simulation endpoints are also unauthenticated**

---

## 18.9 Security Summary

| Category | Finding | Severity |
|---|---|---|
| CORS | allow_origins=["*"] + allow_credentials | HIGH |
| Authentication | No auth on any endpoint | CRITICAL |
| SQL Injection | Parameterized queries used | ✓ SAFE |
| XSS | JSON responses not executable | ✓ SAFE |
| Input Validation | Empty user_id accepted silently | WARNING |
| Data Exposure | Metrics accessible without auth | HIGH |
| Data at Rest | SQLite unencrypted | WARNING |
| String Length | No max length validation | WARNING |
| Simulation Security | Endpoints exploitable for recon | CRITICAL |

---

## CRITICAL FINDINGS
1. No authentication or authorization on any endpoint — open to the internet
2. Simulation endpoints allow systematic reconnaissance of detection logic
3. CORS wildcard with credentials violates Fetch spec and may enable CSRF

## WARNINGS
1. Empty user_id silently uses default scores (ghost transactions)
2. Ground truth SQLite not encrypted at rest
3. Metrics endpoint exposes transaction volumes and fraud rates
4. No rate limiting — enables credential stuffing or brute-force pattern discovery

---

**Security Score: 35 / 100**
