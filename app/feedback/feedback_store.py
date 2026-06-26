"""
Feedback Store — persists analyst decisions, false positives/negatives,
and investigation outcomes.

Schema is append-only: corrections are new rows, not updates.
Feedback records include device_id and merchant_id at submission time so
the reputation updater never has to parse free-text notes.
"""

import json
import logging
import uuid
import aiosqlite
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from enum import Enum

_logger = logging.getLogger(__name__)

DB_PATH = "fraud_feedback.db"


class OutcomeLabel(str, Enum):
    true_positive = "true_positive"      # correctly caught fraud
    false_positive = "false_positive"    # legitimate transaction blocked
    true_negative = "true_negative"      # correctly approved
    false_negative = "false_negative"    # missed fraud
    unknown = "unknown"


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id TEXT PRIMARY KEY,
                transaction_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                device_id TEXT,
                merchant_id TEXT,
                system_decision TEXT NOT NULL,
                system_risk_score REAL,
                analyst_decision TEXT,
                outcome_label TEXT NOT NULL DEFAULT 'unknown',
                fraud_type_confirmed TEXT,
                notes TEXT,
                created_at TEXT NOT NULL,
                reviewer_id TEXT,
                processed_at TEXT
            )
        """)
        # Run column migrations BEFORE creating indexes that reference new columns
        for col, definition in [
            ("device_id", "TEXT"),
            ("merchant_id", "TEXT"),
            ("processed_at", "TEXT"),
        ]:
            try:
                await db.execute(f"ALTER TABLE feedback ADD COLUMN {col} {definition}")
            except Exception:
                pass  # column already exists

        # Dedup: same analyst cannot submit twice for the same transaction.
        # COALESCE maps NULL reviewer_id to '' so anonymous submissions are also deduplicated.
        await db.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_dedup
            ON feedback(transaction_id, COALESCE(reviewer_id, ''))
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_outcome ON feedback(outcome_label)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_created ON feedback(created_at)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_processed ON feedback(processed_at)
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS pattern_updates (
                id TEXT PRIMARY KEY,
                pattern_name TEXT NOT NULL,
                update_type TEXT NOT NULL,
                old_config TEXT,
                new_config TEXT,
                reason TEXT,
                triggered_by_feedback_id TEXT,
                created_at TEXT NOT NULL
            )
        """)
        await db.commit()


async def submit_feedback(
    transaction_id: str,
    user_id: str,
    system_decision: str,
    system_risk_score: float,
    analyst_decision: str,
    outcome_label: OutcomeLabel,
    fraud_type_confirmed: Optional[str] = None,
    notes: Optional[str] = None,
    reviewer_id: Optional[str] = None,
    device_id: Optional[str] = None,
    merchant_id: Optional[str] = None,
) -> str:
    feedback_id = f"fb_{uuid.uuid4().hex}"  # full 128-bit UUID for collision safety
    now = datetime.now(timezone.utc).isoformat()

    # Guard against oversized payloads
    if notes and len(notes) > 2000:
        _logger.warning(
            "FeedbackStore: notes truncated to 2000 chars for txn=%r", transaction_id
        )
        notes = notes[:2000]

    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute("""
                INSERT INTO feedback
                (id, transaction_id, user_id, device_id, merchant_id,
                 system_decision, system_risk_score, analyst_decision,
                 outcome_label, fraud_type_confirmed, notes, created_at, reviewer_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                feedback_id, transaction_id, user_id, device_id, merchant_id,
                system_decision, system_risk_score, analyst_decision,
                outcome_label.value, fraud_type_confirmed, notes, now, reviewer_id,
            ))
            await db.commit()
        except aiosqlite.IntegrityError:
            _logger.warning(
                "FeedbackStore: duplicate submission for txn=%r reviewer=%r — returning existing id",
                transaction_id, reviewer_id,
            )
            async with db.execute(
                "SELECT id FROM feedback WHERE transaction_id = ? AND COALESCE(reviewer_id, '') = COALESCE(?, '')",
                (transaction_id, reviewer_id or ""),
            ) as cur:
                row = await cur.fetchone()
                return row[0] if row else feedback_id

    _logger.info(
        "FeedbackStore: recorded outcome=%s txn=%r reviewer=%r id=%s",
        outcome_label.value, transaction_id, reviewer_id, feedback_id,
    )
    return feedback_id


async def record_pattern_update(
    pattern_name: str,
    update_type: str,
    old_config: dict,
    new_config: dict,
    reason: str,
    triggered_by_feedback_id: Optional[str] = None,
) -> str:
    """Write an audit trail entry for pattern threshold/weight changes."""
    update_id = f"pu_{uuid.uuid4().hex}"
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO pattern_updates
            (id, pattern_name, update_type, old_config, new_config,
             reason, triggered_by_feedback_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            update_id, pattern_name, update_type,
            json.dumps(old_config), json.dumps(new_config),
            reason, triggered_by_feedback_id, now,
        ))
        await db.commit()
    _logger.info(
        "FeedbackStore: pattern_update recorded pattern=%r type=%r id=%s",
        pattern_name, update_type, update_id,
    )
    return update_id


async def get_feedback_stats() -> Dict[str, Any]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT outcome_label, COUNT(*) FROM feedback GROUP BY outcome_label"
        ) as cur:
            counts = {row[0]: row[1] async for row in cur}

        async with db.execute("SELECT COUNT(*) FROM feedback") as cur:
            row = await cur.fetchone()
            total = row[0] if row else 0

        async with db.execute("""
            SELECT outcome_label, AVG(system_risk_score)
            FROM feedback GROUP BY outcome_label
        """) as cur:
            avg_scores = {row[0]: round(row[1], 2) async for row in cur}

        async with db.execute("""
            SELECT fraud_type_confirmed, COUNT(*)
            FROM feedback
            WHERE outcome_label = 'false_negative'
            GROUP BY fraud_type_confirmed
        """) as cur:
            missed_types = {row[0]: row[1] async for row in cur}

    tp = counts.get("true_positive", 0)
    fp = counts.get("false_positive", 0)
    tn = counts.get("true_negative", 0)
    fn = counts.get("false_negative", 0)

    precision = tp / (tp + fp) if (tp + fp) > 0 else None
    recall = tp / (tp + fn) if (tp + fn) > 0 else None
    # Explicit None checks: 0.0 is falsy in Python but is a valid precision/recall value
    if precision is not None and recall is not None and (precision + recall) > 0:
        f1 = 2 * precision * recall / (precision + recall)
    else:
        f1 = None

    return {
        "total_feedback": total,
        "outcome_counts": counts,
        "avg_risk_scores_by_outcome": avg_scores,
        "missed_fraud_types": missed_types,
        "metrics": {
            "precision": round(precision, 4) if precision is not None else None,
            "recall": round(recall, 4) if recall is not None else None,
            "f1_score": round(f1, 4) if f1 is not None else None,
            "false_positive_rate": round(fp / (fp + tn), 4) if (fp + tn) > 0 else None,
        },
    }


async def get_unprocessed_feedback(limit: int = 200) -> List[Dict[str, Any]]:
    """Return records not yet processed by the reputation updater (high-watermark)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM feedback WHERE processed_at IS NULL ORDER BY created_at ASC LIMIT ?",
            (limit,),
        ) as cur:
            return [dict(row) async for row in cur]


async def mark_feedback_processed(feedback_ids: List[str]) -> None:
    """Set processed_at on the given records — idempotent (only updates NULL rows)."""
    if not feedback_ids:
        return
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        placeholders = ",".join("?" * len(feedback_ids))
        await db.execute(
            f"UPDATE feedback SET processed_at = ? "
            f"WHERE id IN ({placeholders}) AND processed_at IS NULL",
            [now, *feedback_ids],
        )
        await db.commit()


async def get_recent_feedback(limit: int = 50) -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM feedback ORDER BY created_at DESC LIMIT ?", (limit,)
        ) as cur:
            return [dict(row) async for row in cur]


async def get_false_positives(limit: int = 20) -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM feedback WHERE outcome_label = 'false_positive' "
            "ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ) as cur:
            return [dict(row) async for row in cur]
