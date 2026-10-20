# Insider Cluster Buy Tracker

Watches SEC EDGAR for Form 4 filings (insider stock purchases) and flags when
2+ insiders at the same company buy within a short window — the pattern with
the strongest historical association with subsequent outperformance.

This is a **research prioritization tool**, not a trading signal. It tells you
where to look, not what to buy.

## Setup

```bash
pip install -r requirements.txt
```

Edit `config.py`:
- **`SEC_USER_AGENT`** — required. SEC blocks requests without a real identifying
  User-Agent (name + email). This isn't a paywall, just a courtesy/compliance requirement.
- **`MIN_PURCHASE_VALUE`** — dollar floor for a single purchase to be considered (default $50K)
- **`MIN_CLUSTER_SIZE`** — how many distinct insiders needed to count as a cluster (default 2)
- **`CLUSTER_WINDOW_DAYS`** — how many days apart purchases can be and still cluster (default 10)
- **`WATCHLIST`** — optional list of tickers to restrict to; leave empty to scan the whole market
- **`ALERT_METHOD`** — `"console"`, `"email"`, or `"slack"`, plus the relevant config block

## Run

```bash
python main.py
```

Run this daily via cron (or Task Scheduler on Windows) for a running digest.
Example cron entry for 7am daily:
```
0 7 * * * cd /path/to/insider_tracker && python3 main.py
```

## Web dashboard (GitHub Pages)

`docs/index.html` is a static dashboard that reads `docs/data.json` (written by
`export_json.py` at the end of every `main.py` run). It re-runs cluster detection
in the browser, so the dollar floor, insider count, window, and role filter are
live controls.

`.github/workflows/update.yml` runs the pipeline every weekday at 11:30 UTC,
sends the ntfy alert (tapping it opens the dashboard), and commits the updated
`insider_tracker.db` + `docs/data.json` back to the repo, which republishes the page.

One-time setup after pushing to GitHub:
1. **Settings → Pages** → Source: *Deploy from a branch*, branch `main`, folder `/docs`.
2. **Actions → Update insider data → Run workflow** with `lookback_days` = 20 to backfill history.

Preview locally: `cd docs && python3 -m http.server` and open http://localhost:8000.

## How it works

1. `edgar_client.py` — pulls recent Form 4 filing metadata from SEC's full-text search API
2. `parser.py` — fetches each filing's XML and extracts open-market purchases (transaction code "P"), filtering out sales, option exercises, and gifts
3. `storage.py` — saves to local SQLite, dedupes so you don't get re-alerted on the same filing
4. `cluster_detector.py` — groups purchases by company, flags clusters of 2+ distinct insiders within the configured window
5. `digest.py` — formats and sends the daily digest
6. `export_json.py` — writes `docs/data.json` for the web dashboard

## What it will NOT do

- Predict direction reliably — it surfaces candidates for research, nothing more
- Distinguish "just opened trading window post-earnings" clusters (weaker signal,
  often mechanical) from genuinely independent conviction buying (stronger signal) —
  that judgment call is on you, the tool just gets you the raw fact
- Account for 10b5-1 pre-scheduled trades, which don't reflect real-time conviction
  (worth checking manually on anything that looks interesting)
- Generate any specific expected return — the published academic effect for
  insider cluster buying is real but modest, and inconsistent year to year

## Suggested workflow

When a cluster fires:
1. Check whether it's right after an earnings release (weaker) or mid-quarter (stronger)
2. Check if any of the insiders have a routine pattern of buying (weaker) vs. this being unusual for them (stronger)
3. Do actual fundamental research before considering anything
4. Log the thesis and your conclusion somewhere you'll revisit in 6–12 months

## Known limitations of this version

- `edgar_client.py`'s filing-list fetch uses EDGAR's full-text search JSON API,
  which is the right approach but wasn't tested against live SEC servers in this
  sandbox (no internet access to sec.gov here) — validated with realistic mock
  Form 4 XML instead (see `test_pipeline.py`). Test against live EDGAR on your
  own machine before relying on it, and watch stderr for any filings it skips.
- SEC rate-limits to ~10 requests/second; the pipeline already sleeps between
  calls, but if you scan the whole market (no watchlist) a daily run can take
  a while the first time since it has to parse every Form 4 filed that day.
- No fundamentals enrichment yet (P/E, price action) — flagged in the code as
  a natural next step once the core pipeline is confirmed working for you.
