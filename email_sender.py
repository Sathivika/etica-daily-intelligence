"""
email_sender.py
Assembles the final HTML report and sends it via Gmail SMTP.
"""

import os
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Recipients ────────────────────────────────────────────────────────────────
RECIPIENTS = [
    os.environ.get("RECIPIENT_1", ""),
    os.environ.get("RECIPIENT_2", ""),
]


def _load_template() -> str:
    template_path = Path(__file__).parent / "templates" / "report.html"
    return template_path.read_text(encoding="utf-8")


def _build_market_snapshot_html(snapshot: dict) -> str:
    """
    Builds the market snapshot section as an HTML table — 3 cards per row.
    Row 1: Nifty, Sensex, USD/INR
    Row 2: Gold, Silver, Crude Oil
    Table layout ensures correct rendering in all email clients including mobile.
    """

    def _td(data: dict) -> str:
        color  = "#16a34a" if data["direction"] == "up" else ("#dc2626" if data["direction"] == "down" else "#888888")
        arrow  = "▲" if data["direction"] == "up" else ("▼" if data["direction"] == "down" else "—")
        bg     = "#f0fdf4" if data["direction"] == "up" else ("#fef2f2" if data["direction"] == "down" else "#f9f9f9")
        border = "#86efac" if data["direction"] == "up" else ("#fca5a5" if data["direction"] == "down" else "#e0e0e0")
        return (
            f'<td class="snapshot-card" style="background:{bg};border:1px solid {border};">'
            f'<div class="snapshot-label">{data["label"]}</div>'
            f'<div class="snapshot-price">{data["price"]}</div>'
            f'<div class="snapshot-change" style="color:{color};">{arrow} {data["change"]} ({data["pct_change"]})</div>'
            f'</td>'
        )

    row1 = _td(snapshot["nifty"]) + _td(snapshot["sensex"]) + _td(snapshot["usdinr"])
    row2 = _td(snapshot["gold"])  + _td(snapshot["silver"]) + _td(snapshot["crude"])

    return f"""
<div class="market-snapshot">
  <div class="snapshot-heading">📈 Market Snapshot</div>
  <table class="snapshot-grid">
    <tr>{row1}</tr>
    <tr>{row2}</tr>
  </table>
  <div class="snapshot-note">Live prices as of email delivery &nbsp;·&nbsp; Nifty/Sensex/USD/Crude: Yahoo Finance &nbsp;·&nbsp; Gold/Silver: IBJA</div>
</div>"""


def _build_category_sections(categories: dict[str, str]) -> str:
    sections = []
    for category, html in categories.items():
        section = f"""
<div class="category-block">
  <div class="category-label">{category}</div>
  {html}
</div>
"""
        sections.append(section)
    return "\n".join(sections)


def build_email_html(summarized: dict, snapshot: dict) -> str:
    template = _load_template()

    now      = datetime.now()
    date_str = now.strftime("%A, %d %B %Y")
    year_str = str(now.year)

    market_snapshot_html = _build_market_snapshot_html(snapshot)
    category_sections    = _build_category_sections(summarized["categories"])

    html = (
        template
        .replace("{{DATE}}",             date_str)
        .replace("{{YEAR}}",             year_str)
        .replace("{{LOGO_URL}}",         "https://raw.githubusercontent.com/Sathivika/etica-daily-intelligence/main/templates/assets/etica_logo.png")
        .replace("{{MARKET_SNAPSHOT}}",  market_snapshot_html)
        .replace("{{EXECUTIVE_SUMMARY}}", summarized["executive_summary"])
        .replace("{{CATEGORY_SECTIONS}}", category_sections)
    )
    return html


def send_email(html_content: str) -> None:
    sender_email    = os.environ["EMAIL_USER"]
    sender_password = os.environ["EMAIL_PASSWORD"]

    today   = datetime.now().strftime("%d %b %Y")
    subject = f"Etica Daily Intelligence Brief · {today}"

    recipients = [r for r in RECIPIENTS if r]
    if not recipients:
        logger.warning("No recipients configured. Set RECIPIENT_1, RECIPIENT_2, etc. in GitHub Secrets.")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"Etica Intelligence <{sender_email}>"
    msg["To"]      = ", ".join(recipients)
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    logger.info(f"Sending email to {len(recipients)} recipient(s)...")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, recipients, msg.as_string())
    logger.info("Email sent successfully.")


def send_failure_notification(error: str) -> None:
    try:
        sender_email    = os.environ.get("EMAIL_USER", "")
        sender_password = os.environ.get("EMAIL_PASSWORD", "")
        if not sender_email or not sender_password:
            return

        recipients = [r for r in RECIPIENTS if r]
        if not recipients:
            return

        msg = MIMEMultipart()
        msg["Subject"] = "⚠️ Etica News Automation Failed"
        msg["From"]    = f"Etica Intelligence <{sender_email}>"
        msg["To"]      = ", ".join(recipients)

        body = f"""Hi,

The Etica Daily Intelligence automation failed today.

Error:
{error}

Please check the GitHub Actions logs for details:
https://github.com/Sathivika/etica-daily-intelligence/actions

— Automated Alert
"""
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, recipients, msg.as_string())
        logger.info("Failure notification sent.")
    except Exception as e:
        logger.error(f"Could not send failure notification: {e}")