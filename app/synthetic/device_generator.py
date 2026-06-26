"""
Device Generator — produces realistic device fingerprints and trust profiles.
"""

import random
import uuid
from typing import Dict, Any, Literal


_OS_POOL = [
    ("Android 13", "mobile"),
    ("Android 14", "mobile"),
    ("iOS 17", "mobile"),
    ("iOS 16", "mobile"),
    ("Windows 11", "desktop"),
    ("Windows 10", "desktop"),
    ("macOS Sonoma", "desktop"),
    ("iPadOS 17", "tablet"),
]

_BROWSERS = [
    "Chrome/120.0", "Chrome/119.0", "Safari/17.0", "Firefox/121.0",
    "Edge/120.0", "Samsung Browser/23.0", "Chrome Mobile/120.0",
]

DeviceMode = Literal["known", "new", "suspicious"]


def generate_device(mode: DeviceMode = "known") -> Dict[str, Any]:
    os_name, device_type = random.choice(_OS_POOL)
    browser = random.choice(_BROWSERS)
    device_id = f"dev_{uuid.uuid4().hex[:12]}"

    if mode == "known":
        trust_score = round(random.uniform(0.75, 0.98), 3)
        age_days = random.randint(60, 730)
        account_count = 1
        fraud_count = 0
    elif mode == "new":
        trust_score = round(random.uniform(0.30, 0.55), 3)
        age_days = random.randint(0, 7)
        account_count = 1
        fraud_count = 0
    else:  # suspicious
        trust_score = round(random.uniform(0.05, 0.30), 3)
        age_days = random.randint(1, 30)
        account_count = random.randint(3, 12)
        fraud_count = random.randint(1, 5)

    return {
        "device_id": device_id,
        "device_type": device_type,
        "os": os_name,
        "browser": browser,
        "fingerprint": f"fp_{uuid.uuid4().hex[:16]}",
        "trust_score": trust_score,
        "age_days": age_days,
        "account_count": account_count,
        "fraud_count": fraud_count,
        "mode": mode,
        "ip_address": _random_ip(mode),
    }


def _random_ip(mode: DeviceMode) -> str:
    if mode == "suspicious":
        # Use known suspicious IP ranges (anonymized)
        return f"{random.choice([45, 185, 104, 91])}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"
    return f"103.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"
