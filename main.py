"""
main.py
Etica Daily Intelligence — Master Orchestrator

Flow:
  1. Fetch news from RSS (all categories) + General news + Live NFO + Word of the Day
  2. Summarize each category + executive summary via Groq
  3. Fetch market snapshot (indices, forex, commodities)
  4. Build HTML email
  5. Send to recipients

On any failure → send failure notification email.
"""

import logging
import sys
import traceback

from news_fetcher import fetch_all_news, fetch_market_snapshot, fetch_general_news, fetch_live_nfo, fetch_word_of_the_day
from summarizer   import summarize_all
from email_sender import build_email_html, send_email, send_failure_notification

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
    logger.info("[1/5] Fetching news, NFOs and Word of the Day...")
    all_news      = fetch_all_news()
    mint_articles = fetch_general_news()
    nfo_list      = fetch_live_nfo()
    wotd          = fetch_word_of_the_day()

    # ── Step 2: Summarize with Groq ───────────────────────────
    logger.info("[2/5] Generating intelligence with Groq...")
    summarized = summarize_all(all_news)

    # ── Step 3: Fetch Market Snapshot ─────────────────────────
    logger.info("[3/5] Fetching live market snapshot...")
    snapshot = fetch_market_snapshot()

    # ── Step 4: Build HTML ────────────────────────────────────
    logger.info("[4/5] Assembling HTML email...")
    html = build_email_html(summarized, snapshot, mint_articles, nfo_list, wotd)

    # ── Step 5: Send Email ────────────────────────────────────
    logger.info("[5/5] Sending email...")
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