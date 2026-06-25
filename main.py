"""
main.py
Etica Daily Intelligence — Master Orchestrator

Flow:
  1. Fetch news from RSS (all categories) + Mint general news
  2. Summarize each category + executive summary via Groq
  3. Fetch live NFOs from Groww + inject into Mutual Funds section
  4. Fetch market snapshot (indices, forex, commodities)
  5. Build HTML email
  6. Send to recipients

On any failure → send failure notification email.
"""

import logging
import sys
import traceback

from news_fetcher import fetch_all_news, fetch_market_snapshot, fetch_mint_news, fetch_live_nfos
from summarizer   import summarize_all, inject_nfo_table
from email_sender import build_email_html, send_email, send_failure_notification

# ── Logging ───────────────────────────────────────────────────────────────────
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
    logger.info("[1/6] Fetching news from RSS feeds...")
    all_news      = fetch_all_news()
    mint_articles = fetch_mint_news()

    # ── Step 2: Summarize with Groq ───────────────────────────
    logger.info("[2/6] Generating intelligence with Groq...")
    summarized = summarize_all(all_news)

    # ── Step 3: Fetch Live NFOs from Groww ───────────────────
    logger.info("[3/6] Fetching live NFOs from Groww...")
    nfos = fetch_live_nfos()
    summarized = inject_nfo_table(summarized, nfos)

    # ── Step 4: Fetch Market Snapshot ─────────────────────────
    logger.info("[4/6] Fetching live market snapshot...")
    snapshot = fetch_market_snapshot()

    # ── Step 5: Build HTML ────────────────────────────────────
    logger.info("[5/6] Assembling HTML email...")
    html = build_email_html(summarized, snapshot, mint_articles)

    # ── Step 6: Send Email ────────────────────────────────────
    logger.info("[6/6] Sending email...")
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