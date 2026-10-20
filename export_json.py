"""
Exports stored transactions to a JSON file the static web dashboard (docs/) reads.

The dashboard re-runs cluster detection in the browser so thresholds can be
tweaked live, so we export the raw purchases rather than pre-computed clusters.
"""

import json
import os
from datetime import datetime, timezone

from config import (
    WEB_DATA_PATH, MIN_PURCHASE_VALUE, MIN_CLUSTER_SIZE, CLUSTER_WINDOW_DAYS,
)
from storage import get_recent_transactions

EXPORT_DAYS = 180  # how much history the dashboard gets


def export_json(path: str = WEB_DATA_PATH) -> int:
    rows = get_recent_transactions(days=EXPORT_DAYS)
    transactions = [
        {
            "company_name": r["company_name"],
            "ticker": (r["ticker"] or "").upper(),
            "insider_name": r["insider_name"],
            "insider_title": r["insider_title"],
            "shares": r["shares"],
            "price_per_share": r["price_per_share"],
            "transaction_date": r["transaction_date"],
            "total_value": round(r["total_value"], 2),
        }
        for r in rows
    ]
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "defaults": {
            "min_purchase_value": MIN_PURCHASE_VALUE,
            "min_cluster_size": MIN_CLUSTER_SIZE,
            "cluster_window_days": CLUSTER_WINDOW_DAYS,
        },
        "transactions": transactions,
    }
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(payload, f, indent=1)
    return len(transactions)


if __name__ == "__main__":
    n = export_json()
    print(f"Exported {n} transactions to {WEB_DATA_PATH}")
