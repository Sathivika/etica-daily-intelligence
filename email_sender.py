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

# ── Recipients — auto-scans RECIPIENT_1 through RECIPIENT_20 ─────────────────
# To add more recipients: just add RECIPIENT_3, RECIPIENT_4, etc. as GitHub Secrets.
# No code changes needed — this loop picks them up automatically.
RECIPIENTS = [
    os.environ[key].strip()
    for key in (f"RECIPIENT_{i}" for i in range(1, 21))
    if key in os.environ and os.environ[key].strip()
]


def _load_template() -> str:
    template_path = Path(__file__).parent / "templates" / "report.html"
    return template_path.read_text(encoding="utf-8")


def _build_market_snapshot_html(snapshot: dict) -> str:
    """
    Builds market snapshot as an HTML table — 2 cards per row, 5 rows.
    Order: Nifty, Sensex | Gold, Silver | USD/INR, Crude | S&P500, NASDAQ | Nikkei, HangSeng
    Table layout works reliably in all email clients on both desktop and mobile.
    """

    def _td(data: dict) -> str:
        color  = "#16a34a" if data["direction"] == "up" else ("#dc2626" if data["direction"] == "down" else "#888888")
        arrow  = "▲" if data["direction"] == "up" else ("▼" if data["direction"] == "down" else "—")
        bg     = "#f0fdf4" if data["direction"] == "up" else ("#fef2f2" if data["direction"] == "down" else "#f9f9f9")
        border = "#86efac" if data["direction"] == "up" else ("#fca5a5" if data["direction"] == "down" else "#e0e0e0")
        return (
            f'<td class="snapshot-card" style="background:{bg};border:1px solid {border};width:50%;">'
            f'<div class="snapshot-label">{data["label"]}</div>'
            f'<div class="snapshot-price">{data["price"]}</div>'
            f'<div class="snapshot-change" style="color:{color};">{arrow} {data["change"]} ({data["pct_change"]})</div>'
            f'</td>'
        )

    rows = [
        _td(snapshot["nifty"])    + _td(snapshot["sensex"]),
        _td(snapshot["gold"])     + _td(snapshot["silver"]),
        _td(snapshot["usdinr"])   + _td(snapshot["crude"]),
        _td(snapshot["sp500"])    + _td(snapshot["nasdaq"]),
        _td(snapshot["nikkei"])   + _td(snapshot["hangseng"]),
    ]
    table_rows = "\n    ".join(f"<tr>{r}</tr>" for r in rows)

    return f"""
<div class="market-snapshot">
  <div class="snapshot-heading">📈 Market Snapshot</div>
  <table class="snapshot-grid">
    {table_rows}
  </table>
  <div class="snapshot-note">Live prices as of email delivery &nbsp;·&nbsp; Indices/Forex/Crude: Yahoo Finance &nbsp;·&nbsp; Gold/Silver: IBJA</div>
</div>
<div style="padding:18px 24px 20px;background:#fdf5fa;border-bottom:3px solid #f0e4ec;">
  <div style="font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:2.5px;color:#c2127f;margin-bottom:12px;text-align:center;">⚡ Quick Navigation</div>
  <table width="100%" cellpadding="0" cellspacing="0" border="0">
    <tr>
      <td width="25%" style="padding:3px 4px;">
        <a href="#cat-indian-stock-market" style="display:block;text-align:center;padding:8px 4px;background:#ffffff;color:#c2127f;font-size:11px;font-weight:700;border-radius:8px;text-decoration:none;border:1.5px solid #e8b4d8;line-height:1.3;">🇮🇳<br/>Indian Stock<br/>Market</a>
      </td>
      <td width="25%" style="padding:3px 4px;">
        <a href="#cat-global-markets" style="display:block;text-align:center;padding:8px 4px;background:#ffffff;color:#c2127f;font-size:11px;font-weight:700;border-radius:8px;text-decoration:none;border:1.5px solid #e8b4d8;line-height:1.3;">🌐<br/>Global<br/>Markets</a>
      </td>
      <td width="25%" style="padding:3px 4px;">
        <a href="#cat-geopolitics-trade" style="display:block;text-align:center;padding:8px 4px;background:#ffffff;color:#c2127f;font-size:11px;font-weight:700;border-radius:8px;text-decoration:none;border:1.5px solid #e8b4d8;line-height:1.3;">🌍<br/>Geopolitics<br/>&amp; Trade</a>
      </td>
      <td width="25%" style="padding:3px 4px;">
        <a href="#cat-mutual-funds" style="display:block;text-align:center;padding:8px 4px;background:#ffffff;color:#c2127f;font-size:11px;font-weight:700;border-radius:8px;text-decoration:none;border:1.5px solid #e8b4d8;line-height:1.3;">💰<br/>Mutual<br/>Funds</a>
      </td>
    </tr>
    <tr>
      <td width="25%" style="padding:3px 4px;">
        <a href="#cat-nfo-tracker" style="display:block;text-align:center;padding:8px 4px;background:#c2127f;color:#ffffff;font-size:11px;font-weight:700;border-radius:8px;text-decoration:none;border:1.5px solid #c2127f;line-height:1.3;">📋<br/>Live NFO<br/>Tracker</a>
      </td>
      <td width="25%" style="padding:3px 4px;">
        <a href="#cat-commodities-currency" style="display:block;text-align:center;padding:8px 4px;background:#ffffff;color:#c2127f;font-size:11px;font-weight:700;border-radius:8px;text-decoration:none;border:1.5px solid #e8b4d8;line-height:1.3;">🥇<br/>Commodities<br/>&amp; Currency</a>
      </td>
      <td width="25%" style="padding:3px 4px;">
        <a href="#cat-economy-policy" style="display:block;text-align:center;padding:8px 4px;background:#ffffff;color:#c2127f;font-size:11px;font-weight:700;border-radius:8px;text-decoration:none;border:1.5px solid #e8b4d8;line-height:1.3;">🏛️<br/>Economy<br/>&amp; Policy</a>
      </td>
      <td width="25%" style="padding:3px 4px;">
        <a href="#cat-health-insurance" style="display:block;text-align:center;padding:8px 4px;background:#ffffff;color:#c2127f;font-size:11px;font-weight:700;border-radius:8px;text-decoration:none;border:1.5px solid #e8b4d8;line-height:1.3;">🏥<br/>Health &amp;<br/>Insurance</a>
      </td>
    </tr>
    <tr>
      <td colspan="2" style="padding:3px 4px;">
        <a href="#cat-general-news" style="display:block;text-align:center;padding:8px 4px;background:#ffffff;color:#c2127f;font-size:11px;font-weight:700;border-radius:8px;text-decoration:none;border:1.5px solid #e8b4d8;line-height:1.3;">📰 General News</a>
      </td>
      <td colspan="2" style="padding:3px 4px;">
        <a href="#cat-executive-summary" style="display:block;text-align:center;padding:8px 4px;background:#fbe7f3;color:#c2127f;font-size:11px;font-weight:700;border-radius:8px;text-decoration:none;border:1.5px solid #e8b4d8;line-height:1.3;">📌 Executive Summary</a>
      </td>
    </tr>
  </table>
</div>"""


def _category_anchor(category: str) -> str:
    """Returns the anchor name for a given category — must match the nav button href."""
    mapping = {
        "Indian Stock Market":    "cat-indian-stock-market",
        "Global Markets":         "cat-global-markets",
        "Geopolitics & Trade":    "cat-geopolitics-trade",
        "Mutual Funds":           "cat-mutual-funds",
        "Commodities & Currency": "cat-commodities-currency",
        "Economy & Policy":       "cat-economy-policy",
        "Health & Term Insurance":"cat-health-insurance",
        "General News":           "cat-general-news",
    }
    return mapping.get(category, category.lower().replace(" ", "-").replace("&", "and"))


def _build_category_sections(categories: dict[str, str], nfo_list: list[dict]) -> str:
    """Wraps each AI-generated category HTML in a styled block.
    For Mutual Funds, injects the Live NFO Tracker table after the stories.
    Each block has an <a name> anchor so the nav buttons can jump to it.
    """
    sections = []
    for category, html in categories.items():
        anchor = _category_anchor(category)
        extra = ""
        if category == "Mutual Funds" and nfo_list:
            extra = _build_nfo_table(nfo_list)
        section = f"""
<a name="{anchor}"></a>
<div class="category-block">
  <div class="category-label">{category}</div>
  {html}
  {extra}
</div>
"""
        sections.append(section)
    return "\n".join(sections)


def _build_nfo_table(nfo_list: list[dict]) -> str:
    """Builds the Live NFO Tracker table sourced from AMFI (Name, Fund House, Open Date, Close Date)."""
    if not nfo_list:
        return ""

    rows = ""
    for nfo in nfo_list:
        rows += f"""
      <tr>
        <td style="padding:8px 10px;border-bottom:1px solid #f0d9ea;color:#2b2b2b;font-size:12px;line-height:1.4;">{nfo["name"]}</td>
        <td style="padding:8px 10px;border-bottom:1px solid #f0d9ea;color:#3a3a3a;font-size:12px;">{nfo["fund_house"]}</td>
        <td style="padding:8px 10px;border-bottom:1px solid #f0d9ea;color:#3a3a3a;font-size:12px;white-space:nowrap;">{nfo["open_date"]}</td>
        <td style="padding:8px 10px;border-bottom:1px solid #f0d9ea;color:#3a3a3a;font-size:12px;white-space:nowrap;">{nfo["close_date"]}</td>
      </tr>"""

    return f"""
<div class="nfo-table-wrap" style="margin-top:20px;">
  <a name="cat-nfo-tracker"></a>
  <div class="nfo-table-heading" style="font-size:13px;font-weight:700;color:#c2127f;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px;">
    📋 Live NFO Tracker &nbsp;<span style="font-size:10px;font-weight:400;color:#888;text-transform:none;letter-spacing:0;">Source: AMFI India</span>
  </div>
  <table style="width:100%;display:table;border-collapse:collapse;font-size:12px;clear:both;">
    <thead>
      <tr>
        <th style="background:#c2127f;color:#fff;padding:8px 10px;text-align:left;font-weight:700;font-size:11px;letter-spacing:0.5px;">NFO Name</th>
        <th style="background:#c2127f;color:#fff;padding:8px 10px;text-align:left;font-weight:700;font-size:11px;letter-spacing:0.5px;">Fund House</th>
        <th style="background:#c2127f;color:#fff;padding:8px 10px;text-align:left;font-weight:700;font-size:11px;letter-spacing:0.5px;">Open Date</th>
        <th style="background:#c2127f;color:#fff;padding:8px 10px;text-align:left;font-weight:700;font-size:11px;letter-spacing:0.5px;">Close Date</th>
      </tr>
    </thead>
    <tbody>{rows}
    </tbody>
  </table>
  <div style="display:block;width:100%;text-align:center;margin-top:16px;clear:both;">
    <a href="https://www.amfiindia.com/new-fund-offer"
       style="display:inline-block;background:#c2127f;color:#ffffff;font-size:12px;font-weight:700;
              padding:8px 20px;border-radius:20px;text-decoration:none;letter-spacing:0.5px;">
      View All NFOs on AMFI →
    </a>
  </div>
</div>"""


def _build_mint_section(mint_articles: list[dict]) -> str:
    """Builds the General News section with multi-source articles and Explore More links."""
    if not mint_articles:
        return ""

    cards = ""
    for a in mint_articles:
        source = a.get("source", "News")
        cards += f"""
  <div class="story">
    <h4 class="story-title">{a['title']}</h4>
    <div class="story-link-row">
      <a class="story-link" href="{a['link']}">Read article →</a>
      <span class="story-source">{source}</span>
    </div>
  </div>"""

    return f"""
<a name="cat-general-news"></a>
<div class="category-block">
  <div class="category-label">General News</div>
  {cards}
  <div style="text-align:center;margin-top:20px;">
    <a href="https://www.livemint.com/"
       style="display:inline-block;background:#c2127f;color:#ffffff;font-size:12px;font-weight:700;
              padding:8px 18px;border-radius:20px;text-decoration:none;letter-spacing:0.5px;margin:4px;">
      Mint →
    </a>
    <a href="https://economictimes.indiatimes.com/"
       style="display:inline-block;background:#c2127f;color:#ffffff;font-size:12px;font-weight:700;
              padding:8px 18px;border-radius:20px;text-decoration:none;letter-spacing:0.5px;margin:4px;">
      Economic Times →
    </a>
    <a href="https://www.google.com/news"
       style="display:inline-block;background:#c2127f;color:#ffffff;font-size:12px;font-weight:700;
              padding:8px 18px;border-radius:20px;text-decoration:none;letter-spacing:0.5px;margin:4px;">
      Google News →
    </a>
    <div style="font-size:10px;color:#aaaaaa;margin-top:10px;">Top stories from India's leading publications</div>
  </div>
</div>"""


def build_email_html(summarized: dict, snapshot: dict, mint_articles: list[dict], nfo_list: list[dict]) -> str:
    template = _load_template()

    now      = datetime.now()
    date_str = now.strftime("%A, %d %B %Y")
    year_str = str(now.year)

    market_snapshot_html = _build_market_snapshot_html(snapshot)
    category_sections    = _build_category_sections(summarized["categories"], nfo_list)
    mint_section         = _build_mint_section(mint_articles)

    html = (
        template
        .replace("{{DATE}}",              date_str)
        .replace("{{YEAR}}",              year_str)
        .replace("{{LOGO_URL}}",          "https://raw.githubusercontent.com/Sathivika/etica-daily-intelligence/main/templates/assets/etica_logo.png")
        .replace("{{MARKET_SNAPSHOT}}",   market_snapshot_html)
        .replace("{{EXECUTIVE_SUMMARY}}", summarized["executive_summary"])
        .replace("{{CATEGORY_SECTIONS}}", category_sections + mint_section)
    )
    return html


def send_email(html_content: str) -> None:
    sender_email    = os.environ["EMAIL_USER"]
    sender_password = os.environ["EMAIL_PASSWORD"]

    today   = datetime.now().strftime("%d %b %Y")
    subject = f"Etica Daily Intelligence Brief · {today}"

    recipients = [r.strip() for r in RECIPIENTS if r.strip()]
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

        recipients = [r.strip() for r in RECIPIENTS if r.strip()]
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