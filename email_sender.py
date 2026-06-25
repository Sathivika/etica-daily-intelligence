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
def _load_recipients() -> list[str]:
    """
    Auto-scans RECIPIENT_1, RECIPIENT_2, ... RECIPIENT_N from environment.
    Add a new RECIPIENT_N secret in GitHub + YAML to include more people.
    """
    recipients = []
    i = 1
    while True:
        val = os.environ.get(f"RECIPIENT_{i}", "").strip()
        if not val:
            break
        recipients.append(val)
        i += 1
    return recipients

RECIPIENTS = _load_recipients()


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


def _summarize_general_news(articles: list[dict]) -> str:
    """
    Calls Groq to generate story cards for General News with the same
    HTML structure (summary + why it matters) as all other categories.
    Falls back to title-only cards on failure.
    """
    import os
    from groq import Groq

    try:
        client = Groq(api_key=os.environ["GROQ_API_KEY"])
        articles_text = "\n".join(
            f"{i+1}. {a['title']}  [{a['source']}]  {a['link']}"
            for i, a in enumerate(articles)
        )
        prompt = f"""You are a senior analyst for Etica, a wealth management firm in India.

Here are today's top general news headlines:
{articles_text}

For EACH article, return a story card using EXACTLY this HTML structure:

<div class="story">
  <h4 class="story-title">Exact headline</h4>
  <p class="story-summary">2-sentence factual summary. Do NOT repeat the headline key words in the first sentence.</p>
  <p class="story-why"><strong>Why it matters:</strong> 1 sentence on why this is relevant to an Indian reader or investor.</p>
  <div class="story-link-row">
    <a class="story-link" href="ACTUAL_URL">Read article →</a>
    <span class="story-source">Source name</span>
  </div>
</div>

Rules:
- Return ONLY the story div blocks. No wrapper divs, no markdown, no code fences.
- story-source must match the source name from the article list."""

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1500,
            temperature=0.3,
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        logger.warning(f"Groq summarization for General News failed: {e}. Falling back to title-only cards.")
        fallback = ""
        for a in articles:
            fallback += f"""
  <div class="story">
    <h4 class="story-title">{a['title']}</h4>
    <div class="story-link-row">
      <a class="story-link" href="{a['link']}">Read article →</a>
      <span class="story-source">{a['source']}</span>
    </div>
  </div>"""
        return fallback


def _build_mint_section(mint_articles: list[dict]) -> str:
    """Builds the General News section — summarized by Groq to match all other category cards."""
    if not mint_articles:
        return ""

    cards = _summarize_general_news(mint_articles)

    return f"""
<div class="category-block">
  <div class="category-label">General News</div>
  {cards}
  <div style="text-align:center;margin-top:20px;">
    <a href="https://news.google.com/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRFZxYUdjU0FtVnVHZ0pKVGlnQVAB?hl=en-IN&gl=IN&ceid=IN%3Aen"
       style="display:inline-block;background:#c2127f;color:#ffffff;font-size:13px;font-weight:700;
              padding:10px 28px;border-radius:24px;text-decoration:none;letter-spacing:0.5px;">
      Explore More →
    </a>
    <div style="font-size:10px;color:#aaaaaa;margin-top:8px;">Top stories from Indian news sources</div>
  </div>
</div>"""


def build_email_html(summarized: dict, snapshot: dict, mint_articles: list[dict]) -> str:
    template = _load_template()

    now      = datetime.now()
    date_str = now.strftime("%A, %d %B %Y")
    year_str = str(now.year)

    market_snapshot_html = _build_market_snapshot_html(snapshot)
    category_sections    = _build_category_sections(summarized["categories"])
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

    recipients = _load_recipients()
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

        recipients = _load_recipients()
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