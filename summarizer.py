"""
summarizer.py
Sends collected news articles to Gemini and gets:
  1. Per-category HTML intelligence (top 5 stories with summaries)
  2. One executive summary block for senior management
"""

import os
import logging
import google.generativeai as genai

logger = logging.getLogger(__name__)

# Configure Gemini once at import time
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
_model = genai.GenerativeModel("gemini-2.0-flash")


# ── helpers ──────────────────────────────────────────────────────────────────

def _articles_text(articles: list[dict]) -> str:
    lines = []
    for i, a in enumerate(articles, 1):
        lines.append(f"{i}. {a['title']}  [{a.get('source','')}]")
    return "\n".join(lines)


def _call_gemini(prompt: str) -> str:
    response = _model.generate_content(prompt)
    return response.text.strip()


# ── public API ────────────────────────────────────────────────────────────────

def summarize_category(category: str, articles: list[dict]) -> str:
    """
    Returns an HTML snippet covering the top 5 stories for this category.
    """
    articles_text = _articles_text(articles)

    prompt = f"""You are a senior financial analyst writing for wealth management professionals in India.

Category: {category}

Today's articles:
{articles_text}

Instructions:
- Select the 5 most important and distinct stories from the list above.
- For each story, return ONLY HTML (no markdown, no code fences).
- Use exactly this structure for each story:

<div class="story">
  <h4 class="story-title">HEADLINE HERE</h4>
  <p class="story-summary">2-sentence summary in simple, factual language.</p>
  <p class="story-why"><strong>Why it matters:</strong> 1 sentence on relevance to Indian investors or Etica's clients.</p>
  <a class="story-link" href="ARTICLE_LINK_HERE">Read article →</a>
</div>

Use the actual article link from the list where available. Keep language professional and concise.
Return ONLY the 5 <div class="story"> blocks, nothing else."""

    logger.info(f"  Summarizing category: {category}")
    return _call_gemini(prompt)


def generate_executive_summary(all_news: dict[str, list[dict]]) -> str:
    """
    Returns an HTML executive summary block for senior management.
    """
    # Build a condensed overview of all categories
    overview_lines = []
    for cat, articles in all_news.items():
        headlines = " | ".join(a["title"] for a in articles[:5])
        overview_lines.append(f"{cat}: {headlines}")
    overview = "\n".join(overview_lines)

    prompt = f"""You are a chief market strategist preparing a morning briefing for the leadership of Etica, a wealth management firm in India.

Today's headlines across all categories:
{overview}

Generate a concise executive intelligence brief in HTML. Use exactly this structure:

<div class="exec-section">
  <h3 class="exec-heading">📌 Today's Key Takeaways</h3>
  <ul class="exec-list">
    <li>...</li>
    <li>...</li>
    <li>...</li>
    <li>...</li>
    <li>...</li>
  </ul>
</div>

<div class="exec-section">
  <h3 class="exec-heading">🟢 Opportunities</h3>
  <ul class="exec-list">
    <li>...</li>
    <li>...</li>
    <li>...</li>
  </ul>
</div>

<div class="exec-section">
  <h3 class="exec-heading">🔴 Risks to Watch</h3>
  <ul class="exec-list">
    <li>...</li>
    <li>...</li>
    <li>...</li>
  </ul>
</div>

<div class="exec-section">
  <h3 class="exec-heading">📊 Market Outlook</h3>
  <p class="exec-outlook">2–3 sentences on the overall market tone for today.</p>
</div>

Return ONLY the HTML blocks above. No markdown. No code fences. Be specific and data-aware."""

    logger.info("Generating executive summary...")
    return _call_gemini(prompt)


def summarize_all(all_news: dict[str, list[dict]]) -> dict:
    """
    Master function called by main.py.
    Returns:
      {
        "executive_summary": "<html>...",
        "categories": {
          "Indian Stock Market": "<html>...",
          ...
        }
      }
    """
    results = {"executive_summary": "", "categories": {}}

    # Executive summary first
    results["executive_summary"] = generate_executive_summary(all_news)

    # Per-category summaries
    for category, articles in all_news.items():
        if not articles:
            logger.warning(f"No articles for {category}, skipping.")
            continue
        results["categories"][category] = summarize_category(category, articles)

    return results
