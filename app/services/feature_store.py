"""
Redis Feature Store — precomputes and caches all behavioral features.

Key structure:
  user:{uid}:features        → Hash  (avg_amount_7d, txn_count_1h, etc.)
  user:{uid}:devices         → Set   (known device IDs)
  user:{uid}:locations       → Set   ("city:country" strings)
  user:{uid}:merchants       → Hash  (merchant_id → count)
  user:{uid}:txns            → ZSet  (score=unix_ts, member=txn_id:amount)
  device:{did}:reputation    → Hash  (trust_score, fraud_count, account_count …)
  merchant:{mid}:reputation  → Hash  (reputation_score, chargeback_rate …)
  cohort:{name}:features     → Hash  (cohort averages)
  seq:{uid}:events           → List  (recent event strings, capped at 50)
"""

import json
import logging
import time
from typing import Optional
import redis.asyncio as aioredis

from app.config import settings

_logger = logging.getLogger(__name__)


class FeatureStore:
    def __init__(self):
        self._redis: Optional[aioredis.Redis] = None

    async def connect(self):
        # Try real Redis first; fall back to fakeredis for demo/dev
        try:
            client = aioredis.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=1)
            await client.ping()
            self._redis = client
            _logger.info("FeatureStore: connected to Redis at %s", settings.redis_url)
        except Exception:
            try:
                import fakeredis.aioredis as fakeredis
                self._redis = fakeredis.FakeRedis(decode_responses=True)
                _logger.info("FeatureStore: Redis unavailable — using fakeredis (in-memory, demo mode)")
            except ImportError:
                # Last resort: minimal in-memory dict store
                self._redis = _DictRedis()
                _logger.warning("FeatureStore: fakeredis not installed — using minimal dict store (no persistence)")

    async def close(self):
        if self._redis:
            try:
                await self._redis.aclose()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Feature retrieval (< 5 ms target via pipeline)
    # ------------------------------------------------------------------
    async def get_user_features(self, user_id: str) -> dict:
        key = f"user:{user_id}:features"
        pipe = self._redis.pipeline()
        pipe.hgetall(key)
        pipe.smembers(f"user:{user_id}:devices")
        pipe.smembers(f"user:{user_id}:locations")
        pipe.hgetall(f"user:{user_id}:merchants")
        results = await pipe.execute()

        features = {k: float(v) if _is_float(v) else v for k, v in results[0].items()}
        features["known_devices"] = list(results[1])
        features["known_locations"] = list(results[2])
        features["merchant_frequencies"] = {k: int(v) for k, v in results[3].items()}
        return features

    async def get_device_reputation(self, device_id: str) -> dict:
        data = await self._redis.hgetall(f"device:{device_id}:reputation")
        if not data:
            return {"trust_score": 0.5, "fraud_count": 0, "account_count": 1, "age_days": 0}
        return {k: float(v) if _is_float(v) else v for k, v in data.items()}

    async def get_merchant_reputation(self, merchant_id: str) -> dict:
        data = await self._redis.hgetall(f"merchant:{merchant_id}:reputation")
        if not data:
            return {"reputation_score": 0.5, "chargeback_rate": 0.02, "refund_rate": 0.05,
                    "fraud_associations": 0, "transaction_volume": 0, "customer_diversity": 0}
        return {k: float(v) if _is_float(v) else v for k, v in data.items()}

    async def get_cohort_features(self, cohort: str) -> dict:
        data = await self._redis.hgetall(f"cohort:{cohort}:features")
        return {k: float(v) if _is_float(v) else v for k, v in data.items()}

    async def get_recent_events(self, user_id: str, limit: int = 20) -> list:
        raw = await self._redis.lrange(f"seq:{user_id}:events", 0, limit - 1)
        events = []
        for e in raw:
            try:
                events.append(json.loads(e))
            except (json.JSONDecodeError, TypeError) as exc:
                _logger.warning(
                    "FeatureStore.get_recent_events: skipping corrupted entry for "
                    "user=%r — %s: %s", user_id, type(exc).__name__, exc
                )
        return events

    # ------------------------------------------------------------------
    # Feature updates (called by Feature Builder Service)
    # ------------------------------------------------------------------
    async def update_user_features(self, user_id: str, features: dict):
        key = f"user:{user_id}:features"
        pipe = self._redis.pipeline()
        flat = {k: str(v) for k, v in features.items()
                if not isinstance(v, (list, set, dict))}
        if flat:
            pipe.hset(key, mapping=flat)
            pipe.expire(key, 86400)       # 24-hour TTL
        await pipe.execute()

    async def register_device(self, user_id: str, device_id: str):
        await self._redis.sadd(f"user:{user_id}:devices", device_id)

    async def register_location(self, user_id: str, location: str):
        await self._redis.sadd(f"user:{user_id}:locations", location)

    async def increment_merchant_count(self, user_id: str, merchant_id: str):
        await self._redis.hincrby(f"user:{user_id}:merchants", merchant_id, 1)

    async def record_transaction(self, user_id: str, txn_id: str, amount: float, ts: float):
        key = f"user:{user_id}:txns"
        pipe = self._redis.pipeline()
        pipe.zadd(key, {f"{txn_id}:{amount}": ts})
        pipe.zremrangebyscore(key, 0, ts - 86400 * 30)   # keep 30 days
        pipe.expire(key, 86400 * 31)
        await pipe.execute()

    async def push_event(self, user_id: str, event: dict):
        key = f"seq:{user_id}:events"
        pipe = self._redis.pipeline()
        pipe.lpush(key, json.dumps(event))
        pipe.ltrim(key, 0, 49)   # keep last 50 events
        pipe.expire(key, 86400 * 7)
        await pipe.execute()

    async def set_device_reputation(self, device_id: str, data: dict):
        key = f"device:{device_id}:reputation"
        await self._redis.hset(key, mapping={k: str(v) for k, v in data.items()})
        await self._redis.expire(key, 86400 * 7)

    async def set_merchant_reputation(self, merchant_id: str, data: dict):
        key = f"merchant:{merchant_id}:reputation"
        await self._redis.hset(key, mapping={k: str(v) for k, v in data.items()})
        await self._redis.expire(key, 86400)

    async def seed_cohort_features(self, cohort: str, features: dict):
        key = f"cohort:{cohort}:features"
        await self._redis.hset(key, mapping={k: str(v) for k, v in features.items()
                                              if isinstance(v, (int, float, str))})

    # ------------------------------------------------------------------
    # Velocity helpers
    # ------------------------------------------------------------------
    async def get_txn_count_window(self, user_id: str, window_seconds: int) -> int:
        now = time.time()
        cutoff = now - window_seconds
        return await self._redis.zcount(f"user:{user_id}:txns", cutoff, "+inf")


def _is_float(v: str) -> bool:
    try:
        float(v)
        return True
    except (ValueError, TypeError):
        return False


class _DictRedis:
    """Minimal in-memory Redis substitute using plain dicts. No persistence."""
    def __init__(self):
        self._hashes: dict = {}
        self._sets: dict = {}
        self._zsets: dict = {}
        self._lists: dict = {}

    async def ping(self): return True
    async def hgetall(self, key): return dict(self._hashes.get(key, {}))
    async def hset(self, key, mapping=None, **kw):
        self._hashes.setdefault(key, {}).update(mapping or kw)
    async def hincrby(self, key, field, amount):
        h = self._hashes.setdefault(key, {})
        h[field] = str(int(h.get(field, 0)) + amount)
    async def expire(self, key, ttl): pass
    async def sadd(self, key, *vals):
        self._sets.setdefault(key, set()).update(str(v) for v in vals)
    async def smembers(self, key): return self._sets.get(key, set())
    async def zadd(self, key, mapping):
        self._zsets.setdefault(key, {}). update(mapping)
    async def zremrangebyscore(self, key, mn, mx):
        z = self._zsets.get(key, {})
        self._zsets[key] = {k: v for k, v in z.items() if not (mn <= v <= mx)}
    async def zcount(self, key, mn, mx):
        z = self._zsets.get(key, {})
        return sum(1 for v in z.values() if mn <= v)
    async def lpush(self, key, *vals):
        lst = self._lists.setdefault(key, [])
        for v in vals: lst.insert(0, v)
    async def ltrim(self, key, start, end):
        lst = self._lists.get(key, [])
        self._lists[key] = lst[start:end + 1]
    async def lrange(self, key, start, end):
        lst = self._lists.get(key, [])
        return lst[start:end + 1] if end >= 0 else lst[start:]

    def pipeline(self):
        return _DictPipeline(self)

    async def aclose(self): pass


class _DictPipeline:
    def __init__(self, store):
        self._store = store
        self._cmds = []

    def hgetall(self, key): self._cmds.append(("hgetall", key)); return self
    def smembers(self, key): self._cmds.append(("smembers", key)); return self
    def hset(self, key, mapping=None, **kw): self._cmds.append(("hset", key, mapping or kw)); return self
    def expire(self, key, ttl): self._cmds.append(("expire", key)); return self
    def zadd(self, key, mapping): self._cmds.append(("zadd", key, mapping)); return self
    def zremrangebyscore(self, key, mn, mx): self._cmds.append(("zremrangebyscore", key, mn, mx)); return self

    async def execute(self):
        results = []
        for cmd in self._cmds:
            op = cmd[0]
            if op == "hgetall": results.append(await self._store.hgetall(cmd[1]))
            elif op == "smembers": results.append(await self._store.smembers(cmd[1]))
            elif op == "hset": await self._store.hset(cmd[1], mapping=cmd[2]); results.append(True)
            elif op == "expire": results.append(True)
            elif op == "zadd": await self._store.zadd(cmd[1], cmd[2]); results.append(True)
            elif op == "zremrangebyscore": await self._store.zremrangebyscore(cmd[1], cmd[2], cmd[3]); results.append(0)
            else: results.append(None)
        self._cmds.clear()
        return results


feature_store = FeatureStore()
