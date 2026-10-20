"""
Pulls Form 4 filings from SEC EDGAR.

We use EDGAR's DAILY INDEX files, not the full-text search API. Full-text
search requires an actual keyword (it's built for "find filings containing
this phrase"), and Form 4 filings barely have free text in them anyway --
so it's the wrong tool for "give me every Form 4 filed this week." The daily
index is SEC's own enumeration of every filing, by form type, per day.

Docs: https://www.sec.gov/Archives/edgar/daily-index/
"""

import re
import requests
import threading
import time
from collections import deque
from datetime import datetime, timedelta

from config import SEC_USER_AGENT, LOOKBACK_DAYS

HEADERS = {"User-Agent": SEC_USER_AGENT}


class RateLimiter:
    """Caps requests to N/second across all threads (SEC allows ~10/sec)."""

    def __init__(self, max_per_second: int):
        self.max_per_second = max_per_second
        self.lock = threading.Lock()
        self.timestamps = deque()

    def acquire(self):
        with self.lock:
            while True:
                now = time.monotonic()
                while self.timestamps and now - self.timestamps[0] > 1:
                    self.timestamps.popleft()
                if len(self.timestamps) < self.max_per_second:
                    self.timestamps.append(now)
                    return
                time.sleep(self.timestamps[0] + 1 - now)


_rate_limiter = RateLimiter(max_per_second=8)  # stay under SEC's ~10/sec limit


def _get(url, **kwargs):
    _rate_limiter.acquire()
    return requests.get(url, headers=HEADERS, **kwargs)

# Each line in a daily form.idx file looks like (fields are space-padded, not fixed-width
# in a way that's safe to slice blindly, so we parse with a regex instead):
#   4           Example Corp                              0001234567  2026-08-06  edgar/data/1234567/0001234567-26-000123.txt
FORM_LINE_RE = re.compile(
    r"^(?P<form>\S+)\s+(?P<company>.+?)\s+(?P<cik>\d{1,10})\s+"
    r"(?P<date>\d{8})\s+(?P<path>edgar\S+)\s*$"
)

ACCESSION_RE = re.compile(r"(\d{10}-\d{2}-\d{6})\.txt$")


def _business_days_back(n_days: int) -> list:
    """Returns the last n_days calendar days that are weekdays (SEC doesn't file on weekends)."""
    days = []
    d = datetime.utcnow().date()
    while len(days) < n_days:
        if d.weekday() < 5:  # Mon-Fri
            days.append(d)
        d -= timedelta(days=1)
    return days


def get_recent_form4_filings(lookback_days: int = LOOKBACK_DAYS) -> list[dict]:
    """
    Returns a list of recent Form 4 filing metadata dicts:
    {cik, company_name, filing_date, accession_no, index_url}
    """
    filings = []
    for day in _business_days_back(lookback_days):
        quarter = (day.month - 1) // 3 + 1
        date_str = day.strftime("%Y%m%d")
        url = (
            f"https://www.sec.gov/Archives/edgar/daily-index/"
            f"{day.year}/QTR{quarter}/form.{date_str}.idx"
        )
        resp = _get(url, timeout=20)
        if resp.status_code != 200:
            # No filings that day (holiday) or index not yet published -- skip, don't crash
            continue

        for line in resp.text.splitlines():
            match = FORM_LINE_RE.match(line.strip())
            if not match:
                continue
            if match.group("form") != "4":  # exact Form 4 only, not "4/A" amendments
                continue

            path = match.group("path")
            acc_match = ACCESSION_RE.search(path)
            if not acc_match:
                continue

            accession_no = acc_match.group(1)
            accession_no_nodash = accession_no.replace("-", "")
            cik = str(int(match.group("cik")))  # strip leading zeros for the URL path
            raw_date = match.group("date")
            filing_date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}"

            filings.append(
                {
                    "cik": cik,
                    "company_name": match.group("company").strip(),
                    "filing_date": filing_date,
                    "accession_no": accession_no,
                    "index_url": (
                        f"https://www.sec.gov/Archives/edgar/data/"
                        f"{cik}/{accession_no_nodash}/"
                    ),
                }
            )

    return filings

def fetch_form4_xml(filing_index_url: str) -> str | None:
    """
    Given a filing's index directory URL, find and fetch the actual Form 4 XML document.
    """
    json_url = filing_index_url + "index.json"
    idx_resp = _get(json_url, timeout=15)
    if idx_resp.status_code != 200:
        return None

    items = idx_resp.json().get("directory", {}).get("item", [])
    xml_files = [i["name"] for i in items if i["name"].endswith(".xml")]
    if not xml_files:
        return None

    xml_url = filing_index_url + xml_files[0]
    xml_resp = _get(xml_url, timeout=15)
    if xml_resp.status_code != 200:
        return None
    return xml_resp.text