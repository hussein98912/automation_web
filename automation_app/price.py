import json
from decimal import Decimal
import os

# Load KB
KB_PATH = os.path.join(os.path.dirname(__file__), "Knowledgebase.json")
with open(KB_PATH, "r", encoding="utf-8") as f:
    KB = json.load(f)

def get_service_info(service_title, industry=None):
    for svc in KB.get("services", []):
        if svc["title"].lower() == service_title.lower():
            return {
                "price": Decimal(svc["price"]),
                "industry": svc.get("industry")
            }

    return {"price": Decimal("0"), "industry": industry}

def calculate_order_price(service_title, host_duration, industry=None):
    """
    Calculate total price based on service title, industry, and hosting duration.
    """
    service_info = get_service_info(service_title, industry)
    base_price = service_info["price"]

    # Duration multiplier
    duration_multiplier = {
        "1_month": Decimal("1"),
        "3_months": Decimal("2.8"),
        "6_months": Decimal("5.2"),
        "12_months": Decimal("10"),
    }

    total_price = base_price * duration_multiplier.get(host_duration, Decimal("1"))
    return total_price
