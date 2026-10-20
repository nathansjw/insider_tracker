"""
Configuration for the insider cluster-buy tracker.
Tune these thresholds as you and your dad refine what counts as "worth an alert."
"""

import os

# SEC requires a descriptive User-Agent identifying who's making requests.
SEC_USER_AGENT = "Nathan Wong nathansjwong@gmail.com"

# Minimum dollar value of a SINGLE purchase to even consider it
MIN_PURCHASE_VALUE = 50_000

# Minimum number of distinct insiders buying at the same company to count as a "cluster"
MIN_CLUSTER_SIZE = 2

# How many trading days apart purchases can be and still count as the same cluster
CLUSTER_WINDOW_DAYS = 10

# Optional: restrict to a watchlist of tickers. Leave empty list to scan the whole market.
WATCHLIST = []  # e.g. ["NVDA", "CEVA", "WEX"]

# Only include these transaction codes (P = open market purchase).
# We deliberately exclude sales, option exercises, and gifts.
INCLUDE_TRANSACTION_CODES = ["P"]

# Exclude reporting owners who are ONLY a >=10% owner (not an officer or director) --
# these are typically VC/PE funds or institutional holders buying into a financing
# round (e.g. IPO/PIPE allocations), not an employee's personal conviction buy.
EXCLUDE_FUND_ONLY_OWNERS = True

# Local SQLite database file
DB_PATH = "insider_tracker.db"

# How many days back to look on each run (EDGAR full-text search doesn't paginate infinitely well,
# so keep this reasonably tight and run daily)
LOOKBACK_DAYS = int(os.environ.get("LOOKBACK_DAYS", 3))

#Alert delivery
ALERT_METHOD = os.environ.get("ALERT_METHOD", "ntfy")  # "console", "email", "slack", or "ntfy"

EMAIL_CONFIG = {
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "sender": "your_email@gmail.com",
    "sender_password": "",  # use an App Password, never your real password, and never commit this
    "recipients": ["you@example.com", "dad@example.com"],
}

SLACK_WEBHOOK_URL = ""  # https://hooks.slack.com/services/...

# ntfy.sh push notifications. Pick a hard-to-guess topic name -- anyone who knows
# it can read your digest and/or post to it, since public ntfy.sh topics aren't
# access-controlled. Install the ntfy app (iOS/Android) and subscribe to the same
# topic to get pushes on your phone; have your dad subscribe too.
NTFY_SERVER = "https://ntfy.sh"
NTFY_TOPIC = "insider-cluster-30f8c67d9a94"

# Optional: tapping the ntfy notification opens this URL (e.g. the GitHub Pages dashboard)
NTFY_CLICK_URL = os.environ.get("NTFY_CLICK_URL", "")

# Where export_json.py writes the data file the web dashboard reads
WEB_DATA_PATH = "docs/data.json"
