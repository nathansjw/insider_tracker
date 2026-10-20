"""
SQLite storage for insider transactions.
Keeps history so we can detect clusters (which requires looking back N days)
and avoid re-alerting on the same filing twice.
"""

import sqlite3
from contextlib import contextmanager
from config import DB_PATH


SCHEMA = """
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_name TEXT NOT NULL,
    ticker TEXT,
    insider_name TEXT NOT NULL,
    insider_title TEXT,
    transaction_code TEXT,
    shares REAL,
    price_per_share REAL,
    transaction_date TEXT,
    total_value REAL,
    inserted_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(company_name, insider_name, transaction_date, shares, price_per_share)
);

CREATE TABLE IF NOT EXISTS alerted_clusters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT,
    cluster_start_date TEXT,
    cluster_end_date TEXT,
    num_insiders INTEGER,
    alerted_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ticker, cluster_start_date, cluster_end_date)
);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)


def save_transaction(tx) -> bool:
    """Returns True if newly inserted, False if it was already there (duplicate filing)."""
    with get_conn() as conn:
        try:
            conn.execute(
                """
                INSERT INTO transactions
                (company_name, ticker, insider_name, insider_title, transaction_code,
                 shares, price_per_share, transaction_date, total_value)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tx.company_name, tx.ticker, tx.insider_name, tx.insider_title,
                    tx.transaction_code, tx.shares, tx.price_per_share,
                    tx.transaction_date, tx.total_value,
                ),
            )
            return True
        except sqlite3.IntegrityError:
            return False  # already recorded this exact transaction


def get_recent_transactions(days: int) -> list[sqlite3.Row]:
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT * FROM transactions
            WHERE transaction_date >= date('now', ?)
            ORDER BY ticker, transaction_date
            """,
            (f"-{days} days",),
        )
        return [dict(row) for row in cur.fetchall()]


def cluster_already_alerted(ticker: str, start_date: str, end_date: str) -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT 1 FROM alerted_clusters WHERE ticker=? AND cluster_start_date=? AND cluster_end_date=?",
            (ticker, start_date, end_date),
        )
        return cur.fetchone() is not None


def mark_cluster_alerted(ticker: str, start_date: str, end_date: str, num_insiders: int):
    with get_conn() as conn:
        try:
            conn.execute(
                """
                INSERT INTO alerted_clusters (ticker, cluster_start_date, cluster_end_date, num_insiders)
                VALUES (?, ?, ?, ?)
                """,
                (ticker, start_date, end_date, num_insiders),
            )
        except sqlite3.IntegrityError:
            pass
