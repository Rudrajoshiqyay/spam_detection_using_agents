"""
Economic Environment Engine — macro-level events that influence the entire population.

Supported events (spec §6):
  Diwali, Christmas, Black Friday, IPL Season,
  Fuel Price Increase, Stock Market Rally, Market Crash

Effects:
  - Transaction volume multiplier (whole population)
  - Per-category spend multiplier
  - Fraud activity multiplier (fraudsters hide in volume spikes)
  - Country-specific events

Usage:
    env = EconomicEnvironment(year=2025)
    multiplier = env.get_multiplier(dt, category="ecommerce")
    fraud_mult  = env.get_fraud_multiplier(dt)
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional, Any


@dataclass
class MacroEvent:
    name: str
    start_date: date
    end_date: date
    country: str                          # "ALL", "India", "USA", etc.

    # Volume effects (multiplicative on top of baseline)
    global_volume_mult: float             # total txn count multiplier
    fraud_volume_mult: float              # extra fraud hidden in spike
    category_multipliers: Dict[str, float] = field(default_factory=dict)
    description: str = ""

    def is_active(self, dt: datetime) -> bool:
        d = dt.date() if hasattr(dt, "date") else dt
        return self.start_date <= d <= self.end_date

    def affects_country(self, country: str) -> bool:
        return self.country == "ALL" or self.country == country


def _d(month: int, day: int, year: int = 2025) -> date:
    return date(year, month, day)


# ── Event Calendar ────────────────────────────────────────────────────────────

def build_event_calendar(year: int = 2025) -> List[MacroEvent]:
    return [

        MacroEvent(
            name="Diwali",
            start_date=_d(10, 20, year),
            end_date=_d(11, 5, year),
            country="India",
            global_volume_mult=2.5,
            fraud_volume_mult=1.8,
            category_multipliers={
                "ecommerce":   3.5,
                "electronics": 4.0,
                "clothing":    3.0,
                "jewelry":     3.5,
                "restaurants": 2.0,
                "gambling":    1.5,   # bonus season → more gambling
            },
            description="Diwali festival — major shopping spike, fraud hides in volume",
        ),

        MacroEvent(
            name="Christmas",
            start_date=_d(12, 20, year),
            end_date=_d(12, 31, year),
            country="ALL",
            global_volume_mult=2.0,
            fraud_volume_mult=1.6,
            category_multipliers={
                "ecommerce":     3.0,
                "electronics":   2.5,
                "clothing":      2.0,
                "airlines":      2.5,
                "hotels":        2.0,
                "restaurants":   2.0,
            },
            description="Christmas shopping season",
        ),

        MacroEvent(
            name="Black Friday",
            start_date=_d(11, 28, year),
            end_date=_d(12, 2, year),
            country="ALL",
            global_volume_mult=3.0,
            fraud_volume_mult=2.2,
            category_multipliers={
                "ecommerce":   5.0,
                "electronics": 6.0,
                "clothing":    4.0,
                "luxury":      3.0,
            },
            description="Black Friday / Cyber Monday — highest fraud-in-volume risk",
        ),

        MacroEvent(
            name="IPL Season",
            start_date=_d(3, 20, year),
            end_date=_d(5, 31, year),
            country="India",
            global_volume_mult=1.4,
            fraud_volume_mult=1.5,
            category_multipliers={
                "gambling":      4.0,
                "gaming":        3.0,
                "entertainment": 2.0,
                "food_delivery": 1.8,
                "streaming":     2.0,
            },
            description="IPL cricket season — sports gambling spike",
        ),

        MacroEvent(
            name="Holi",
            start_date=_d(3, 13, year),
            end_date=_d(3, 16, year),
            country="India",
            global_volume_mult=1.6,
            fraud_volume_mult=1.3,
            category_multipliers={
                "clothing":      2.5,
                "restaurants":   2.0,
                "entertainment": 1.8,
            },
            description="Holi festival",
        ),

        MacroEvent(
            name="Fuel Price Increase",
            start_date=_d(4, 1, year),
            end_date=_d(4, 30, year),
            country="India",
            global_volume_mult=1.1,
            fraud_volume_mult=1.1,
            category_multipliers={
                "fuel":          1.8,
                "transport":     1.5,
                "grocery":       1.2,  # cost of goods rises
            },
            description="Fuel price hike — transport category spike",
        ),

        MacroEvent(
            name="Stock Market Rally",
            start_date=_d(1, 15, year),
            end_date=_d(2, 15, year),
            country="ALL",
            global_volume_mult=1.3,
            fraud_volume_mult=1.4,
            category_multipliers={
                "investments":     4.0,
                "cryptocurrency":  3.0,
                "luxury":          2.0,
                "wire_transfer":   1.8,
            },
            description="Bull market — investment and luxury spending surge",
        ),

        MacroEvent(
            name="Market Crash",
            start_date=_d(8, 5, year),
            end_date=_d(8, 20, year),
            country="ALL",
            global_volume_mult=0.7,
            fraud_volume_mult=1.6,   # desperate fraud attempts increase
            category_multipliers={
                "investments":     0.3,
                "cryptocurrency":  2.5,  # panic crypto selling
                "luxury":          0.4,
                "grocery":         1.3,  # defensive spending
                "wire_transfer":   1.5,  # capital flight
            },
            description="Market crash — reduced spending, crypto panic, fraud spike",
        ),

        MacroEvent(
            name="Budget Day",
            start_date=_d(2, 1, year),
            end_date=_d(2, 2, year),
            country="India",
            global_volume_mult=0.8,
            fraud_volume_mult=1.0,
            category_multipliers={
                "investments": 2.0,
                "real_estate": 1.5,
            },
            description="Union Budget Day — investment activity",
        ),

        MacroEvent(
            name="Eid",
            start_date=_d(3, 30, year),
            end_date=_d(4, 3, year),
            country="India",
            global_volume_mult=1.7,
            fraud_volume_mult=1.3,
            category_multipliers={
                "clothing":    3.0,
                "jewelry":     2.5,
                "restaurants": 2.5,
            },
            description="Eid celebrations",
        ),

        MacroEvent(
            name="New Year",
            start_date=_d(12, 31, year - 1) if year > 2020 else _d(12, 31, year),
            end_date=_d(1, 3, year),
            country="ALL",
            global_volume_mult=2.0,
            fraud_volume_mult=1.5,
            category_multipliers={
                "restaurants":   3.0,
                "hotels":        2.5,
                "airlines":      2.0,
                "entertainment": 3.0,
            },
            description="New Year celebrations",
        ),
    ]


# ── EconomicEnvironment class ────────────────────────────────────────────────

class EconomicEnvironment:
    def __init__(self, year: int = 2025):
        self.year = year
        self.events: List[MacroEvent] = build_event_calendar(year)

    def get_active_events(self, dt: datetime, country: str = "India") -> List[MacroEvent]:
        return [e for e in self.events if e.is_active(dt) and e.affects_country(country)]

    def get_volume_multiplier(self, dt: datetime, country: str = "India") -> float:
        """Combined transaction volume multiplier for this date."""
        mult = 1.0
        for e in self.get_active_events(dt, country):
            mult *= e.global_volume_mult
        return round(min(mult, 8.0), 3)

    def get_fraud_multiplier(self, dt: datetime, country: str = "India") -> float:
        """Fraud activity multiplier — fraudsters exploit volume spikes."""
        mult = 1.0
        for e in self.get_active_events(dt, country):
            mult *= e.fraud_volume_mult
        return round(min(mult, 5.0), 3)

    def get_category_multiplier(self, dt: datetime, category: str, country: str = "India") -> float:
        """Spending multiplier for a specific merchant category."""
        mult = 1.0
        for e in self.get_active_events(dt, country):
            cat_mult = e.category_multipliers.get(category, 1.0)
            mult *= cat_mult
        return round(min(mult, 10.0), 3)

    def get_day_profile(self, dt: datetime, country: str = "India") -> Dict[str, Any]:
        """Full multiplier profile for a given day."""
        active = self.get_active_events(dt, country)
        return {
            "date": dt.strftime("%Y-%m-%d"),
            "active_events": [e.name for e in active],
            "volume_multiplier": self.get_volume_multiplier(dt, country),
            "fraud_multiplier": self.get_fraud_multiplier(dt, country),
            "top_categories": _top_category_multipliers(active),
            "is_high_risk_day": self.get_fraud_multiplier(dt, country) > 1.3,
        }

    def annotate_transaction(self, txn_dict: Dict, country: str = "India") -> Dict:
        """Add economic context fields to a transaction dict."""
        from datetime import datetime as _dt
        ts_raw = txn_dict.get("timestamp")
        try:
            if isinstance(ts_raw, str):
                ts = _dt.fromisoformat(ts_raw.replace("Z", "+00:00"))
            elif isinstance(ts_raw, _dt):
                ts = ts_raw
            else:
                ts = _dt.now(timezone.utc)
        except Exception:
            ts = _dt.now(timezone.utc)

        category = txn_dict.get("merchant_category", "ecommerce")
        active = self.get_active_events(ts, country)
        txn_dict["economic_events"] = [e.name for e in active]
        txn_dict["volume_context_mult"] = self.get_volume_multiplier(ts, country)
        txn_dict["category_context_mult"] = self.get_category_multiplier(ts, category, country)
        return txn_dict

    def list_events(self) -> List[Dict]:
        return [
            {
                "name": e.name,
                "start": e.start_date.isoformat(),
                "end": e.end_date.isoformat(),
                "country": e.country,
                "volume_mult": e.global_volume_mult,
                "fraud_mult": e.fraud_volume_mult,
                "description": e.description,
            }
            for e in self.events
        ]


def _top_category_multipliers(events: List[MacroEvent], top_n: int = 5) -> Dict[str, float]:
    merged: Dict[str, float] = {}
    for e in events:
        for cat, mult in e.category_multipliers.items():
            merged[cat] = merged.get(cat, 1.0) * mult
    sorted_cats = sorted(merged.items(), key=lambda x: -x[1])
    return dict(sorted_cats[:top_n])


# ── Singleton ─────────────────────────────────────────────────────────────────

_default_env: Optional[EconomicEnvironment] = None


def get_economic_environment(year: int = 2025) -> EconomicEnvironment:
    global _default_env
    if _default_env is None or _default_env.year != year:
        _default_env = EconomicEnvironment(year)
    return _default_env
