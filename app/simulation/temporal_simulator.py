"""
Temporal Simulator — generates realistic timestamps following persona behavioral cycles.

Patterns modeled:
  - Daily: persona active hours, meal times, commute patterns
  - Weekly: weekday vs weekend spending shifts
  - Monthly: salary credit spikes, rent/bill payments, end-of-month squeeze
  - Seasonal: festivals, travel seasons (not implemented — hackathon scope)
"""

import math
import random
from datetime import datetime, timedelta, timezone
from typing import List, Tuple
from dataclasses import dataclass

from app.simulation.persona_agent import PersonaProfile, PersonaType


@dataclass
class TimeSlot:
    timestamp: datetime
    slot_type: str        # "routine", "salary_credit", "weekend_shopping", "bill_payment", "night_activity"
    expected_amount_mult: float   # multiplier on persona avg amount for this slot


# ── Hour weights per activity type ──────────────────────────────────────────

def _hour_weight(hour: int, active_hours: List[int], night_active: bool) -> float:
    """Weight for generating a transaction at a given hour."""
    if hour in active_hours:
        # Peak at middle of active window
        return 3.0
    if night_active and hour in (0, 1, 2, 3):
        return 1.5
    if hour in (6, 7, 8):
        return 0.5   # morning commute
    if hour in (12, 13):
        return 1.2   # lunch
    if hour in (18, 19, 20):
        return 1.0   # evening
    return 0.1       # off-peak


def pick_hour(persona: PersonaProfile) -> int:
    weights = [_hour_weight(h, persona.active_hours, persona.night_activity) for h in range(24)]
    return random.choices(range(24), weights=weights)[0]


# ── Day-of-week weights ──────────────────────────────────────────────────────

_WEEKDAY_WEIGHTS = {
    PersonaType.student:           [0.8, 0.9, 0.9, 0.9, 1.0, 1.4, 1.1],
    PersonaType.salaried_employee: [1.0, 1.0, 1.0, 1.0, 1.0, 1.5, 1.3],
    PersonaType.business_owner:    [1.3, 1.3, 1.3, 1.3, 1.2, 0.6, 0.3],
    PersonaType.frequent_traveler: [1.0, 1.0, 1.0, 1.0, 1.2, 1.4, 1.2],
    PersonaType.senior_citizen:    [1.0, 1.1, 1.1, 1.0, 1.0, 0.9, 0.8],
    PersonaType.gig_worker:        [1.1, 1.0, 1.0, 1.1, 1.2, 1.3, 1.1],
    PersonaType.high_net_worth:    [0.9, 1.0, 1.0, 1.0, 1.1, 1.3, 1.2],
    PersonaType.crypto_trader:     [1.0, 1.0, 1.0, 1.0, 1.0, 1.1, 1.1],  # markets 24/7
}

# Index: 0=Mon … 6=Sun


def _day_weight(persona: PersonaProfile, weekday: int) -> float:
    weights = _WEEKDAY_WEIGHTS.get(persona.persona_type, [1.0] * 7)
    return weights[weekday]


# ── Monthly patterns ─────────────────────────────────────────────────────────

def _day_of_month_mult(day_of_month: int, persona: PersonaProfile) -> Tuple[float, str]:
    """Returns (amount_multiplier, slot_type) for a given day of month."""
    # Salary credit
    if persona.salary_day > 0 and day_of_month in (persona.salary_day, persona.salary_day + 1):
        return 2.5, "salary_credit"
    # Rent/EMI typically 1st-5th
    if day_of_month in (1, 2, 3, 4, 5):
        return 1.4, "bill_payment"
    # End-of-month squeeze: lower spending last 3 days
    if day_of_month >= 28:
        return 0.7, "low_balance"
    # Mid-month comfort
    if 10 <= day_of_month <= 20:
        return 1.2, "routine"
    return 1.0, "routine"


# ── Main timeline generator ──────────────────────────────────────────────────

def generate_timeline(
    persona: PersonaProfile,
    span_days: int = 30,
    start_date: datetime = None,
) -> List[TimeSlot]:
    """
    Generate a list of TimeSlots for a persona over span_days.
    The number of slots follows persona.txn_per_day with Poisson variation.
    """
    if start_date is None:
        start_date = datetime.now(timezone.utc) - timedelta(days=span_days)

    slots: List[TimeSlot] = []

    for day_offset in range(span_days):
        date = start_date + timedelta(days=day_offset)
        weekday = date.weekday()
        day_of_month = date.day

        # Number of transactions this day: Poisson(lambda=txn_per_day * day_weight)
        day_w = _day_weight(persona, weekday)
        lam = persona.txn_per_day * day_w
        n_txns = max(0, int(random.gauss(lam, lam ** 0.5)))

        dom_mult, slot_type = _day_of_month_mult(day_of_month, persona)

        for _ in range(n_txns):
            hour = pick_hour(persona)
            minute = random.randint(0, 59)
            second = random.randint(0, 59)
            ts = date.replace(hour=hour, minute=minute, second=second, microsecond=0)

            # Weekend multiplier
            weekend_mult = persona.weekend_multiplier if weekday >= 5 else 1.0

            # Night activity spike
            night_mult = 1.3 if (persona.night_activity and hour in (0, 1, 2, 23)) else 1.0

            amount_mult = dom_mult * weekend_mult * night_mult

            # Classify the slot
            if slot_type == "salary_credit":
                actual_type = "salary_credit"
            elif weekday >= 5 and hour in (14, 15, 16, 17, 18, 19):
                actual_type = "weekend_shopping"
            elif hour in (20, 21, 22) and persona.persona_type in (PersonaType.student, PersonaType.gig_worker):
                actual_type = "night_food_delivery"
            else:
                actual_type = slot_type

            slots.append(TimeSlot(
                timestamp=ts,
                slot_type=actual_type,
                expected_amount_mult=amount_mult,
            ))

    # Sort chronologically
    slots.sort(key=lambda s: s.timestamp)
    return slots


def get_salary_timestamps(
    persona: PersonaProfile,
    span_months: int = 3,
    base_date: datetime = None,
) -> List[datetime]:
    """Return exact salary credit timestamps for a persona."""
    if persona.salary_day == 0:
        return []
    if base_date is None:
        base_date = datetime.now(timezone.utc)
    result = []
    for m in range(span_months):
        month = (base_date.month - m - 1) % 12 + 1
        year = base_date.year - ((base_date.month - m - 1) // 12)
        try:
            ts = base_date.replace(year=year, month=month, day=persona.salary_day,
                                   hour=random.randint(8, 10), minute=random.randint(0, 59))
            result.append(ts)
        except ValueError:
            pass  # day doesn't exist in that month
    return result
