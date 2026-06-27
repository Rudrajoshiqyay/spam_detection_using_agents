"""
Feedback Store — persists analyst decisions, false positives/negatives,
and investigation outcomes.

Backend: SQLAlchemy Core async.
  - Dev/test:   sqlite+aiosqlite:///./fraud_feedback.db  (default)
  - Production: postgresql+asyncpg://...  (Neon)

Schema is append-only: corrections are new rows, not updates.
Feedback records include device_id and merchant_id at submission time so
the reputation updater never has to parse free-text notes.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from enum import Enum

from sqlalchemy import text, bindparam
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from sqlalchemy.exc import IntegrityError

from app.config import settings

_logger = logging.getLogger(__name__)

_engine: Optional[AsyncEngine] = None


def _get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        url = settings.database_url
        kwargs: Dict[str, Any] = {}
        if url.startswith("postgresql"):
            import ssl as _ssl
            ssl_ctx = _ssl.create_default_context()
            kwargs["connect_args"] = {"ssl": ssl_ctx}
            # Neon free tier allows 100 connections — keep pool small per instance
            kwargs["pool_size"] = 3
            kwargs["max_overflow"] = 5
            kwargs["pool_timeout"] = 30
        _engine = create_async_engine(url, **kwargs)
        _logger.debug(
            "FeedbackStore: engine created (%s)",
            url.split("@")[-1] if "@" in url else url,
        )
    return _engine


async def close_db() -> None:
    """Dispose the engine and release all pooled connections. Call on shutdown."""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _logger.info("FeedbackStore: database engine disposed")


class OutcomeLabel(str, Enum):
    true_positive = "true_positive"      # correctly caught fraud
    false_positive = "false_positive"    # legitimate transaction blocked
    true_negative = "true_negative"      # correctly approved
    false_negative = "false_negative"    # missed fraud
    unknown = "unknown"


async def init_db():
    engine = _get_engine()
    is_pg = engine.url.drivername.startswith("postgresql")

    async with engine.begin() as conn:
        await conn.execute(text("""
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
        """))

        for col, definition in [
            ("device_id", "TEXT"),
            ("merchant_id", "TEXT"),
            ("processed_at", "TEXT"),
        ]:
            if is_pg:
                await conn.execute(text(
                    f"ALTER TABLE feedback ADD COLUMN IF NOT EXISTS {col} {definition}"
                ))
            else:
                try:
                    await conn.execute(text(f"ALTER TABLE feedback ADD COLUMN {col} {definition}"))
                except Exception:
                    pass  # column already exists in SQLite

        await conn.execute(text("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_dedup
            ON feedback(transaction_id, COALESCE(reviewer_id, ''))
        """))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_outcome ON feedback(outcome_label)"
        ))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_created ON feedback(created_at)"
        ))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_processed ON feedback(processed_at)"
        ))
        await conn.execute(text("""
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
        """))


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

    if notes and len(notes) > 2000:
        _logger.warning(
            "FeedbackStore: notes truncated to 2000 chars for txn=%r", transaction_id
        )
        notes = notes[:2000]

    engine = _get_engine()
    try:
        async with engine.begin() as conn:
            await conn.execute(text("""
                INSERT INTO feedback
                (id, transaction_id, user_id, device_id, merchant_id,
                 system_decision, system_risk_score, analyst_decision,
                 outcome_label, fraud_type_confirmed, notes, created_at, reviewer_id)
                VALUES (:id, :txn, :uid, :did, :mid,
                        :sys_dec, :risk, :ana_dec,
                        :label, :fraud_type, :notes, :now, :reviewer)
            """), {
                "id": feedback_id, "txn": transaction_id, "uid": user_id,
                "did": device_id, "mid": merchant_id,
                "sys_dec": system_decision, "risk": system_risk_score,
                "ana_dec": analyst_decision, "label": outcome_label.value,
                "fraud_type": fraud_type_confirmed, "notes": notes,
                "now": now, "reviewer": reviewer_id,
            })
    except IntegrityError:
        _logger.warning(
            "FeedbackStore: duplicate submission for txn=%r reviewer=%r — returning existing id",
            transaction_id, reviewer_id,
        )
        async with engine.connect() as conn:
            result = await conn.execute(text(
                "SELECT id FROM feedback "
                "WHERE transaction_id = :txn AND COALESCE(reviewer_id, '') = COALESCE(:reviewer, '')"
            ), {"txn": transaction_id, "reviewer": reviewer_id or ""})
            row = result.fetchone()
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
    async with _get_engine().begin() as conn:
        await conn.execute(text("""
            INSERT INTO pattern_updates
            (id, pattern_name, update_type, old_config, new_config,
             reason, triggered_by_feedback_id, created_at)
            VALUES (:id, :name, :utype, :old, :new, :reason, :ref, :now)
        """), {
            "id": update_id, "name": pattern_name, "utype": update_type,
            "old": json.dumps(old_config), "new": json.dumps(new_config),
            "reason": reason, "ref": triggered_by_feedback_id, "now": now,
        })
    _logger.info(
        "FeedbackStore: pattern_update recorded pattern=%r type=%r id=%s",
        pattern_name, update_type, update_id,
    )
    return update_id


async def get_feedback_stats() -> Dict[str, Any]:
    async with _get_engine().connect() as conn:
        result = await conn.execute(text(
            "SELECT outcome_label, COUNT(*) FROM feedback GROUP BY outcome_label"
        ))
        counts = {row[0]: row[1] for row in result.fetchall()}

        result = await conn.execute(text("SELECT COUNT(*) FROM feedback"))
        total = result.scalar() or 0

        result = await conn.execute(text(
            "SELECT outcome_label, AVG(system_risk_score) "
            "FROM feedback GROUP BY outcome_label"
        ))
        avg_scores = {row[0]: round(row[1], 2) for row in result.fetchall()}

        result = await conn.execute(text(
            "SELECT fraud_type_confirmed, COUNT(*) FROM feedback "
            "WHERE outcome_label = 'false_negative' GROUP BY fraud_type_confirmed"
        ))
        missed_types = {row[0]: row[1] for row in result.fetchall()}

    tp = counts.get("true_positive", 0)
    fp = counts.get("false_positive", 0)
    tn = counts.get("true_negative", 0)
    fn = counts.get("false_negative", 0)

    precision = tp / (tp + fp) if (tp + fp) > 0 else None
    recall = tp / (tp + fn) if (tp + fn) > 0 else None
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
    async with _get_engine().connect() as conn:
        result = await conn.execute(text(
            "SELECT * FROM feedback WHERE processed_at IS NULL "
            "ORDER BY created_at ASC LIMIT :limit"
        ), {"limit": limit})
        return [dict(row._mapping) for row in result.fetchall()]


async def mark_feedback_processed(feedback_ids: List[str]) -> None:
    """Set processed_at on the given records — idempotent (only updates NULL rows)."""
    if not feedback_ids:
        return
    now = datetime.now(timezone.utc).isoformat()
    async with _get_engine().begin() as conn:
        await conn.execute(
            text(
                "UPDATE feedback SET processed_at = :now "
                "WHERE id IN :ids AND processed_at IS NULL"
            ).bindparams(bindparam("ids", expanding=True)),
            {"now": now, "ids": feedback_ids},
        )


async def get_recent_feedback(limit: int = 50) -> List[Dict[str, Any]]:
    async with _get_engine().connect() as conn:
        result = await conn.execute(text(
            "SELECT * FROM feedback ORDER BY created_at DESC LIMIT :limit"
        ), {"limit": limit})
        return [dict(row._mapping) for row in result.fetchall()]


async def get_false_positives(limit: int = 20) -> List[Dict[str, Any]]:
    async with _get_engine().connect() as conn:
        result = await conn.execute(text(
            "SELECT * FROM feedback WHERE outcome_label = 'false_positive' "
            "ORDER BY created_at DESC LIMIT :limit"
        ), {"limit": limit})
        return [dict(row._mapping) for row in result.fetchall()]
