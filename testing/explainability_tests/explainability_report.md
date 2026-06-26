# Phase 14 — Explainability Testing Report
**Date:** 2026-06-23 | **Auditor:** QA Agent | **Mode:** READ-ONLY

---

## 14.1 Explainability Architecture

**Required:** 3-level explanation hierarchy
- Level 1: Technical (for models/engineers)
- Level 2: Analyst (for fraud analysts)
- Level 3: Customer-facing (for account holders)

**LangGraph Nodes Involved:**
- `explainability` node: generates technical explanation
- `analyst` node: generates analyst-level summary
- `storytelling` node: generates customer-facing narrative

---

## 14.2 Level 1 — Technical Explanation Tests

### Expected Technical Output Components

Based on LangGraph pipeline structure:
1. Per-agent risk scores (behavior, device, geo, merchant, graph)
2. Consensus formula inputs (blended_risk, agreement_score, confidence)
3. Triggering factors (which components exceeded thresholds)
4. Feature attribution (which transaction fields drove each score)
5. Pre-risk decomposition (7 component scores)

### Test E1: Technical Explanation — High Fraud Case
```
Input: ATO attempt (Gen1, no mutations)
Expected technical output includes:
  - pre_risk: 75.0
  - velocity_score: 20.0
  - device_novelty_score: 25.0
  - behavior_agent_score: 88.0
  - device_agent_score: 92.0
  - geo_agent_score: 85.0
  - blended_risk: 79.0
  - agreement_score: 95.9
```

**Assessment:** If all pipeline nodes execute, these values ARE calculated and stored in state.
The explainability node can access them from LangGraph state.

**Risk:** If auto-approve fires (pre_risk < 35), none of the agent scores exist.
Auto-approve provides NO technical explanation — only hardcoded confidence values.
**Status: PARTIAL — technical explanations only exist for escalated transactions**

---

### Test E2: Technical Explanation — Auto-Approved Case
```
Input: normal transaction, pre_risk = 12
Expected: explanation of WHY it was approved
Actual: ConsensusResult with hardcoded values (100, 85)
Agent scores: None (agents never ran)
Feature scores: Not stored from fast_screening
```

**Status: FAIL — auto-approved transactions have no meaningful technical explanation**

---

## 14.3 Level 2 — Analyst Explanation Tests

### Expected Analyst Output
1. Human-readable summary of risk factors
2. Timeline of suspicious events
3. Comparison to peer group behavior
4. Confidence in fraud verdict with uncertainty range
5. Recommended action (block/flag/monitor/approve)

### Test E3: Analyst Explanation — Money Mule
```
Expected: "Transaction shows mule network pattern: single large injection
(₹45,000) followed by rapid layering across 3 accounts over 2 days.
Graph intelligence shows 3 linked accounts. Confidence: 87%."
```

**Assessment:** The `analyst` LangGraph node would generate this via LLM. Quality depends entirely on:
1. LLM prompt quality (not audited — prompt content not in source files read)
2. Whether graph intelligence data is passed to the analyst node
3. Whether the mule network pattern was detected by graph_intelligence

**Risk:** If graph_intelligence singleton was just initialized (cold start), mule pattern signal is missing from analyst context.

---

### Test E4: Analyst Explanation — Disagreeing Agents
```
behavior_agent: FRAUD (90)
device_agent: LEGITIMATE (20)
Agreement: 53.77 (low)
```

**Expected analyst output:** "Behavioral patterns strongly suggest fraud, however device context is inconsistent. Low agreement between agents. Recommend human review."

**Actual:** Depends on LLM output from `analyst` node. The consensus data (agreement_score=53.77) should be in state.

**Status: UNCERTAIN — LLM quality of analyst node not validated**

---

## 14.4 Level 3 — Customer-Facing Explanation Tests

### Test E5: Customer Explanation — Blocked Transaction
```
Expected: "Your transaction was declined for security reasons. 
If this was you, please contact support or verify your identity."
```

**Assessment:** The `storytelling` node generates this. LLM-based.

**Requirements for good customer explanation:**
1. No technical jargon
2. No leakage of fraud detection logic
3. Actionable next steps
4. Appropriate tone (not accusatory)

**Risk of information leakage:** If the storytelling prompt includes the full technical explanation, the LLM might inadvertently include details like "your IP address was flagged" or "your device is new."

---

### Test E6: Customer Explanation — High Net Worth False Positive
```
Legitimate: HNW customer buys jewelry (₹200,000)
System: escalates due to amount anomaly
Customer receives: "Transaction blocked for security"
```

**Issue:** Customer has no way to know what triggered the block. No appeal path described. No explanation of why their normal purchase was flagged.

**Status: UNCERTAIN — dependent on storytelling LLM output quality**

---

## 14.5 Explanation Completeness Matrix

| Level | ATO (Detected) | Gen4 (Missed) | Auto-Approved | Cold Start |
|---|---|---|---|---|
| L1: Technical | ✓ | N/A (not detected) | ✗ (hardcoded) | ✗ (no graph) |
| L2: Analyst | ✓ (LLM-dependent) | N/A | ✗ | ⚠️ (partial) |
| L3: Customer | ✓ (LLM-dependent) | N/A | ✗ | ⚠️ (partial) |

**Explanation coverage for detected fraud: ~70% (pending LLM quality)**
**Explanation coverage for auto-approved: 0% meaningful**

---

## 14.6 SHAP / Feature Attribution Analysis

**Finding:** No SHAP, LIME, or feature attribution framework implemented.

The "explainability" in the pipeline is LLM-generated narrative, not algorithmic feature importance.

**Gap:** For regulatory compliance (RBI guidelines, EU AI Act), fraud decisions may require algorithmic explainability, not just LLM-generated summaries.

**Risk:** LLM explanations can be:
- Hallucinated (confident but wrong about why a decision was made)
- Variable (same transaction, different explanation on each call)
- Not reproducible (cannot audit "why was this blocked on June 23rd?")

---

## 14.7 Counterfactual Explanation Gaps

**Not implemented:** "What would need to change for this transaction to be approved?"

For a blocked transaction:
- Would a smaller amount pass? (reduce_amount counterfactual)
- Would a known device pass? (device counterfactual)
- Would a domestic location pass? (location counterfactual)

These counterfactuals would be valuable for:
1. Fraud analysts understanding detection sensitivity
2. Adversarial testing (what mutations would bypass detection)
3. Customer appeals process

---

## CRITICAL FINDINGS
1. Auto-approved transactions (estimated 40–60% of all) have zero meaningful explanation
2. No algorithmic feature attribution (SHAP/LIME) — only LLM narrative
3. LLM explanations cannot be audited retroactively (non-reproducible)

## WARNINGS
1. Cold-start graph intelligence leaves ring context missing from analyst explanations
2. Customer-facing explanations risk unintentional information leakage via LLM
3. No counterfactual explanation capability
4. 3-level explanation hierarchy only active for escalated/blocked transactions

---

**Explainability Score: 58 / 100**
