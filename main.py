"""
main.py
Etica Daily Intelligence — Master Orchestrator

Flow:
  1. Fetch news from RSS (all 7 categories)
  2. Summarize each category + executive summary via Gemini
  3. Build HTML email
  4. Send to recipients

On any failure → send failure notification email.
"""

import logging
import sys
import traceback

from news_fetcher import fetch_all_news, fetch_market_snapshot
from summarizer   import summarize_all
from email_sender import build_email_html, send_email, send_failure_notification

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def main():
    logger.info("=" * 55)
    logger.info("  Etica Daily Intelligence — Starting")
    logger.info("=" * 55)

    # ── Step 1: Fetch News ────────────────────────────────────
    logger.info("[1/4] Fetching news from RSS feeds...")
    all_news = fetch_all_news()

    # ── Step 2: Summarize with Gemini ─────────────────────────
    logger.info("[2/4] Generating intelligence with Gemini...")
    summarized = summarize_all(all_news)

    # ── Step 3: Build HTML ────────────────────────────────────
    logger.info("[3/4] Assembling HTML email...")
    snapshot = fetch_market_snapshot()
    html = build_email_html(summarized, snapshot)

    # ── Step 4: Send Email ────────────────────────────────────
    logger.info("[4/4] Sending email...")
    send_email(html)

    logger.info("=" * 55)
    logger.info("  Done. Have a great day!")
    logger.info("=" * 55)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        err = traceback.format_exc()
        logger.error(f"FATAL ERROR:\n{err}")
        send_failure_notification(err)
        sys.exit(1)
