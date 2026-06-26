# FraudGuard AI — Red Team Hardening Report
**Date:** 2026-06-23 | **Sprint:** Remediation Sprint 1

---

## Bypass Rate Before Hardening: 68.3% (683/1000 attacks)

---

## Root Cause Analysis — Bypass Patterns

### Pattern A: Stage 1 Bypass via Trusted Artifact Spoofing (72% bypass rate)

**Attack:** Gen4 mutations combine `use_trusted_device + mimic_location + reduce_amount + slow_velocity`
**Why it works:** Each mutation individually removes one fast-screening signal component.
Combined, pre_risk drops below the auto-approve threshold (35), and LangGraph agents never run.

```
device_novelty=0 (known device)
location=0 (known city)
amount_anomaly=0 (within 1.8× avg)
velocity=0 (spread over 35min+)
→ pre_risk ≈ 5-15 → AUTO-APPROVE
```

**Hardening applied:** Consensus engine now penalises agent defaults. Agent failure is no longer transparent. Auto-approve path now generates graduated confidence (not hardcoded 100/85).

**Hardening NOT applied (requires Stage 1 enhancement):** Adding cross-session velocity check to Stage 1 would catch slow-velocity attacks. This is a structural change deferred to next sprint.

---

### Pattern B: Agent Failure Exploitation (35% bypass rate under LLM load)

**Attack:** Submit transactions at high load when LLM API is throttled.
All agents time out → all default to 50.0 → perfect consensus at medium risk → may approve.

**Fix applied (consensus_engine.py):**
```python
# Before: all-agent failure → std_dev=0 → agreement=100 (WRONG)
# After:
if len(agents_defaulted) == len(agent_scores):
    agreement_score = 0.0   # complete failure = zero confidence
else:
    base_agreement = max(0.0, 100.0 - std_dev * 1.5)
    agreement_score = max(0.0, base_agreement - len(agents_defaulted) * 10.0)
```

**Impact:** Full LLM failure now produces `agreement_score=0.0`. Downstream final_decision node must treat low-agreement as ESCALATE.

---

### Pattern C: Cold Start Graph Exploitation (90% bypass rate)

**Attack:** Execute ring fraud immediately after server restart. FraudGraph is empty — no ring signals.

**Root cause:** FraudGraph is module-level in-memory only. Restart loses all accumulated intelligence.

**Fix NOT applied this sprint** (requires Redis/DB persistence — architectural change).
**Mitigation documented:** Restart procedure should pre-warm graph from ground truth DB records before serving traffic. See `scalability_improvements.md`.

---

### Pattern D: Multi-Vector Ring Invisibility (95% bypass rate)

**Attack:** Use multi_vector_ring campaign. Was completely undetectable.

**Fix applied (fraud_ring_agent.py):**
- `generate_multi_vector_ring()` now builds a proper `FraudRingGraph`
- Merges device links and IP links from both sub-rings
- Returns full `node_count`, `edge_count`, and `edges` in result dict
- Graph intelligence can now detect device+IP clustering

**Expected bypass rate post-fix: 40–50%** (graph still has cold-start issue; detection depends on graph being populated)

---

### Pattern E: IP Cluster Ring False Detection (100% FP at scale)

**Attack (indirect):** IP detection degraded to noise at 10k users, forcing operators to disable signal.

**Fix applied (fraud_ring_agent.py):**
- Changed subnet from `192.168.x.x` (private) to `103.x.x.x` (realistic public ISP range)
- IP per user now consistent between graph and transaction records

**Residual risk:** IP pool still limited. At 100k users, even public IP pools will be shared by legitimate users. Dynamic threshold scaling needed (see scalability_improvements.md).

---

## Weakest Agents (by bypass contribution)

| Agent | Bypass Contribution | Weakness | Hardening Status |
|---|---|---|---|
| Fast Screening (Stage 1) | 72% | Gen4 mutations reduce all 7 components | Partial (agent fallback improved) |
| Graph Agent | 95% | Multi-vector ring had no graph | ✅ FIXED |
| IP Detection | 100% at scale | IP pool exhaustion + IP mismatch | ✅ IP mismatch FIXED |
| Behavior Agent | 35% | Defaults to 50 on LLM failure | ✅ Default penalty FIXED |
| Device Agent | 35% | Defaults to 50 on LLM failure | ✅ Default penalty FIXED |

---

## Weakest Rules

| Rule | Issue | Bypass Probability | Status |
|---|---|---|---|
| Velocity (1h window) | slow_velocity mutation spreads to 35min gaps | 90% | Not fixed (structural) |
| Amount anomaly | reduce_amount brings txn within 1.8× avg | 85% | Not fixed (need peer-group) |
| Device novelty | use_trusted_device uses victim's real device | 95% | Not fixed (cross-channel needed) |
| Merchant risk | use_trusted_merchant: 50% of target category | 60% | Not fixed |
| Location check | mimic_location uses victim's known city | 95% | Not fixed |

---

## Weakest Consensus Pathways

| Pathway | Issue | Fix Status |
|---|---|---|
| All agents fail → agreement=100 | Hardcoded std_dev(50,50,50,50,50)=0 | ✅ FIXED — agreement=0 on full failure |
| Auto-approve → agreement=100 | Hardcoded regardless of pre_risk | ✅ FIXED — graduated confidence |
| 3/5 agents fail → anchor to 50 | Partial failure still biases toward 50 | ✅ FIXED — 10pt penalty per failed agent |

---

## Expected Bypass Rate Post-Hardening

| Attack Vector | Before | After | Change |
|---|---|---|---|
| Gen4 mutations (Stage 1 bypass) | 72% | 65% | −7% (confidence now graduated) |
| Agent timeout exploitation | 35% | 8% | −27% (full-failure → agreement=0) |
| Multi-vector ring | 95% | 45% | −50% (graph now built) |
| IP cluster ring | 100% FP → disabled | 40% detection | +60% |
| Cold start graph | 90% | 90% | No change (requires persistence) |
| Cross-border mislabel | 60% | 10% | −50% (type now correct) |
| Threshold probing | 55% | 50% | −5% (graduated confidence) |

**Estimated overall bypass rate after fixes: ~45%** (down from 68.3%)

---

## Recommended Additional Hardening (Next Sprint)

1. **Cross-session velocity:** Track user_id velocity over 24h rolling window, not just 1h
2. **Cross-account device tracking:** Flag when device_id appears across 3+ user_ids within 6h
3. **Peer-group amount comparison:** Compare txn amount against cohort percentile, not just personal avg × 1.8
4. **Stage 1.5 check:** Between fast screening and LangGraph — pattern-match for known bypass signatures
5. **Graph persistence:** Pre-warm FraudGraph from ground truth DB on startup

---

**Red Team Defense Score Estimate After Fixes: 55 / 100** (up from 32)
