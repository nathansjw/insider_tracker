"""
Drops purchases that would distort the screener. Raw rows stay in the database;
this filter is applied whenever transactions are read for clustering or export.

Two problems show up in real Form 4 data:

1. No exchange ticker. Issuers like private BDCs and interval funds file Form 4s
   with an issuerTradingSymbol of "NONE", "N/A", etc. Grouping by that value
   lumps unrelated companies into one fake "cluster", and they can't be bought
   on an exchange anyway.
2. Bad prices. Some filers type the wrong number into transactionPricePerShare
   (e.g. SLBT reported $2,272,653/share; its footnote says $0.50). One such row
   can add trillions of dollars to the totals.
"""

import re
from collections import defaultdict
from statistics import median

PLACEHOLDER_TICKERS = {"NONE", "N/A", "NA", "NULL", "-", "--", "N.A.", "NOT APPLICABLE"}
TICKER_RE = re.compile(r"^[A-Z][A-Z0-9]{0,5}([.\-][A-Z0-9]{1,2})?$")

# Above this per-share price, a purchase is treated as a data-entry error unless the
# ticker is one of the few US stocks that genuinely trade that high.
MAX_PLAUSIBLE_PRICE = 2_000
HIGH_PRICED_TICKERS = {
    "BRK.A", "BRK-A", "NVR", "BKNG", "AZO", "MKL", "SEB", "WTM", "FCNCA", "TPL",
    "MTD", "CABO", "NWLI", "MELI", "TDG", "ORLY", "FICO", "GWW", "CMG",
}

# A purchase priced this many times above/below the median of all the company's
# purchases is treated as a typo (catches errors under the absolute cap). Set well
# above 25x because some ADRs (e.g. PAM, 1 ADS = 25 local shares) legitimately show
# insiders buying both the ADS and the local share at very different prices.
OUTLIER_RATIO = 50


def _get(tx, key):
    return tx[key] if isinstance(tx, dict) else getattr(tx, key)


def clean_ticker(raw) -> str:
    """
    Normalized ticker, or "" if the issuer has no real exchange ticker.
    Handles filer formatting like "HEI, HEI.A" -> "HEI", "NYSE:FLG" -> "FLG", "[NONE]" -> "".
    """
    t = (raw or "").strip().upper().strip("[]()")
    if t in PLACEHOLDER_TICKERS:
        return ""
    t = re.split(r"[,;/\s]+", t)[0]          # first of several listed classes
    t = t.split(":")[-1]                      # drop exchange prefix
    if t in PLACEHOLDER_TICKERS or not TICKER_RE.match(t):
        return ""
    return t


def filter_transactions(transactions: list) -> list:
    """
    Return only purchases with a real ticker and a plausible price, as dicts with
    the ticker normalized. Input order is preserved.
    """
    kept = []
    for tx in transactions:
        ticker = clean_ticker(_get(tx, "ticker"))
        price = _get(tx, "price_per_share") or 0
        if not ticker or price <= 0:
            continue
        if price > MAX_PLAUSIBLE_PRICE and ticker not in HIGH_PRICED_TICKERS:
            continue
        row = dict(tx) if isinstance(tx, dict) else dict(vars(tx))
        row["ticker"] = ticker
        kept.append(row)

    prices = defaultdict(list)
    for tx in kept:
        prices[tx["ticker"]].append(tx["price_per_share"])
    ref = {t: median(ps) for t, ps in prices.items() if len(ps) >= 3}

    return [
        tx for tx in kept
        if tx["ticker"] not in ref
        or ref[tx["ticker"]] / OUTLIER_RATIO <= tx["price_per_share"] <= ref[tx["ticker"]] * OUTLIER_RATIO
    ]
