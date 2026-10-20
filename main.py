"""
Insider Cluster Buy Tracker -- main entry point.

Run this daily (via cron or a scheduler) to:
1. Pull recent Form 4 filings from SEC EDGAR
2. Parse out qualifying open-market purchases
3. Save new ones to the local database
4. Detect clusters (2+ insiders, same company, short window)
5. Send a digest to you and your dad

Usage:
    python main.py

Setup:
    pip install -r requirements.txt
    Edit config.py: set SEC_USER_AGENT to your real name/email (SEC requires this),
    set your WATCHLIST if you want to scope it down, and configure ALERT_METHOD.
"""

import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import LOOKBACK_DAYS, WATCHLIST
from edgar_client import get_recent_form4_filings, fetch_form4_xml
from parser import parse_form4_xml
from storage import init_db, save_transaction, get_recent_transactions
from cluster_detector import detect_clusters
from digest import send_digest
from export_json import export_json


def run():
    print("Initializing database...")
    init_db()

    print(f"Fetching Form 4 filings from the last {LOOKBACK_DAYS} day(s)...")
    try:
        filings = get_recent_form4_filings(LOOKBACK_DAYS)
    except Exception as e:
        print(f"Failed to fetch filing list from EDGAR: {e}", file=sys.stderr)
        return

    print(f"Found {len(filings)} filings. Parsing each for qualifying purchases...")

    def process_filing(filing):
        xml_content = fetch_form4_xml(filing["index_url"])
        if not xml_content:
            return 0

        transactions = parse_form4_xml(xml_content)

        if WATCHLIST:
            transactions = [t for t in transactions if t.ticker in WATCHLIST]

        return sum(1 for tx in transactions if save_transaction(tx))

    new_tx_count = 0
    # RateLimiter in edgar_client caps actual requests/sec across all workers,
    # so this pool just keeps enough fetches in flight to use that budget.
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(process_filing, f): f for f in filings}
        for i, future in enumerate(as_completed(futures), 1):
            filing = futures[future]
            try:
                new_tx_count += future.result()
            except Exception as e:
                print(f"  Skipping filing {filing.get('accession_no')}: {e}", file=sys.stderr)

            if i % 20 == 0:
                print(f"  Processed {i}/{len(filings)} filings...")

    print(f"Saved {new_tx_count} new qualifying transactions.")

    print("Detecting clusters...")
    recent = get_recent_transactions(days=30)  # look back further than fetch window for clustering
    clusters = detect_clusters(recent)

    print(f"Found {len(clusters)} cluster(s). Sending digest...")
    digest_text = send_digest(clusters)

    n_exported = export_json()
    print(f"Exported {n_exported} transactions for the web dashboard.")
    print("\nDone. Digest sent via configured ALERT_METHOD.")


if __name__ == "__main__":
    run()
