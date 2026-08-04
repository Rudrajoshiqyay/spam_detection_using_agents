import csv
import os
import hashlib
import uuid
import random
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Generator

from app.models.transaction import Transaction
from app.synthetic.geo_generator import generate_location
from app.synthetic.device_generator import generate_device

_CACHE_DIR = "dataset/dataset1"

def _hash_to_uuid(string_val: str) -> str:
    """Consistently hash a string to a UUID format."""
    return str(uuid.UUID(hashlib.md5(string_val.encode("utf-8")).hexdigest()))

def load_csv_transactions(filename: str = "bs140513_032310.csv", limit: int = 100) -> List[Transaction]:
    """
    Load transactions from a Kaggle-style CSV and map them to our internal Transaction model.
    Expected headers: step,customer,age,gender,zipcodeOri,merchant,zipMerchant,category,amount,fraud
    """
    file_path = os.path.join(_CACHE_DIR, filename)
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"CSV dataset not found at {file_path}")

    transactions = []
    base_time = datetime.now(timezone.utc) - timedelta(days=7)

    with open(file_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i >= limit:
                break
            
            # Map CSV fields to internal schema
            customer_raw = row.get("customer", f"cust_{i}").strip("'")
            merchant_raw = row.get("merchant", f"merch_{i}").strip("'")
            amount_val = float(row.get("amount", 0.0))
            category_raw = row.get("category", "es_other").strip("'")
            step = int(row.get("step", 0))
            is_fraud = int(row.get("fraud", 0)) == 1

            # Consistent mapping
            # Map customer to a valid mock user to prevent 404s in the live engine
            valid_users = ["user_001", "user_002", "user_003", "user_004", "user_005"]
            # Use hash modulo to consistently assign the same customer to the same mock user
            hash_int = int(hashlib.md5(customer_raw.encode("utf-8")).hexdigest(), 16)
            user_id = valid_users[hash_int % len(valid_users)]
            
            merchant_id = _hash_to_uuid(merchant_raw)
            transaction_id = str(uuid.uuid4())
            
            # Generate missing fields
            dev = generate_device("mobile")
            loc = generate_location("normal", "Madrid") # Defaulting to Spain given 'es_' categories
            
            txn_time = base_time + timedelta(hours=step, minutes=random.randint(0, 59))
            
            # Remove 'es_' prefix from category
            clean_category = category_raw.replace("es_", "")
            
            txn = Transaction(
                transaction_id=transaction_id,
                user_id=user_id,
                amount=amount_val,
                currency="EUR",
                merchant_id=merchant_id,
                merchant_name=merchant_raw,
                merchant_category=clean_category,
                location_city=loc["city"],
                location_country=loc["country"],
                latitude=loc.get("latitude", 40.4168),
                longitude=loc.get("longitude", -3.7038),
                device_id=dev["device_id"],
                ip_address=dev.get("ip_address", "192.168.1.1"),
                channel="online" if "tech" in clean_category else "in-store",
                transaction_type="purchase",
                timestamp=txn_time,
                is_international=False,
                metadata={"ground_truth_fraud": is_fraud, "source": "csv"}
            )
            transactions.append(txn)
            
    return transactions
