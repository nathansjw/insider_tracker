"""
Formats detected clusters into a readable digest and sends it via
console / email / Slack, depending on config.ALERT_METHOD.
"""

import smtplib
from email.mime.text import MIMEText
import requests

from config import ALERT_METHOD, EMAIL_CONFIG, SLACK_WEBHOOK_URL, NTFY_SERVER, NTFY_TOPIC, NTFY_CLICK_URL


def format_digest(clusters: list) -> str:
    if not clusters:
        return "No new insider buying clusters today. Nothing above threshold."

    lines = [f"**INSIDER CLUSTER BUY DIGEST -- {len(clusters)} companies flagged**\n"]
    for c in sorted(clusters, key=lambda x: x.total_value, reverse=True):
        lines.append(f"**{c.ticker} ({c.company_name})**")
        lines.append(f"  {c.num_insiders} insiders, ${c.total_value:,.0f} combined, {c.start_date} to {c.end_date}")
        for name, title, date, value in c.insiders:
            lines.append(f"    - {name} ({title}): ${value:,.0f} on {date}")
        lines.append("")
    return "\n".join(lines)


def send_digest(clusters: list):
    text = format_digest(clusters)

    if ALERT_METHOD == "console":
        print(text)

    elif ALERT_METHOD == "email":
        _send_email(text)

    elif ALERT_METHOD == "slack":
        _send_slack(text)

    elif ALERT_METHOD == "ntfy":
        _send_ntfy(text, num_clusters=len(clusters))

    else:
        print(f"Unknown ALERT_METHOD '{ALERT_METHOD}', printing to console instead:\n")
        print(text)

    return text


def _send_email(body: str):
    msg = MIMEText(body)
    msg["Subject"] = "Insider Cluster Buy Digest"
    msg["From"] = EMAIL_CONFIG["sender"]
    msg["To"] = ", ".join(EMAIL_CONFIG["recipients"])

    with smtplib.SMTP(EMAIL_CONFIG["smtp_server"], EMAIL_CONFIG["smtp_port"]) as server:
        server.starttls()
        server.login(EMAIL_CONFIG["sender"], EMAIL_CONFIG["sender_password"])
        server.sendmail(EMAIL_CONFIG["sender"], EMAIL_CONFIG["recipients"], msg.as_string())


def _send_slack(body: str):
    requests.post(SLACK_WEBHOOK_URL, json={"text": body}, timeout=10)


def _send_ntfy(body: str, num_clusters: int):
    if not NTFY_TOPIC:
        print("NTFY_TOPIC not set in config.py -- printing digest to console instead:\n")
        print(body)
        return

    title = (
        f"{num_clusters} insider cluster(s) flagged"
        if num_clusters
        else "No insider clusters today"
    )
    headers = {
        "Title": title,
        "Priority": "default" if num_clusters else "low",
        "Tags": "chart_with_upwards_trend" if num_clusters else "zzz",
        "Markdown": "yes",
    }
    if NTFY_CLICK_URL:
        headers["Click"] = NTFY_CLICK_URL
    requests.post(
        f"{NTFY_SERVER.rstrip('/')}/{NTFY_TOPIC}",
        data=body.encode("utf-8"),
        headers=headers,
        timeout=10,
    )
