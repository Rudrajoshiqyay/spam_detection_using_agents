# FraudGuard AI — Complete Architecture

## Full System Diagram

```
╔══════════════════════════════════════════════════════════════════════════╗
║                    DATA GENERATION LAYER  [CORE]                        ║
╠══════════════════════════════════════════════════════════════════════════╣
║                                                                          ║
║  ┌─────────────┐  ┌──────────────┐  ┌─────────────┐  ┌──────────────┐  ║
║  │    User     │  │   Merchant   │  │   Device    │  │    Geo       │  ║
║  │  Generator  │  │  Generator   │  │  Generator  │  │  Generator   │  ║
║  │  (5 types)  │  │ (10 cats)    │  │ (3 modes)   │  │ (4 modes)    │  ║
║  └──────┬──────┘  └──────┬───────┘  └──────┬──────┘  └──────┬───────┘  ║
║         └────────────────┴─────────────────┴────────────────┘           ║
║                                     │                                    ║
║                          ┌──────────▼──────────┐                        ║
║                          │ Transaction Generator│                        ║
║                          │  batch / stream /    │                        ║
║                          │  JSON / JSONL        │                        ║
║                          └──────────┬───────────┘                        ║
╚═════════════════════════════════════╪════════════════════════════════════╝
                                      │
╔═════════════════════════════════════╪════════════════════════════════════╗
║              FRAUD INJECTION LAYER  [CORE]                               ║
╠═════════════════════════════════════╪════════════════════════════════════╣
║                          ┌──────────▼───────────┐                        ║
║                          │   Fraud Injector      │                        ║
║         ┌────────────────┤   (6 Scenario Types)  ├──────────────┐        ║
║         │                └───────────────────────┘              │        ║
║  ┌──────┴──────┐  ┌──────────────┐  ┌──────────────┐  ┌────────┴──────┐ ║
║  │  Account    │  │    Card      │  │    Money     │  │  Velocity     │ ║
║  │  Takeover   │  │   Testing    │  │    Mule      │  │   Attack      │ ║
║  └─────────────┘  └──────────────┘  └──────────────┘  └───────────────┘ ║
║  ┌──────────────────┐  ┌──────────────────────────────────────────────┐  ║
║  │ Merchant Abuse   │  │          Synthetic Identity Fraud            │  ║
║  └──────────────────┘  └──────────────────────────────────────────────┘  ║
║                                                                          ║
║                   ┌─────────────────────────────┐                       ║
║                   │     Scenario Builder Agent   │                       ║
║                   │  "fraud_ring_campaign" →     │                       ║
║                   │  1000 users, 10k txns,       │                       ║
║                   │  5 rings, 50 compromised     │                       ║
║                   └──────────────┬──────────────┘                       ║
╚══════════════════════════════════╪═══════════════════════════════════════╝
                                   │
                    ┌──────────────▼──────────────┐
                    │    Real-Time Event Stream    │
                    │  (in-memory / Redis Streams) │
                    └──────────────┬──────────────┘
                                   │
╔══════════════════════════════════╪═══════════════════════════════════════╗
║                 STAGE 1 — FAST SCREENING  [< 20ms]  [CORE]              ║
╠══════════════════════════════════╪═══════════════════════════════════════╣
║              ┌───────────────────▼───────────────────┐                  ║
║              │           Redis Feature Store          │  < 5ms           ║
║              │  avg_amount_30d • txn_count_1h •       │                  ║
║              │  known_devices • merchant_frequencies  │                  ║
║              └───────────────────┬───────────────────┘                  ║
║                                  │                                       ║
║  ┌───────────┐ ┌───────────┐ ┌───▼──────────┐ ┌──────────┐ ┌────────┐  ║
║  │ Velocity  │ │  Amount   │ │   Device     │ │ Merchant │ │  Geo   │  ║
║  │  Checks   │ │ Anomaly   │ │  Novelty     │ │  Risk    │ │ Check  │  ║
║  └─────┬─────┘ └─────┬─────┘ └──────┬───────┘ └────┬─────┘ └───┬────┘  ║
║        └─────────────┴──────────────┴──────────────┴───────────┘        ║
║                                      │                                   ║
║              ┌───────────────────────▼──────────────────────┐           ║
║              │      Behavioral Similarity Engine             │           ║
║              │  cosine_similarity(profile_vec, txn_vec)      │           ║
║              └───────────────────────┬──────────────────────┘           ║
║                                      │                                   ║
║              ┌───────────────────────▼──────────────────────┐           ║
║              │     pre_risk_score (0–100)                    │           ║
║              │                                               │           ║
║              │  score < 35  ─── AUTO APPROVE ──► END         │           ║
║              │  score ≥ 35  ─── DEEP INVESTIGATION ──────►  │           ║
║              └───────────────────────────────────────────────┘           ║
╚════════════════════════════════════════════════════════════════════════════╝
                                   │ (suspicious path only)
╔══════════════════════════════════╪════════════════════════════════════════╗
║          STAGE 2 — DEEP INVESTIGATION  [CORE]                            ║
╠══════════════════════════════════╪════════════════════════════════════════╣
║                                  │                                        ║
║  ┌────────────────────────────────▼────────────────────────────────────┐  ║
║  │                  Pre-Agent Deterministic Analysis                   │  ║
║  │            (all run concurrently via asyncio.gather)                │  ║
║  │                                                                     │  ║
║  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │  ║
║  │  │    Fraud     │  │  Sequence    │  │  Kill Chain  │              │  ║
║  │  │   Patterns   │  │Intelligence  │  │   Matching   │              │  ║
║  │  │  (7 types)   │  │  (sliding    │  │  (3 chains)  │              │  ║
║  │  │              │  │   window)    │  │              │              │  ║
║  │  └──────────────┘  └──────────────┘  └──────────────┘              │  ║
║  │                                                                     │  ║
║  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │  ║
║  │  │   Cohort     │  │    Risk      │  │  Negative    │              │  ║
║  │  │  Analysis    │  │    Delta     │  │   Signals    │              │  ║
║  │  │  (6 cohorts) │  │  (6 deltas) │  │  Framework   │              │  ║
║  │  └──────────────┘  └──────────────┘  └──────────────┘              │  ║
║  │                                                                     │  ║
║  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │  ║
║  │  │    Device    │  │   Merchant   │  │     Geo      │              │  ║
║  │  │  Reputation  │  │  Reputation  │  │   Velocity   │              │  ║
║  │  │   Engine     │  │   Engine     │  │   Engine     │              │  ║
║  │  └──────────────┘  └──────────────┘  └──────────────┘              │  ║
║  └─────────────────────────────────────────────────────────────────────┘  ║
║                                  │                                        ║
║  ┌───────────────────────────────▼─────────────────────────────────────┐  ║
║  │             Graph Intelligence Layer  (NetworkX)  < 50ms            │  ║
║  │   Users — Devices — Merchants — IPs — Transactions — Locations      │  ║
║  │   Detects: Fraud Rings • Shared Devices • Mule Networks             │  ║
║  └───────────────────────────────┬─────────────────────────────────────┘  ║
║                                  │                                        ║
║  ┌───────────────────────────────▼─────────────────────────────────────┐  ║
║  │              Evidence Builder Service                                │  ║
║  │  Aggregates all signals → compressed InvestigationPackage            │  ║
║  │  Strong / Medium / Weak reliability scoring                          │  ║
║  └───────────────────────────────┬─────────────────────────────────────┘  ║
║                                  │                                        ║
║  ┌───────────────────────────────▼─────────────────────────────────────┐  ║
║  │          Parallel LangGraph Agents  (asyncio.gather)  < 500ms       │  ║
║  │                                                                     │  ║
║  │  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌──────────┐ ┌───────┐  │  ║
║  │  │ Behavior  │ │  Device   │ │    Geo    │ │Merchant  │ │ Graph │  │  ║
║  │  │   Agent   │ │   Agent   │ │   Agent   │ │  Agent   │ │ Agent │  │  ║
║  │  │  25% wt   │ │  20% wt   │ │  20% wt   │ │ 15% wt   │ │20% wt │  │  ║
║  │  └─────┬─────┘ └─────┬─────┘ └─────┬─────┘ └─────┬────┘ └───┬───┘  │  ║
║  └────────┴─────────────┴─────────────┴─────────────┴───────────┴──────┘  ║
║                                  │                                        ║
╚══════════════════════════════════╪════════════════════════════════════════╝
                                   │
╔══════════════════════════════════╪════════════════════════════════════════╗
║              CONSENSUS ENGINE  [CORE]                                    ║
╠══════════════════════════════════╪════════════════════════════════════════╣
║                                  │                                        ║
║  risk_score      = Σ(agent_score × weight) × 0.70                        ║
║                  + pre_risk_score × 0.20                                  ║
║                  + signal_risk_score × 0.10                               ║
║                                                                           ║
║  agreement_score = 100 − std_dev(agent_scores) × 1.5                     ║
║  confidence_score = agreement_score × evidence_verdict_factor             ║
║                                                                           ║
║  Output: { risk_score: 92, agreement_score: 88, confidence_score: 95 }   ║
╚══════════════════════════════════╪════════════════════════════════════════╝
                                   │
╔══════════════════════════════════╪════════════════════════════════════════╗
║        DEEP INVESTIGATION PIPELINE  [CORE]                               ║
╠══════════════════════════════════╪════════════════════════════════════════╣
║                                  │                                        ║
║              ┌───────────────────▼───────────────────┐                   ║
║              │         Investigation Agent            │  deep_model       ║
║              │   verdict • fraud_probability • notes  │                   ║
║              └────────────────┬──────────────────────┘                   ║
║                               │                                           ║
║    ┌──────────────────────────▼──────────────────────────┐               ║
║    │           Counterfactual Analysis Engine             │               ║
║    │  "Would this still be suspicious if device known?"   │               ║
║    │  primary_contributor • contribution_score            │               ║
║    └──────────────────────────┬──────────────────────────┘               ║
║                               │                                           ║
║    ┌──────────────────────────▼──────────────────────────┐               ║
║    │              Explainability Agent                    │               ║
║    │  human_explanation  (customer-facing)                │               ║
║    │  analyst_explanation (technical)                     │               ║
║    │  executive_explanation (board-level)                 │               ║
║    └──────────────────────────┬──────────────────────────┘               ║
║                               │                                           ║
║    ┌──────────────────────────▼──────────────────────────┐               ║
║    │          Analyst Recommendation Agent                │               ║
║    │  APPROVED / MONITORING / STEP_UP_AUTH /              │               ║
║    │  TEMPORARY_HOLD / BLOCKED / ESCALATED                │               ║
║    └──────────────────────────┬──────────────────────────┘               ║
║                               │                                           ║
║    ┌──────────────────────────▼──────────────────────────┐               ║
║    │              Storytelling Agent                      │               ║
║    │  Human-readable fraud investigation narrative        │               ║
║    └──────────────────────────┬──────────────────────────┘               ║
║                               │                                           ║
║              ┌────────────────▼──────────────────────┐                   ║
║              │         Final Fraud Decision            │                   ║
║              └────────────────┬──────────────────────┘                   ║
╚═══════════════════════════════╪═══════════════════════════════════════════╝
                                │
╔═══════════════════════════════╪═══════════════════════════════════════════╗
║          FEEDBACK LEARNING LAYER  [CORE + OPTIONAL]                      ║
╠═══════════════════════════════╪═══════════════════════════════════════════╣
║                               │                                           ║
║  ┌────────────────────────────▼────────────────────────────────────────┐  ║
║  │                      Feedback Store  [CORE]                          │  ║
║  │  analyst_decision • outcome_label • fraud_type_confirmed • notes     │  ║
║  │  Metrics: precision • recall • F1 • false_positive_rate              │  ║
║  └────────────────────────────┬────────────────────────────────────────┘  ║
║                               │                                            ║
║       ┌───────────────────────┼───────────────────────┐                   ║
║       │                       │                       │                   ║
║  ┌────▼────────────┐  ┌───────▼────────────┐  ┌──────▼──────────────┐   ║
║  │  Pattern Weight  │  │   Pattern Discovery│  │  Reputation Updater │   ║
║  │  Adjustment      │  │   Agent  [OPTIONAL]│  │  [CORE]             │   ║
║  │  [CORE]          │  │   LLM-based        │  │  device • merchant  │   ║
║  │  deterministic   │  │   emerging fraud   │  │  user risk scores   │   ║
║  │  threshold tuning│  │   pattern mining   │  │  in Redis           │   ║
║  └──────────────────┘  └────────────────────┘  └─────────────────────┘   ║
║                               │                                            ║
║              ┌────────────────▼────────────────────┐                      ║
║              │  Future Detection Improvement         │                      ║
║              │  → Updated pattern thresholds         │                      ║
║              │  → Updated device/merchant trust      │                      ║
║              │  → Updated user risk profiles         │                      ║
║              └─────────────────────────────────────┘                      ║
╚════════════════════════════════════════════════════════════════════════════╝
```

---

## Data Flow: From Deterministic Math to LLM Context (The Evidence Builder)

The system bridges the gap between fast, raw mathematical signals and intelligent LLM reasoning using the **Evidence Builder Service**. This step is critical for minimizing latency, reducing LLM token costs, and maximizing explainability.

1. **Deterministic Services (e.g., NetworkX)**: Services like the Graph Intelligence Layer process raw data. For example, NetworkX detects if multiple accounts are using the same device and outputs raw flags (e.g., `{"shared_device_flag": True}`).
2. **Translation & Scrubbing (Evidence Builder)**: The Evidence Builder intercepts these raw dictionaries. It translates boolean flags into human-readable evidence strings (e.g., `"Device used by multiple accounts"`), scores their strength (Weak/Medium/Strong), and scrubs all fields of PII and potential prompt-injection attacks.
3. **The Investigation Package**: It bundles all these translated signals into a single, token-optimized JSON object called the `InvestigationPackage`.
4. **LangGraph Parallel Agents**: The LangGraph orchestrator (`fraud_pipeline.py`) takes this single package and uses `asyncio.gather` to feed exact copies of it to **5 parallel LLM agents** simultaneously. Because the evidence is already translated into clear text, the LLMs can instantly comprehend the signals without performing complex math themselves.

---

## Latency Budget

| Stage | Target | Notes |
|---|---|---|
| Feature Retrieval | < 5ms | Redis pipeline |
| Fast Screening | < 20ms | Deterministic, no I/O |
| Pre-Agent Analysis | < 80ms | asyncio.gather (concurrent) |
| Graph Intelligence | < 50ms | NetworkX in-memory |
| Evidence Builder | < 10ms | Pure aggregation |
| Parallel LLM Agents | < 500ms | 5 agents × haiku-4-5 |
| Consensus Engine | < 5ms | Math only |
| Investigation + Counterfactual | < 400ms | 2 agents parallel, sonnet-4-6 |
| Explainability + Analyst | < 400ms | 2 agents parallel |
| Storytelling | < 300ms | 1 agent |
| **End-to-End (deep path)** | **< 1.5s** | |
| **End-to-End (auto-approve)** | **< 30ms** | Bypasses all agents |

---

## CORE vs OPTIONAL Classification

### ✅ CORE — Must Build (already complete)

| Component | Justification |
|---|---|
| User Generator | Powers demo; without it no data exists |
| Transaction Generator | Core of data pipeline |
| Fraud Injector (6 types) | Required to produce fraud scenarios for demo |
| Scenario Builder | High hackathon impact: one call = full dataset |
| Fast Screening Layer | Latency requirement; bypasses LLM on safe txns |
| Redis Feature Store | Enables < 5ms feature retrieval |
| Behavioral Similarity Engine | No ML, instant demo value, no training needed |
| Fraud Pattern Library | Deterministic, high accuracy contribution |
| Sequence Intelligence Engine | Catches card testing / refund fraud missed by single-txn analysis |
| Kill Chain Matching | Shows AI "thinking in attack progressions" — high demo impact |
| Cohort Analysis | Adaptive thresholds; reduces false positives on normal-but-unusual behavior |
| Risk Delta Engine | Quantifies deviation; feeds explainability directly |
| Device Reputation Engine | Simple trust math; big accuracy uplift on ATO detection |
| Merchant Reputation Engine | Reduces false positives on trusted merchants |
| Geo Velocity Engine | Impossible travel = single strongest fraud signal |
| Negative Signal Framework | False positive reduction — critical for demo credibility |
| Graph Intelligence (NetworkX) | Fraud ring detection; high visual demo impact |
| Evidence Builder | Reduces LLM token usage; speeds up investigation |
| Evidence Reliability Framework | Makes explainability trustworthy (strong vs weak evidence) |
| Parallel LangGraph Agents | Core requirement — all 5 agents run concurrently |
| Consensus Engine | Aggregation layer; required for final score |
| Counterfactual Analysis | High explainability value — "what if" reasoning |
| Explainability Agent (3 levels) | Explicit requirement from spec |
| Analyst Recommendation Agent | Required output format |
| Storytelling Agent | Demo impact — human-readable narrative |
| Feedback Store | Shows learning loop; minimal complexity (SQLite) |
| Pattern Weight Adjustment | Deterministic, no LLM, shows system improves over time |
| Reputation Updater | Closes the feedback loop on device/merchant trust |

---

### 🟡 OPTIONAL — Build Only If Time Permits

| Component | Why Optional | Complexity | Accuracy Gain |
|---|---|---|---|
| **Pattern Evolution Agent (LLM)** | Deterministic weight adjustment already covers 90% of value; LLM adds marginal gain | Medium | Low |
| **Vector DB Similarity Search** | Behavioral similarity via cosine is sufficient for demo; vector DB adds infra overhead | High | Low-Medium |
| **Heavy ML Training Pipelines** | Requires labeled data, training time, model serving — out of scope for 1-month hackathon | Very High | Medium |
| **Kafka Integration** | Redis Streams fully covers real-time event needs at this scale | High | None |
| **Neo4j / Graph DB** | NetworkX covers all required graph algorithms in-memory; Neo4j adds persistence complexity with limited graph size benefit | High | None |
| **Full Device Fingerprinting** | Device ID + trust score covers the detection need; full browser fingerprinting adds little incremental value | Medium | Low |
| **Merchant Category Geocoding** | Static city data is sufficient for demo | Low | None |
| **Real-time Kafka Consumer** | In-memory stream simulation is demo-sufficient | High | None |
| **Distributed Graph Infrastructure** | Graph fits in memory for hackathon scale | Very High | None |
| **Model Fine-tuning** | Pre-trained Claude performs well enough on fraud prompts | Very High | Low |

---

## Component Accuracy Contribution Table

| Component | Accuracy Contribution | Latency Impact | Complexity |
|---|---|---|---|
| Geo Velocity Engine | ⭐⭐⭐⭐⭐ | < 1ms | Low |
| Kill Chain Matching | ⭐⭐⭐⭐⭐ | < 5ms | Low |
| Sequence Intelligence | ⭐⭐⭐⭐⭐ | < 15ms | Low |
| Fraud Pattern Library | ⭐⭐⭐⭐ | < 5ms | Low |
| Graph Intelligence | ⭐⭐⭐⭐ | < 50ms | Medium |
| Device Reputation | ⭐⭐⭐⭐ | < 3ms | Low |
| Cohort Analysis | ⭐⭐⭐ | < 5ms | Low |
| Risk Delta Engine | ⭐⭐⭐ | < 1ms | Low |
| Negative Signal Framework | ⭐⭐⭐ | < 1ms | Low |
| Parallel LLM Agents | ⭐⭐⭐ | < 500ms | Medium |
| Counterfactual Agent | ⭐⭐ | < 200ms | Medium |
| Vector DB Similarity | ⭐⭐ | < 10ms | High |
| ML Training Pipeline | ⭐⭐⭐ | offline | Very High |
| Pattern Evolution LLM | ⭐⭐ | offline | Medium |
