"""
Life Events Engine — users evolve over time through life events that
modify their spending behavior temporarily or permanently.

Supported events (spec §3):
  Salary Credit, Bonus, Job Change, Job Loss, Marriage,
  Vacation, Loan Approval, EMI Start, New Credit Card, Festival Spending

Events produce a BehaviorModifier that scales PersonaProfile fields
for the duration of the event.
"""

import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import List, Dict, Any, Optional

from app.simulation.persona_agent import PersonaProfile, PersonaType


# ── Event Types ───────────────────────────────────────────────────────────────

class LifeEventType(str, Enum):
    salary_credit      = "salary_credit"
    bonus              = "bonus"
    job_change         = "job_change"
    job_loss           = "job_loss"
    marriage           = "marriage"
    vacation           = "vacation"
    loan_approval      = "loan_approval"
    emi_start          = "emi_start"
    new_credit_card    = "new_credit_card"
    festival_spending  = "festival_spending"


@dataclass
class LifeEvent:
    event_type: LifeEventType
    start_date: datetime
    end_date: datetime          # same day for point events; weeks/months for sustained

    # Behavioral multipliers during the event window
    amount_multiplier: float    # scale avg_txn_amount
    velocity_multiplier: float  # scale txn_per_day
    new_category: Optional[str] = None     # temporary merchant category addition
    new_device_likely: bool = False        # chance of new device appearing
    international_boost: bool = False      # temporarily more intl travel
    description: str = ""


@dataclass
class EventTimeline:
    """A user's life event history over a simulation window."""
    user_id: str
    persona_type: str
    events: List[LifeEvent] = field(default_factory=list)

    def get_active_modifier(self, ts: datetime) -> Dict[str, Any]:
        """Return stacked multipliers for a given timestamp."""
        amount_mult = 1.0
        velocity_mult = 1.0
        extra_categories: List[str] = []
        new_device = False
        intl_boost = False

        for ev in self.events:
            if ev.start_date <= ts <= ev.end_date:
                amount_mult *= ev.amount_multiplier
                velocity_mult *= ev.velocity_multiplier
                if ev.new_category:
                    extra_categories.append(ev.new_category)
                if ev.new_device_likely:
                    new_device = True
                if ev.international_boost:
                    intl_boost = True

        return {
            "amount_multiplier": round(amount_mult, 3),
            "velocity_multiplier": round(velocity_mult, 3),
            "extra_categories": extra_categories,
            "new_device_likely": new_device,
            "international_boost": intl_boost,
        }


# ── Event generators per type ─────────────────────────────────────────────────

def _make_salary_credit(base_date: datetime, persona: PersonaProfile) -> LifeEvent:
    day = persona.salary_day or 1
    try:
        ts = base_date.replace(day=day, hour=8, minute=0, second=0)
    except ValueError:
        ts = base_date.replace(day=28, hour=8, minute=0, second=0)
    return LifeEvent(
        event_type=LifeEventType.salary_credit,
        start_date=ts,
        end_date=ts + timedelta(hours=4),
        amount_multiplier=3.0,    # big credit + immediate spending
        velocity_multiplier=2.5,
        new_category="utilities",
        description="Monthly salary credited",
    )


def _make_bonus(base_date: datetime) -> LifeEvent:
    ts = base_date + timedelta(days=random.randint(0, 30))
    multiplier = random.uniform(2.0, 5.0)
    return LifeEvent(
        event_type=LifeEventType.bonus,
        start_date=ts,
        end_date=ts + timedelta(days=14),
        amount_multiplier=multiplier,
        velocity_multiplier=1.8,
        new_category=random.choice(["electronics", "luxury", "clothing"]),
        description=f"Performance bonus — {multiplier:.1f}x spending for 2 weeks",
    )


def _make_job_change(base_date: datetime) -> LifeEvent:
    ts = base_date + timedelta(days=random.randint(0, 60))
    new_income_mult = random.uniform(1.2, 2.5)
    return LifeEvent(
        event_type=LifeEventType.job_change,
        start_date=ts,
        end_date=ts + timedelta(days=90),  # 3 months adjustment
        amount_multiplier=new_income_mult,
        velocity_multiplier=1.3,
        new_device_likely=True,      # new employer device or personal upgrade
        new_category="restaurants",  # celebration dinners
        description=f"Job change — income increased {new_income_mult:.1f}x",
    )


def _make_job_loss(base_date: datetime) -> LifeEvent:
    ts = base_date + timedelta(days=random.randint(0, 30))
    return LifeEvent(
        event_type=LifeEventType.job_loss,
        start_date=ts,
        end_date=ts + timedelta(days=120),  # 4 months austerity
        amount_multiplier=0.4,
        velocity_multiplier=0.6,
        new_category="grocery",    # cost-conscious shift
        description="Job loss — reduced spending for 4 months",
    )


def _make_marriage(base_date: datetime) -> LifeEvent:
    ts = base_date + timedelta(days=random.randint(0, 90))
    return LifeEvent(
        event_type=LifeEventType.marriage,
        start_date=ts - timedelta(days=30),
        end_date=ts + timedelta(days=30),
        amount_multiplier=4.0,
        velocity_multiplier=3.0,
        new_category="jewelry",
        international_boost=True,  # honeymoon
        description="Marriage event — wedding + honeymoon spending spike",
    )


def _make_vacation(base_date: datetime, persona: PersonaProfile) -> LifeEvent:
    ts = base_date + timedelta(days=random.randint(7, 60))
    duration = random.randint(5, 21)
    is_intl = persona.travel_frequency in ("frequent", "very_frequent")
    return LifeEvent(
        event_type=LifeEventType.vacation,
        start_date=ts,
        end_date=ts + timedelta(days=duration),
        amount_multiplier=2.5,
        velocity_multiplier=2.0,
        new_category="hotels",
        international_boost=is_intl,
        description=f"{'International' if is_intl else 'Domestic'} vacation — {duration} days",
    )


def _make_loan_approval(base_date: datetime) -> LifeEvent:
    ts = base_date + timedelta(days=random.randint(0, 30))
    return LifeEvent(
        event_type=LifeEventType.loan_approval,
        start_date=ts,
        end_date=ts + timedelta(days=7),
        amount_multiplier=5.0,
        velocity_multiplier=2.5,
        new_category="real_estate",
        description="Loan disbursed — large purchase activity",
    )


def _make_emi_start(base_date: datetime) -> LifeEvent:
    ts = base_date + timedelta(days=random.randint(0, 15))
    return LifeEvent(
        event_type=LifeEventType.emi_start,
        start_date=ts,
        end_date=ts + timedelta(days=365),  # 12 months EMI
        amount_multiplier=0.75,             # less discretionary spending
        velocity_multiplier=0.85,
        new_category="insurance",
        description="EMI started — reduced discretionary spend for 12 months",
    )


def _make_new_credit_card(base_date: datetime) -> LifeEvent:
    ts = base_date + timedelta(days=random.randint(0, 7))
    return LifeEvent(
        event_type=LifeEventType.new_credit_card,
        start_date=ts,
        end_date=ts + timedelta(days=30),
        amount_multiplier=2.0,
        velocity_multiplier=1.8,
        new_category="ecommerce",   # online spending surge with new card
        new_device_likely=False,
        description="New credit card — spending surge for first month",
    )


def _make_festival(base_date: datetime, festival_name: str = "Diwali") -> LifeEvent:
    # Festivals are usually known dates — approximate
    festival_offsets = {
        "Diwali":     random.randint(280, 310),  # ~Oct-Nov
        "Christmas":  350,
        "Holi":       random.randint(70, 90),
        "Eid":        random.randint(150, 180),
    }
    offset = festival_offsets.get(festival_name, random.randint(1, 365))
    from datetime import date
    try:
        year_start = base_date.replace(month=1, day=1)
    except Exception:
        year_start = base_date
    ts = year_start + timedelta(days=offset)
    return LifeEvent(
        event_type=LifeEventType.festival_spending,
        start_date=ts - timedelta(days=7),
        end_date=ts + timedelta(days=3),
        amount_multiplier=3.5,
        velocity_multiplier=4.0,
        new_category=random.choice(["clothing", "jewelry", "electronics"]),
        description=f"{festival_name} festival spending spike",
    )


# ── Event probability table ───────────────────────────────────────────────────

# P(event occurs in simulation window) per persona
_EVENT_PROBABILITIES: Dict[PersonaType, Dict[LifeEventType, float]] = {
    PersonaType.student: {
        LifeEventType.salary_credit:     0.0,
        LifeEventType.bonus:             0.0,
        LifeEventType.job_change:        0.05,
        LifeEventType.job_loss:          0.02,
        LifeEventType.marriage:          0.02,
        LifeEventType.vacation:          0.30,
        LifeEventType.loan_approval:     0.05,
        LifeEventType.emi_start:         0.05,
        LifeEventType.new_credit_card:   0.15,
        LifeEventType.festival_spending: 0.80,
    },
    PersonaType.salaried_employee: {
        LifeEventType.salary_credit:     1.00,
        LifeEventType.bonus:             0.50,
        LifeEventType.job_change:        0.15,
        LifeEventType.job_loss:          0.05,
        LifeEventType.marriage:          0.10,
        LifeEventType.vacation:          0.60,
        LifeEventType.loan_approval:     0.20,
        LifeEventType.emi_start:         0.35,
        LifeEventType.new_credit_card:   0.30,
        LifeEventType.festival_spending: 0.90,
    },
    PersonaType.business_owner: {
        LifeEventType.salary_credit:     0.0,
        LifeEventType.bonus:             0.20,
        LifeEventType.job_change:        0.0,
        LifeEventType.job_loss:          0.08,
        LifeEventType.marriage:          0.05,
        LifeEventType.vacation:          0.40,
        LifeEventType.loan_approval:     0.40,
        LifeEventType.emi_start:         0.50,
        LifeEventType.new_credit_card:   0.40,
        LifeEventType.festival_spending: 0.80,
    },
    PersonaType.frequent_traveler: {
        LifeEventType.salary_credit:     0.80,
        LifeEventType.bonus:             0.30,
        LifeEventType.job_change:        0.20,
        LifeEventType.job_loss:          0.05,
        LifeEventType.marriage:          0.05,
        LifeEventType.vacation:          1.00,  # always traveling
        LifeEventType.loan_approval:     0.10,
        LifeEventType.emi_start:         0.15,
        LifeEventType.new_credit_card:   0.50,
        LifeEventType.festival_spending: 0.60,
    },
    PersonaType.senior_citizen: {
        LifeEventType.salary_credit:     0.0,
        LifeEventType.bonus:             0.0,
        LifeEventType.job_change:        0.0,
        LifeEventType.job_loss:          0.0,
        LifeEventType.marriage:          0.02,
        LifeEventType.vacation:          0.20,
        LifeEventType.loan_approval:     0.05,
        LifeEventType.emi_start:         0.10,
        LifeEventType.new_credit_card:   0.05,
        LifeEventType.festival_spending: 0.70,
    },
    PersonaType.gig_worker: {
        LifeEventType.salary_credit:     0.0,
        LifeEventType.bonus:             0.10,
        LifeEventType.job_change:        0.30,
        LifeEventType.job_loss:          0.15,
        LifeEventType.marriage:          0.08,
        LifeEventType.vacation:          0.20,
        LifeEventType.loan_approval:     0.10,
        LifeEventType.emi_start:         0.20,
        LifeEventType.new_credit_card:   0.20,
        LifeEventType.festival_spending: 0.75,
    },
    PersonaType.high_net_worth: {
        LifeEventType.salary_credit:     0.0,
        LifeEventType.bonus:             0.70,
        LifeEventType.job_change:        0.05,
        LifeEventType.job_loss:          0.01,
        LifeEventType.marriage:          0.05,
        LifeEventType.vacation:          0.90,
        LifeEventType.loan_approval:     0.30,
        LifeEventType.emi_start:         0.20,
        LifeEventType.new_credit_card:   0.60,
        LifeEventType.festival_spending: 0.95,
    },
    PersonaType.crypto_trader: {
        LifeEventType.salary_credit:     0.30,
        LifeEventType.bonus:             0.30,
        LifeEventType.job_change:        0.25,
        LifeEventType.job_loss:          0.20,
        LifeEventType.marriage:          0.05,
        LifeEventType.vacation:          0.40,
        LifeEventType.loan_approval:     0.10,
        LifeEventType.emi_start:         0.15,
        LifeEventType.new_credit_card:   0.40,
        LifeEventType.festival_spending: 0.60,
    },
}


# ── Timeline builder ──────────────────────────────────────────────────────────

def build_event_timeline(
    user: Dict,
    sim_start: datetime = None,
    span_days: int = 90,
) -> EventTimeline:
    """
    Build a life event timeline for a user over span_days from sim_start.
    Events are sampled based on persona-type probabilities.
    """
    if sim_start is None:
        sim_start = datetime.now(timezone.utc)

    user_id = user["metadata"]["user_id"]
    persona_type_str = user["metadata"]["persona_type"]
    persona = user["persona"]

    try:
        pt = PersonaType(persona_type_str)
    except ValueError:
        pt = PersonaType.salaried_employee

    prob_table = _EVENT_PROBABILITIES.get(pt, {})
    timeline = EventTimeline(user_id=user_id, persona_type=persona_type_str)

    for event_type, probability in prob_table.items():
        if random.random() > probability:
            continue

        if event_type == LifeEventType.salary_credit:
            # Monthly — generate for each month in span
            for m in range(span_days // 30 + 1):
                base = sim_start + timedelta(days=m * 30)
                timeline.events.append(_make_salary_credit(base, persona))

        elif event_type == LifeEventType.bonus:
            timeline.events.append(_make_bonus(sim_start))

        elif event_type == LifeEventType.job_change:
            timeline.events.append(_make_job_change(sim_start))

        elif event_type == LifeEventType.job_loss:
            timeline.events.append(_make_job_loss(sim_start))

        elif event_type == LifeEventType.marriage:
            timeline.events.append(_make_marriage(sim_start))

        elif event_type == LifeEventType.vacation:
            timeline.events.append(_make_vacation(sim_start, persona))

        elif event_type == LifeEventType.loan_approval:
            timeline.events.append(_make_loan_approval(sim_start))

        elif event_type == LifeEventType.emi_start:
            timeline.events.append(_make_emi_start(sim_start))

        elif event_type == LifeEventType.new_credit_card:
            timeline.events.append(_make_new_credit_card(sim_start))

        elif event_type == LifeEventType.festival_spending:
            festival = random.choice(["Diwali", "Christmas", "Holi", "Eid"])
            timeline.events.append(_make_festival(sim_start, festival))

    return timeline


def apply_event_modifier(
    base_persona: PersonaProfile,
    modifier: Dict[str, Any],
) -> PersonaProfile:
    """
    Return a modified copy of the persona with event multipliers applied.
    Does NOT mutate the original.
    """
    from copy import copy
    p = copy(base_persona)
    p.avg_txn_amount = round(p.avg_txn_amount * modifier["amount_multiplier"])
    p.txn_per_day = round(p.txn_per_day * modifier["velocity_multiplier"], 2)
    for cat in modifier.get("extra_categories", []):
        if cat not in p.preferred_merchants:
            p.preferred_merchants = p.preferred_merchants + [cat]
    if modifier.get("international_boost"):
        p.travel_frequency = "frequent"
    return p
