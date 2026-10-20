"""
Groups recent insider purchases by company and flags clusters:
2+ DISTINCT insiders buying within a short window (default 10 trading days).

This is the core signal. Everything upstream (edgar_client, parser, storage)
just exists to feed this function clean data.
"""

from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict

from config import MIN_CLUSTER_SIZE, CLUSTER_WINDOW_DAYS


@dataclass
class Cluster:
    ticker: str
    company_name: str
    insiders: list  # list of (name, title, date, value)
    total_value: float
    start_date: str
    end_date: str

    @property
    def num_insiders(self) -> int:
        return len({name for name, *_ in self.insiders})


def _parse_date(d: str) -> datetime:
    return datetime.strptime(d, "%Y-%m-%d")


def detect_clusters(transactions: list) -> list[Cluster]:
    """
    transactions: iterable of rows/objects with attributes
    company_name, ticker, insider_name, insider_title, transaction_date, total_value

    Returns clusters meeting MIN_CLUSTER_SIZE within CLUSTER_WINDOW_DAYS.
    """
    by_ticker = defaultdict(list)
    for tx in transactions:
        by_ticker[tx["ticker"] if isinstance(tx, dict) else tx.ticker].append(tx)

    clusters = []

    for ticker, txs in by_ticker.items():
        if not ticker:
            continue

        # sort by date
        txs_sorted = sorted(
            txs,
            key=lambda t: t["transaction_date"] if isinstance(t, dict) else t.transaction_date,
        )

        # sliding window: for each purchase, look at all purchases within
        # CLUSTER_WINDOW_DAYS after it, and see how many DISTINCT insiders that covers
        n = len(txs_sorted)
        for i in range(n):
            t0 = txs_sorted[i]
            date0 = _parse_date(t0["transaction_date"] if isinstance(t0, dict) else t0.transaction_date)

            window_txs = [t0]
            for j in range(i + 1, n):
                tj = txs_sorted[j]
                date_j = _parse_date(tj["transaction_date"] if isinstance(tj, dict) else tj.transaction_date)
                if (date_j - date0).days <= CLUSTER_WINDOW_DAYS:
                    window_txs.append(tj)
                else:
                    break

            distinct_insiders = {
                (t["insider_name"] if isinstance(t, dict) else t.insider_name) for t in window_txs
            }

            if len(distinct_insiders) >= MIN_CLUSTER_SIZE:
                insiders_info = [
                    (
                        t["insider_name"] if isinstance(t, dict) else t.insider_name,
                        t["insider_title"] if isinstance(t, dict) else t.insider_title,
                        t["transaction_date"] if isinstance(t, dict) else t.transaction_date,
                        t["total_value"] if isinstance(t, dict) else t.total_value,
                    )
                    for t in window_txs
                ]
                clusters.append(
                    Cluster(
                        ticker=ticker,
                        company_name=(t0["company_name"] if isinstance(t0, dict) else t0.company_name),
                        insiders=insiders_info,
                        total_value=sum(v for *_, v in insiders_info),
                        start_date=(window_txs[0]["transaction_date"] if isinstance(window_txs[0], dict) else window_txs[0].transaction_date),
                        end_date=(window_txs[-1]["transaction_date"] if isinstance(window_txs[-1], dict) else window_txs[-1].transaction_date),
                    )
                )

    # Dedup: keep only the largest cluster per ticker (avoid overlapping sub-windows)
    best_per_ticker = {}
    for c in clusters:
        existing = best_per_ticker.get(c.ticker)
        if existing is None or c.num_insiders > existing.num_insiders:
            best_per_ticker[c.ticker] = c

    return list(best_per_ticker.values())
