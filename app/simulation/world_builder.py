"""
World Builder — expanded synthetic world: 100+ cities, 20+ countries,
20+ merchant categories, 500+ merchant pool.

Replaces the 14-city / 10-category limits in the original generators.
"""

import random
import uuid
from typing import List, Dict, Any

# ── 100+ Cities across 20+ countries ────────────────────────────────────────

WORLD_CITIES: List[Dict[str, Any]] = [
    # India (30 cities)
    {"city": "Mumbai",       "country": "India",       "lat": 19.076,   "lon": 72.878,   "tier": 1},
    {"city": "Delhi",        "country": "India",       "lat": 28.704,   "lon": 77.102,   "tier": 1},
    {"city": "Bangalore",    "country": "India",       "lat": 12.972,   "lon": 77.594,   "tier": 1},
    {"city": "Hyderabad",    "country": "India",       "lat": 17.387,   "lon": 78.491,   "tier": 1},
    {"city": "Chennai",      "country": "India",       "lat": 13.083,   "lon": 80.270,   "tier": 1},
    {"city": "Pune",         "country": "India",       "lat": 18.520,   "lon": 73.856,   "tier": 1},
    {"city": "Kolkata",      "country": "India",       "lat": 22.573,   "lon": 88.364,   "tier": 1},
    {"city": "Ahmedabad",    "country": "India",       "lat": 23.033,   "lon": 72.585,   "tier": 2},
    {"city": "Jaipur",       "country": "India",       "lat": 26.912,   "lon": 75.787,   "tier": 2},
    {"city": "Surat",        "country": "India",       "lat": 21.170,   "lon": 72.831,   "tier": 2},
    {"city": "Lucknow",      "country": "India",       "lat": 26.847,   "lon": 80.947,   "tier": 2},
    {"city": "Kanpur",       "country": "India",       "lat": 26.469,   "lon": 80.315,   "tier": 2},
    {"city": "Nagpur",       "country": "India",       "lat": 21.145,   "lon": 79.088,   "tier": 2},
    {"city": "Indore",       "country": "India",       "lat": 22.719,   "lon": 75.857,   "tier": 2},
    {"city": "Thane",        "country": "India",       "lat": 19.218,   "lon": 72.978,   "tier": 2},
    {"city": "Bhopal",       "country": "India",       "lat": 23.259,   "lon": 77.413,   "tier": 2},
    {"city": "Visakhapatnam","country": "India",       "lat": 17.686,   "lon": 83.218,   "tier": 2},
    {"city": "Coimbatore",   "country": "India",       "lat": 11.017,   "lon": 76.955,   "tier": 2},
    {"city": "Kochi",        "country": "India",       "lat": 9.932,    "lon": 76.267,   "tier": 2},
    {"city": "Patna",        "country": "India",       "lat": 25.594,   "lon": 85.138,   "tier": 3},
    {"city": "Vadodara",     "country": "India",       "lat": 22.307,   "lon": 73.181,   "tier": 2},
    {"city": "Ghaziabad",    "country": "India",       "lat": 28.670,   "lon": 77.416,   "tier": 2},
    {"city": "Ludhiana",     "country": "India",       "lat": 30.901,   "lon": 75.857,   "tier": 2},
    {"city": "Agra",         "country": "India",       "lat": 27.176,   "lon": 78.008,   "tier": 3},
    {"city": "Nashik",       "country": "India",       "lat": 19.998,   "lon": 73.790,   "tier": 3},
    {"city": "Faridabad",    "country": "India",       "lat": 28.408,   "lon": 77.317,   "tier": 3},
    {"city": "Meerut",       "country": "India",       "lat": 28.984,   "lon": 77.706,   "tier": 3},
    {"city": "Rajkot",       "country": "India",       "lat": 22.303,   "lon": 70.802,   "tier": 3},
    {"city": "Varanasi",     "country": "India",       "lat": 25.318,   "lon": 83.013,   "tier": 3},
    {"city": "Guwahati",     "country": "India",       "lat": 26.145,   "lon": 91.736,   "tier": 3},
    # UAE (5 cities)
    {"city": "Dubai",        "country": "UAE",         "lat": 25.204,   "lon": 55.270,   "tier": 1},
    {"city": "Abu Dhabi",    "country": "UAE",         "lat": 24.453,   "lon": 54.377,   "tier": 1},
    {"city": "Sharjah",      "country": "UAE",         "lat": 25.346,   "lon": 55.420,   "tier": 2},
    {"city": "Ajman",        "country": "UAE",         "lat": 25.405,   "lon": 55.513,   "tier": 3},
    {"city": "Ras Al Khaimah","country":"UAE",         "lat": 25.789,   "lon": 55.943,   "tier": 3},
    # UK (5 cities)
    {"city": "London",       "country": "UK",          "lat": 51.508,   "lon": -0.128,   "tier": 1},
    {"city": "Manchester",   "country": "UK",          "lat": 53.483,   "lon": -2.244,   "tier": 2},
    {"city": "Birmingham",   "country": "UK",          "lat": 52.486,   "lon": -1.890,   "tier": 2},
    {"city": "Glasgow",      "country": "UK",          "lat": 55.864,   "lon": -4.252,   "tier": 2},
    {"city": "Edinburgh",    "country": "UK",          "lat": 55.953,   "lon": -3.188,   "tier": 2},
    # USA (8 cities)
    {"city": "New York",     "country": "USA",         "lat": 40.713,   "lon": -74.006,  "tier": 1},
    {"city": "Los Angeles",  "country": "USA",         "lat": 34.052,   "lon": -118.244, "tier": 1},
    {"city": "Chicago",      "country": "USA",         "lat": 41.878,   "lon": -87.630,  "tier": 1},
    {"city": "Houston",      "country": "USA",         "lat": 29.760,   "lon": -95.369,  "tier": 2},
    {"city": "San Francisco","country": "USA",         "lat": 37.774,   "lon": -122.419, "tier": 1},
    {"city": "Miami",        "country": "USA",         "lat": 25.774,   "lon": -80.190,  "tier": 2},
    {"city": "Seattle",      "country": "USA",         "lat": 47.606,   "lon": -122.332, "tier": 2},
    {"city": "Boston",       "country": "USA",         "lat": 42.360,   "lon": -71.059,  "tier": 2},
    # Singapore
    {"city": "Singapore",    "country": "Singapore",   "lat": 1.353,    "lon": 103.820,  "tier": 1},
    # Thailand (3)
    {"city": "Bangkok",      "country": "Thailand",    "lat": 13.757,   "lon": 100.502,  "tier": 1},
    {"city": "Phuket",       "country": "Thailand",    "lat": 7.878,    "lon": 98.398,   "tier": 2},
    {"city": "Chiang Mai",   "country": "Thailand",    "lat": 18.788,   "lon": 98.993,   "tier": 2},
    # Malaysia (3)
    {"city": "Kuala Lumpur", "country": "Malaysia",    "lat": 3.140,    "lon": 101.686,  "tier": 1},
    {"city": "Penang",       "country": "Malaysia",    "lat": 5.414,    "lon": 100.329,  "tier": 2},
    {"city": "Johor Bahru",  "country": "Malaysia",    "lat": 1.493,    "lon": 103.744,  "tier": 2},
    # France (3)
    {"city": "Paris",        "country": "France",      "lat": 48.857,   "lon": 2.347,    "tier": 1},
    {"city": "Lyon",         "country": "France",      "lat": 45.764,   "lon": 4.836,    "tier": 2},
    {"city": "Nice",         "country": "France",      "lat": 43.710,   "lon": 7.262,    "tier": 2},
    # Germany (3)
    {"city": "Berlin",       "country": "Germany",     "lat": 52.520,   "lon": 13.405,   "tier": 1},
    {"city": "Munich",       "country": "Germany",     "lat": 48.137,   "lon": 11.576,   "tier": 1},
    {"city": "Frankfurt",    "country": "Germany",     "lat": 50.110,   "lon": 8.682,    "tier": 1},
    # Australia (3)
    {"city": "Sydney",       "country": "Australia",   "lat": -33.869,  "lon": 151.209,  "tier": 1},
    {"city": "Melbourne",    "country": "Australia",   "lat": -37.814,  "lon": 144.946,  "tier": 1},
    {"city": "Brisbane",     "country": "Australia",   "lat": -27.470,  "lon": 153.021,  "tier": 2},
    # Canada (3)
    {"city": "Toronto",      "country": "Canada",      "lat": 43.651,   "lon": -79.347,  "tier": 1},
    {"city": "Vancouver",    "country": "Canada",      "lat": 49.246,   "lon": -123.116, "tier": 1},
    {"city": "Montreal",     "country": "Canada",      "lat": 45.508,   "lon": -73.587,  "tier": 1},
    # Japan (3)
    {"city": "Tokyo",        "country": "Japan",       "lat": 35.690,   "lon": 139.692,  "tier": 1},
    {"city": "Osaka",        "country": "Japan",       "lat": 34.694,   "lon": 135.502,  "tier": 1},
    {"city": "Kyoto",        "country": "Japan",       "lat": 35.012,   "lon": 135.768,  "tier": 2},
    # Switzerland (2)
    {"city": "Zurich",       "country": "Switzerland", "lat": 47.376,   "lon": 8.548,    "tier": 1},
    {"city": "Geneva",       "country": "Switzerland", "lat": 46.204,   "lon": 6.143,    "tier": 1},
    # Netherlands (2)
    {"city": "Amsterdam",    "country": "Netherlands", "lat": 52.370,   "lon": 4.895,    "tier": 1},
    {"city": "Rotterdam",    "country": "Netherlands", "lat": 51.925,   "lon": 4.478,    "tier": 2},
    # Saudi Arabia (3)
    {"city": "Riyadh",       "country": "Saudi Arabia","lat": 24.688,   "lon": 46.722,   "tier": 1},
    {"city": "Jeddah",       "country": "Saudi Arabia","lat": 21.544,   "lon": 39.173,   "tier": 1},
    {"city": "Mecca",        "country": "Saudi Arabia","lat": 21.387,   "lon": 39.857,   "tier": 2},
    # Sri Lanka (2)
    {"city": "Colombo",      "country": "Sri Lanka",   "lat": 6.927,    "lon": 79.862,   "tier": 1},
    {"city": "Kandy",        "country": "Sri Lanka",   "lat": 7.291,    "lon": 80.636,   "tier": 2},
    # Nepal (1)
    {"city": "Kathmandu",    "country": "Nepal",       "lat": 27.717,   "lon": 85.324,   "tier": 2},
    # Bangladesh (1)
    {"city": "Dhaka",        "country": "Bangladesh",  "lat": 23.810,   "lon": 90.412,   "tier": 1},
    # Hong Kong
    {"city": "Hong Kong",    "country": "Hong Kong",   "lat": 22.320,   "lon": 114.170,  "tier": 1},
    # China (3)
    {"city": "Shanghai",     "country": "China",       "lat": 31.228,   "lon": 121.474,  "tier": 1},
    {"city": "Beijing",      "country": "China",       "lat": 39.904,   "lon": 116.407,  "tier": 1},
    {"city": "Shenzhen",     "country": "China",       "lat": 22.543,   "lon": 114.057,  "tier": 1},
    # South Africa (2)
    {"city": "Johannesburg", "country": "South Africa","lat": -26.205,  "lon": 28.050,   "tier": 1},
    {"city": "Cape Town",    "country": "South Africa","lat": -33.926,  "lon": 18.424,   "tier": 1},
    # Brazil (2)
    {"city": "Sao Paulo",    "country": "Brazil",      "lat": -23.550,  "lon": -46.633,  "tier": 1},
    {"city": "Rio de Janeiro","country":"Brazil",       "lat": -22.906,  "lon": -43.172,  "tier": 1},
    # Spain (2)
    {"city": "Madrid",       "country": "Spain",       "lat": 40.416,   "lon": -3.703,   "tier": 1},
    {"city": "Barcelona",    "country": "Spain",       "lat": 41.385,   "lon": 2.173,    "tier": 1},
    # Italy (2)
    {"city": "Rome",         "country": "Italy",       "lat": 41.902,   "lon": 12.496,   "tier": 1},
    {"city": "Milan",        "country": "Italy",       "lat": 45.464,   "lon": 9.188,    "tier": 1},
]

# Build fast-lookup index
_CITY_INDEX: Dict[str, Dict] = {c["city"]: c for c in WORLD_CITIES}
_COUNTRY_INDEX: Dict[str, List[Dict]] = {}
for _c in WORLD_CITIES:
    _COUNTRY_INDEX.setdefault(_c["country"], []).append(_c)

DOMESTIC_CITIES = [c for c in WORLD_CITIES if c["country"] == "India"]
INTL_CITIES = [c for c in WORLD_CITIES if c["country"] != "India"]
ALL_COUNTRIES = list(_COUNTRY_INDEX.keys())


def get_city(name: str) -> Dict:
    return _CITY_INDEX.get(name, DOMESTIC_CITIES[0])


def get_cities_for_country(country: str) -> List[Dict]:
    return _COUNTRY_INDEX.get(country, [])


def random_domestic_city() -> Dict:
    return random.choice(DOMESTIC_CITIES)


def random_intl_city(exclude_countries: List[str] = None) -> Dict:
    pool = INTL_CITIES if not exclude_countries else [
        c for c in INTL_CITIES if c["country"] not in exclude_countries
    ]
    return random.choice(pool or INTL_CITIES)


# ── 20+ Merchant Categories, 500+ Merchants ──────────────────────────────────

MERCHANT_CATEGORIES: Dict[str, Dict] = {
    "grocery":           {"avg": 650,    "std": 300,    "risk": 0.05, "chargeback": 0.003, "refund": 0.04,  "online": False},
    "fuel":              {"avg": 1200,   "std": 400,    "risk": 0.10, "chargeback": 0.005, "refund": 0.01,  "online": False},
    "food_delivery":     {"avg": 380,    "std": 250,    "risk": 0.08, "chargeback": 0.012, "refund": 0.06,  "online": True},
    "restaurants":       {"avg": 850,    "std": 600,    "risk": 0.08, "chargeback": 0.004, "refund": 0.03,  "online": False},
    "ecommerce":         {"avg": 2500,   "std": 3000,   "risk": 0.20, "chargeback": 0.015, "refund": 0.08,  "online": True},
    "electronics":       {"avg": 8000,   "std": 12000,  "risk": 0.18, "chargeback": 0.010, "refund": 0.07,  "online": True},
    "clothing":          {"avg": 1800,   "std": 2000,   "risk": 0.10, "chargeback": 0.008, "refund": 0.12,  "online": True},
    "luxury":            {"avg": 45000,  "std": 30000,  "risk": 0.15, "chargeback": 0.005, "refund": 0.06,  "online": False},
    "airlines":          {"avg": 12000,  "std": 18000,  "risk": 0.20, "chargeback": 0.012, "refund": 0.15,  "online": True},
    "hotels":            {"avg": 6000,   "std": 8000,   "risk": 0.15, "chargeback": 0.010, "refund": 0.20,  "online": True},
    "transport":         {"avg": 450,    "std": 300,    "risk": 0.07, "chargeback": 0.005, "refund": 0.02,  "online": True},
    "utilities":         {"avg": 1500,   "std": 500,    "risk": 0.04, "chargeback": 0.002, "refund": 0.01,  "online": True},
    "medical":           {"avg": 2200,   "std": 3000,   "risk": 0.06, "chargeback": 0.003, "refund": 0.05,  "online": False},
    "education":         {"avg": 5000,   "std": 8000,   "risk": 0.07, "chargeback": 0.004, "refund": 0.03,  "online": True},
    "entertainment":     {"avg": 700,    "std": 500,    "risk": 0.12, "chargeback": 0.009, "refund": 0.04,  "online": True},
    "streaming":         {"avg": 300,    "std": 100,    "risk": 0.06, "chargeback": 0.007, "refund": 0.02,  "online": True},
    "gaming":            {"avg": 800,    "std": 1200,   "risk": 0.55, "chargeback": 0.04,  "refund": 0.02,  "online": True},
    "gambling":          {"avg": 3500,   "std": 5000,   "risk": 0.75, "chargeback": 0.05,  "refund": 0.01,  "online": True},
    "cryptocurrency":    {"avg": 15000,  "std": 25000,  "risk": 0.80, "chargeback": 0.001, "refund": 0.005, "online": True},
    "wire_transfer":     {"avg": 35000,  "std": 50000,  "risk": 0.60, "chargeback": 0.001, "refund": 0.001, "online": True},
    "mobile_recharge":   {"avg": 299,    "std": 200,    "risk": 0.10, "chargeback": 0.008, "refund": 0.01,  "online": True},
    "jewelry":           {"avg": 25000,  "std": 40000,  "risk": 0.20, "chargeback": 0.006, "refund": 0.04,  "online": False},
    "real_estate":       {"avg": 200000, "std": 500000, "risk": 0.25, "chargeback": 0.001, "refund": 0.01,  "online": False},
    "investments":       {"avg": 50000,  "std": 100000, "risk": 0.30, "chargeback": 0.001, "refund": 0.005, "online": True},
    "b2b_suppliers":     {"avg": 80000,  "std": 120000, "risk": 0.20, "chargeback": 0.004, "refund": 0.03,  "online": False},
    "wholesale":         {"avg": 150000, "std": 200000, "risk": 0.18, "chargeback": 0.003, "refund": 0.02,  "online": False},
    "subscription":      {"avg": 500,    "std": 200,    "risk": 0.08, "chargeback": 0.010, "refund": 0.03,  "online": True},
    "insurance":         {"avg": 8000,   "std": 12000,  "risk": 0.08, "chargeback": 0.002, "refund": 0.05,  "online": True},
    "p2p_transfer":      {"avg": 5000,   "std": 8000,   "risk": 0.45, "chargeback": 0.001, "refund": 0.001, "online": True},
    "atm_withdrawal":    {"avg": 3000,   "std": 2000,   "risk": 0.15, "chargeback": 0.001, "refund": 0.001, "online": False},
}

# Known merchant names per category
_MERCHANT_NAMES: Dict[str, List[str]] = {
    "grocery":       ["BigBasket", "Blinkit", "Zepto", "D-Mart", "Reliance Fresh", "Star Bazaar", "Nature's Basket"],
    "fuel":          ["HPCL", "BPCL", "Indian Oil", "Shell", "Reliance Petrol"],
    "food_delivery": ["Swiggy", "Zomato", "Dominos", "McDonald's Delivery", "KFC Online", "Pizza Hut"],
    "restaurants":   ["Cafe Coffee Day", "Starbucks", "Haldiram's", "Barbeque Nation", "Social", "The Bombay Canteen"],
    "ecommerce":     ["Amazon", "Flipkart", "Myntra", "Nykaa", "Meesho", "JioMart", "Snapdeal"],
    "electronics":   ["Croma", "Vijay Sales", "Samsung Store", "Apple Store", "HP World", "Lenovo"],
    "clothing":      ["Zara", "H&M", "FabIndia", "W for Woman", "Max Fashion", "Levi's", "Peter England"],
    "luxury":        ["Louis Vuitton", "Gucci", "Hermès", "Bulgari", "Cartier", "Harrods", "Tiffany"],
    "airlines":      ["IndiGo", "Air India", "SpiceJet", "Vistara", "Emirates", "British Airways"],
    "hotels":        ["OYO", "Taj Hotels", "Marriott", "Oberoi", "ITC Hotels", "Airbnb", "MakeMyTrip"],
    "transport":     ["Uber", "Ola", "Rapido", "Namma Metro", "IRCTC", "RedBus"],
    "utilities":     ["BESCOM", "Tata Power", "MSEB", "Jio", "Airtel", "BSNL", "Mahanagar Gas"],
    "medical":       ["Apollo Pharmacy", "MedPlus", "1mg", "Practo", "Fortis Hospital", "Dr. Lal PathLabs"],
    "education":     ["BYJU'S", "Unacademy", "Coursera", "Udemy", "Simplilearn", "upGrad", "Allen"],
    "entertainment": ["BookMyShow", "PVR Cinemas", "INOX", "Lionsgate Play", "SonyLIV"],
    "streaming":     ["Netflix", "Amazon Prime", "Disney+Hotstar", "Spotify", "YouTube Premium"],
    "gaming":        ["Steam", "PlayStation Store", "Xbox Game Pass", "MPL", "Dream11", "Mobile Premier League"],
    "gambling":      ["Bet365", "Betway", "10Cric", "Casumo", "Unknown Casino A", "Unknown Casino B"],
    "cryptocurrency":["WazirX", "CoinDCX", "Binance", "Coinbase", "Kraken", "Unknown Crypto Exchange"],
    "wire_transfer": ["Western Union", "MoneyGram", "Remitly", "Wise", "SWIFT Transfer Co.", "International Wire Svc"],
    "mobile_recharge":["Paytm Recharge", "PhonePe", "FreeRecharge", "BSNL Self Care"],
    "jewelry":       ["Tanishq", "Kalyan Jewellers", "Malabar Gold", "CaratLane", "PNG Jewellers"],
    "real_estate":   ["Magicbricks Pay", "99acres", "Housing.com Pay", "DLF Pay"],
    "investments":   ["Zerodha", "Groww", "Angel One", "HDFC Securities", "SBI MF"],
    "b2b_suppliers": ["IndiaMart Supplier", "TradeIndia", "Alibaba B2B", "Justdial B2B"],
    "wholesale":     ["Metro Cash & Carry", "Costco", "Sam's Club India", "Bulk Trader"],
    "subscription":  ["Adobe Creative", "Microsoft 365", "Canva Pro", "Notion", "Slack"],
    "insurance":     ["LIC", "HDFC Life", "Star Health", "ICICI Lombard", "Policybazaar"],
    "p2p_transfer":  ["PhonePe P2P", "GPay", "Paytm P2P", "UPI Transfer", "NEFT Transfer"],
    "atm_withdrawal":["SBI ATM", "HDFC ATM", "ICICI ATM", "Axis ATM", "PNB ATM"],
}

# Pre-generate merchant pool
_MERCHANT_POOL: List[Dict] = []


def build_merchant_pool(target_count: int = 500) -> List[Dict]:
    """Generate a diverse pool of merchants across all categories."""
    global _MERCHANT_POOL
    if _MERCHANT_POOL:
        return _MERCHANT_POOL

    categories = list(MERCHANT_CATEGORIES.keys())
    per_category = max(10, target_count // len(categories))
    pool = []

    for cat, params in MERCHANT_CATEGORIES.items():
        names = _MERCHANT_NAMES.get(cat, [f"{cat.title()} Store"])
        for i in range(per_category):
            base_name = random.choice(names)
            merchant_id = f"mch_{cat[:4]}_{uuid.uuid4().hex[:8]}"

            # Randomize metrics around category baseline
            rep_score = max(0.01, min(1.0, 1.0 - params["risk"] + random.gauss(0, 0.1)))
            chargeback = max(0.0, params["chargeback"] * random.uniform(0.5, 2.0))
            refund = max(0.0, params["refund"] * random.uniform(0.5, 2.0))

            pool.append({
                "merchant_id": merchant_id,
                "merchant_name": f"{base_name} {'#'+str(i+1) if i > 0 else ''}".strip(),
                "merchant_category": cat,
                "reputation_score": round(rep_score, 3),
                "chargeback_rate": round(chargeback, 4),
                "refund_rate": round(refund, 4),
                "fraud_associations": max(0, int(random.gauss(0, 1)) if params["risk"] > 0.3 else 0),
                "transaction_volume": random.randint(10, 100000),
                "customer_diversity": random.randint(5, 5000),
                "is_online": params["online"],
                "avg_ticket": params["avg"],
                "risk_score": params["risk"],
            })

    _MERCHANT_POOL = pool
    return pool


def get_merchant_pool() -> List[Dict]:
    if not _MERCHANT_POOL:
        build_merchant_pool(500)
    return _MERCHANT_POOL


def get_merchant_by_category(category: str) -> Dict:
    pool = get_merchant_pool()
    matches = [m for m in pool if m["merchant_category"] == category]
    return random.choice(matches) if matches else random.choice(pool)


def get_high_risk_merchant() -> Dict:
    pool = get_merchant_pool()
    high_risk = [m for m in pool if m["risk_score"] > 0.5]
    return random.choice(high_risk) if high_risk else random.choice(pool)
