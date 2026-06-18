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

# ── Recipients (add/remove as needed) ────────────────────────────────────────
RECIPIENTS = [
    os.environ.get("RECIPIENT_1", ""),
    os.environ.get("RECIPIENT_2", ""),
    # Add more via GitHub Secrets: RECIPIENT_3, etc.
]


def _load_template() -> str:
    template_path = Path(__file__).parent / "templates" / "report.html"
    return template_path.read_text(encoding="utf-8")


def _build_category_sections(categories: dict[str, str]) -> str:
    """Wraps each Gemini-generated category HTML in a styled block."""
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


def build_email_html(summarized: dict) -> str:
    template = _load_template()

    now = datetime.now()
    date_str = now.strftime("%A, %d %B %Y")
    year_str = str(now.year)

    category_sections = _build_category_sections(summarized["categories"])

    html = (
        template
        .replace("{{DATE}}", date_str)
        .replace("{{YEAR}}", year_str)
        .replace("{{EXECUTIVE_SUMMARY}}", summarized["executive_summary"])
        .replace("{{CATEGORY_SECTIONS}}", category_sections)
    )
    return html


def send_email(html_content: str) -> None:
    sender_email    = os.environ["EMAIL_USER"]
    sender_password = os.environ["EMAIL_PASSWORD"]

    today = datetime.now().strftime("%d %b %Y")
    subject = f"Etica Daily Intelligence Brief · {today}"

    recipients = [r for r in RECIPIENTS if r]  # remove empty strings
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
    """Send a plain-text failure alert so the team knows automation broke."""
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
https://github.com/YOUR_ORG/etica-daily-intelligence/actions

— Automated Alert
"""
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, recipients, msg.as_string())

        logger.info("Failure notification sent.")
    except Exception as e:
        logger.error(f"Could not send failure notification: {e}")
