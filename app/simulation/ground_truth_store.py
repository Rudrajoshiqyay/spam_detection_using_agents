"""
Ground Truth Store — persistent store for generated transaction labels.

Every generated transaction gets: transaction_id, is_fraud, fraud_type,
campaign_id, ring_id, attack_difficulty, expected_label.

Completely separate from feedback_store.py (which stores analyst decisions).
This stores generator intent; feedback stores detection outcomes.
"""

import json
import time
import aiosqlite
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict


DB_PATH = Path(__file__).parent.parent.parent / "ground_truth.db"


@dataclass
class GroundTruthRecord:
    transaction_id: str
    is_fraud: bool
    fraud_type: Optional[str]           # "account_takeover", "card_testing", etc.
    campaign_id: Optional[str]          # which campaign generated this
    ring_id: Optional[str]              # which fraud ring (if any)
    attack_difficulty: float            # 0-100 (higher = harder to detect)
    expected_label: str                 # "BLOCKED", "ESCALATED", "APPROVED", etc.
    persona_type: Optional[str]
    amount: float
    attack_version: int = 1             # version within campaign generation (spec §10, §14)
    campaign_generation: int = 1        # which evolutionary generation (1=basic, 4=APT)
    created_at: float = 0.0

    def __post_init__(self):
        if not self.created_at:
            self.created_at = time.time()


async def init_ground_truth_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS ground_truth (
                transaction_id      TEXT PRIMARY KEY,
                is_fraud            INTEGER NOT NULL,
                fraud_type          TEXT,
                campaign_id         TEXT,
                ring_id             TEXT,
                attack_difficulty   REAL DEFAULT 0.0,
                expected_label      TEXT,
                persona_type        TEXT,
                amount              REAL,
                attack_version      INTEGER DEFAULT 1,
                campaign_generation INTEGER DEFAULT 1,
                created_at          REAL
            )
        """)
        # Migrate existing tables that lack the new columns
        for col, col_def in [
            ("attack_version", "INTEGER DEFAULT 1"),
            ("campaign_generation", "INTEGER DEFAULT 1"),
        ]:
            try:
                await db.execute(f"ALTER TABLE ground_truth ADD COLUMN {col} {col_def}")
            except Exception:
                pass  # column already exists
        await db.execute("CREATE INDEX IF NOT EXISTS idx_campaign ON ground_truth(campaign_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_ring ON ground_truth(ring_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_fraud ON ground_truth(is_fraud)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_gen ON ground_truth(campaign_generation)")
        await db.commit()


async def store_ground_truth(record: GroundTruthRecord):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO ground_truth
            (transaction_id, is_fraud, fraud_type, campaign_id, ring_id,
             attack_difficulty, expected_label, persona_type, amount,
             attack_version, campaign_generation, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            record.transaction_id, int(record.is_fraud), record.fraud_type,
            record.campaign_id, record.ring_id, record.attack_difficulty,
            record.expected_label, record.persona_type, record.amount,
            record.attack_version, record.campaign_generation, record.created_at,
        ))
        await db.commit()


async def bulk_store_ground_truth(records: List[GroundTruthRecord]):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executemany("""
            INSERT OR REPLACE INTO ground_truth
            (transaction_id, is_fraud, fraud_type, campaign_id, ring_id,
             attack_difficulty, expected_label, persona_type, amount,
             attack_version, campaign_generation, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, [
            (r.transaction_id, int(r.is_fraud), r.fraud_type, r.campaign_id,
             r.ring_id, r.attack_difficulty, r.expected_label, r.persona_type,
             r.amount, r.attack_version, r.campaign_generation, r.created_at)
            for r in records
        ])
        await db.commit()


async def get_ground_truth(transaction_id: str) -> Optional[GroundTruthRecord]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT * FROM ground_truth WHERE transaction_id=?", (transaction_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            return _row_to_record(row)


async def get_campaign_records(campaign_id: str) -> List[GroundTruthRecord]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT * FROM ground_truth WHERE campaign_id=?", (campaign_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [_row_to_record(r) for r in rows]


async def get_all_records(limit: int = 10000) -> List[GroundTruthRecord]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT * FROM ground_truth ORDER BY created_at DESC LIMIT ?", (limit,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [_row_to_record(r) for r in rows]


async def get_stats() -> Dict[str, Any]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*), SUM(is_fraud) FROM ground_truth") as c:
            total, fraud = await c.fetchone()
        async with db.execute(
            "SELECT fraud_type, COUNT(*) FROM ground_truth WHERE is_fraud=1 GROUP BY fraud_type"
        ) as c:
            by_type = {row[0]: row[1] for row in await c.fetchall()}
        async with db.execute(
            "SELECT campaign_id, COUNT(*) FROM ground_truth WHERE campaign_id IS NOT NULL GROUP BY campaign_id"
        ) as c:
            by_campaign = {row[0]: row[1] for row in await c.fetchall()}
    return {
        "total": total or 0,
        "fraud": int(fraud or 0),
        "legit": (total or 0) - int(fraud or 0),
        "fraud_rate": round(int(fraud or 0) / max(total or 1, 1), 3),
        "by_fraud_type": by_type,
        "by_campaign": by_campaign,
    }


async def clear_ground_truth():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM ground_truth")
        await db.commit()


def _row_to_record(row) -> GroundTruthRecord:
    return GroundTruthRecord(
        transaction_id=row[0],
        is_fraud=bool(row[1]),
        fraud_type=row[2],
        campaign_id=row[3],
        ring_id=row[4],
        attack_difficulty=row[5] or 0.0,
        expected_label=row[6] or "APPROVED",
        persona_type=row[7],
        amount=row[8] or 0.0,
        attack_version=int(row[9]) if len(row) > 9 and row[9] is not None else 1,
        campaign_generation=int(row[10]) if len(row) > 10 and row[10] is not None else 1,
        created_at=row[11] if len(row) > 11 and row[11] is not None else 0.0,
    )
