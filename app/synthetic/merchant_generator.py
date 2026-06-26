"""
Merchant Generator — produces realistic synthetic merchant profiles.
"""

import random
import uuid
from typing import List, Dict, Any


_MERCHANT_TEMPLATES = {
    "grocery": {
        "avg_ticket": 650, "std_ticket": 300,
        "fraud_rate": 0.005, "chargeback_rate": 0.003, "refund_rate": 0.04,
        "risk_score": 0.05, "transaction_frequency": "high",
        "cities": ["Mumbai", "Delhi", "Bangalore", "Pune", "Chennai"],
    },
    "fuel": {
        "avg_ticket": 1200, "std_ticket": 400,
        "fraud_rate": 0.01, "chargeback_rate": 0.005, "refund_rate": 0.01,
        "risk_score": 0.10, "transaction_frequency": "high",
        "cities": ["Mumbai", "Delhi", "Hyderabad"],
    },
    "ecommerce": {
        "avg_ticket": 2500, "std_ticket": 3000,
        "fraud_rate": 0.02, "chargeback_rate": 0.015, "refund_rate": 0.08,
        "risk_score": 0.20, "transaction_frequency": "very_high",
        "cities": ["Online"],
    },
    "luxury_retail": {
        "avg_ticket": 45000, "std_ticket": 30000,
        "fraud_rate": 0.008, "chargeback_rate": 0.005, "refund_rate": 0.06,
        "risk_score": 0.15, "transaction_frequency": "low",
        "cities": ["Mumbai", "Delhi", "London", "Dubai"],
    },
    "gaming": {
        "avg_ticket": 800, "std_ticket": 1200,
        "fraud_rate": 0.045, "chargeback_rate": 0.04, "refund_rate": 0.02,
        "risk_score": 0.55, "transaction_frequency": "medium",
        "cities": ["Online"],
    },
    "cryptocurrency": {
        "avg_ticket": 15000, "std_ticket": 25000,
        "fraud_rate": 0.06, "chargeback_rate": 0.001, "refund_rate": 0.005,
        "risk_score": 0.75, "transaction_frequency": "medium",
        "cities": ["Online"],
    },
    "restaurant": {
        "avg_ticket": 850, "std_ticket": 600,
        "fraud_rate": 0.006, "chargeback_rate": 0.004, "refund_rate": 0.03,
        "risk_score": 0.08, "transaction_frequency": "high",
        "cities": ["Mumbai", "Delhi", "Bangalore", "Pune", "Dubai"],
    },
    "travel": {
        "avg_ticket": 12000, "std_ticket": 18000,
        "fraud_rate": 0.015, "chargeback_rate": 0.012, "refund_rate": 0.15,
        "risk_score": 0.20, "transaction_frequency": "medium",
        "cities": ["Online", "Mumbai", "Delhi"],
    },
    "gambling": {
        "avg_ticket": 3500, "std_ticket": 5000,
        "fraud_rate": 0.08, "chargeback_rate": 0.06, "refund_rate": 0.01,
        "risk_score": 0.80, "transaction_frequency": "medium",
        "cities": ["Online"],
    },
    "wire_transfer": {
        "avg_ticket": 50000, "std_ticket": 80000,
        "fraud_rate": 0.05, "chargeback_rate": 0.002, "refund_rate": 0.01,
        "risk_score": 0.65, "transaction_frequency": "low",
        "cities": ["Online"],
    },
}

_MERCHANT_NAMES = {
    "grocery":       ["BigBasket", "Grofers", "DMart", "More Supermarket", "Reliance Fresh"],
    "fuel":          ["HP Petrol", "BPCL Fuel", "Indian Oil", "Shell Station", "Essar Fuel"],
    "ecommerce":     ["Amazon India", "Flipkart", "Myntra", "Meesho", "Nykaa"],
    "luxury_retail": ["Louis Vuitton", "Gucci India", "Tanishq", "Harrods", "Zara Premium"],
    "gaming":        ["Steam India", "Google Play", "Xbox Live", "Epic Games", "Garena"],
    "cryptocurrency":["CoinDCX", "WazirX", "Binance", "Coinbase", "ZebPay"],
    "restaurant":    ["Zomato Order", "Swiggy Dine", "McDonald's", "Burger King", "Nobu"],
    "travel":        ["MakeMyTrip", "Goibibo", "IRCTC", "IndiGo Airlines", "Air India"],
    "gambling":      ["Bet365", "Dream11 Pro", "MPL Gaming", "Rummy Circle", "Poker Stars"],
    "wire_transfer": ["Western Union", "Remit2India", "Wise Transfer", "TransferGo", "PayPal Transfer"],
}


def generate_merchant(category: str = None) -> Dict[str, Any]:
    if category is None or category not in _MERCHANT_TEMPLATES:
        category = random.choice(list(_MERCHANT_TEMPLATES.keys()))

    tmpl = _MERCHANT_TEMPLATES[category]
    names = _MERCHANT_NAMES.get(category, [f"{category}_merchant"])
    name = random.choice(names)

    city_pool = tmpl["cities"]
    city = random.choice(city_pool)
    country = "India" if city not in ["Online", "London", "Dubai"] else (
        "UK" if city == "London" else ("UAE" if city == "Dubai" else "Online")
    )

    # Add natural variation to rates
    chargeback_rate = round(tmpl["chargeback_rate"] * random.uniform(0.5, 2.0), 4)
    fraud_rate = round(tmpl["fraud_rate"] * random.uniform(0.5, 2.0), 4)
    reputation_score = round(max(0.0, 1.0 - tmpl["risk_score"] * random.uniform(0.8, 1.2)), 3)

    return {
        "merchant_id": f"mch_{uuid.uuid4().hex[:10]}",
        "merchant_name": name,
        "merchant_category": category,
        "city": city,
        "country": country,
        "avg_ticket_size": round(tmpl["avg_ticket"] * random.uniform(0.7, 1.5)),
        "std_ticket_size": tmpl["std_ticket"],
        "fraud_rate": fraud_rate,
        "chargeback_rate": chargeback_rate,
        "refund_rate": tmpl["refund_rate"],
        "risk_score": round(tmpl["risk_score"] * random.uniform(0.8, 1.2), 3),
        "reputation_score": reputation_score,
        "transaction_frequency": tmpl["transaction_frequency"],
        "customer_diversity": random.randint(10, 50000),
        "is_online": city == "Online",
    }


def generate_merchant_pool(count: int = 50) -> List[Dict[str, Any]]:
    """Generate a diverse merchant pool."""
    merchants = []
    # Ensure coverage across categories
    for category in _MERCHANT_TEMPLATES:
        merchants.append(generate_merchant(category))
    # Fill remainder randomly
    while len(merchants) < count:
        merchants.append(generate_merchant())
    return merchants[:count]
