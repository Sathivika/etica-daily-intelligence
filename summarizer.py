"""
summarizer.py - Single Gemini call version to avoid free tier rate limits.
Sends ALL categories in one prompt and gets back the full HTML report.
"""

import os
import logging
import time
import google.generativeai as genai

logger = logging.getLogger(__name__)

genai.configure(api_key=os.environ["GEMINI_API_KEY"])
_model = genai.GenerativeModel("gemini-1.5-flash-8b")


def _articles_text(articles: list[dict]) -> str:
    lines = []
    for i, a in enumerate(articles, 1):
        lines.append(f"{i}. {a['title']}  [{a.get('source','')}]  {a.get('link','')}")
    return "\n".join(lines)


def summarize_all(all_news: dict[str, list[dict]]) -> dict:
    """
    Makes just 2 Gemini API calls total:
      1. Executive summary
      2. All category summaries in one single call
    """

    # ── Build one big prompt with ALL categories ──────────────────────────
    all_categories_text = ""
    for category, articles in all_news.items():
        all_categories_text += f"\n\n=== {category} ===\n"
        all_categories_text += _articles_text(articles[:10])  # top 10 per category

    # ── CALL 1: Executive Summary ─────────────────────────────────────────
    exec_prompt = f"""You are a chief market strategist for Etica, a wealth management firm in India.

Here are today's top headlines across all categories:
{all_categories_text}

Generate a concise executive intelligence brief in HTML using EXACTLY this structure:

<div class="exec-section">
  <h3 class="exec-heading">📌 Today's Key Takeaways</h3>
  <ul class="exec-list">
    <li>Insight 1</li>
    <li>Insight 2</li>
    <li>Insight 3</li>
    <li>Insight 4</li>
    <li>Insight 5</li>
  </ul>
</div>
<div class="exec-section">
  <h3 class="exec-heading">🟢 Opportunities</h3>
  <ul class="exec-list">
    <li>Opportunity 1</li>
    <li>Opportunity 2</li>
    <li>Opportunity 3</li>
  </ul>
</div>
<div class="exec-section">
  <h3 class="exec-heading">🔴 Risks to Watch</h3>
  <ul class="exec-list">
    <li>Risk 1</li>
    <li>Risk 2</li>
    <li>Risk 3</li>
  </ul>
</div>
<div class="exec-section">
  <h3 class="exec-heading">📊 Market Outlook</h3>
  <p class="exec-outlook">2-3 sentence market outlook here.</p>
</div>

Return ONLY the HTML above. No markdown. No code fences. Be specific."""

    logger.info("Calling Gemini (1/2): Executive summary...")
    exec_response = _model.generate_content(exec_prompt)
    executive_summary = exec_response.text.strip()

    # Wait 10 seconds between calls to respect rate limits
    logger.info("Waiting 10s before next Gemini call...")
    time.sleep(10)

    # ── CALL 2: All Categories in ONE prompt ──────────────────────────────
    categories_prompt = f"""You are a senior financial analyst for Etica, a wealth management firm in India.

Below are news articles grouped by category. For EACH category, pick the 3 most important stories and return HTML.

{all_categories_text}

For each category, use EXACTLY this structure:

<div class="category-stories" data-category="CATEGORY NAME HERE">
  <div class="story">
    <h4 class="story-title">Headline here</h4>
    <p class="story-summary">2-sentence summary.</p>
    <p class="story-why"><strong>Why it matters:</strong> 1 sentence.</p>
    <a class="story-link" href="ACTUAL_ARTICLE_URL">Read article →</a>
  </div>
  <div class="story">...</div>
  <div class="story">...</div>
</div>

Generate one <div class="category-stories"> block for EVERY category listed above.
Return ONLY the HTML. No markdown. No code fences. No extra text."""

    logger.info("Calling Gemini (2/2): All category summaries...")
    cat_response = _model.generate_content(categories_prompt)
    categories_html = cat_response.text.strip()

    # ── Parse the single response into per-category dict ─────────────────
    import re
    categories_dict = {}

    # Split by data-category attribute
    pattern = r'<div class="category-stories" data-category="([^"]+)">(.*?)</div>\s*(?=<div class="category-stories"|$)'
    matches = re.findall(pattern, categories_html, re.DOTALL)

    if matches:
        for cat_name, stories_html in matches:
            categories_dict[cat_name] = stories_html.strip()
    else:
        # Fallback: if parsing fails, put everything under one key
        logger.warning("Could not parse categories individually, using full response")
        for category in all_news.keys():
            categories_dict[category] = categories_html

    # Fill in any missing categories with a placeholder
    for category in all_news.keys():
        if category not in categories_dict:
            categories_dict[category] = '<p style="color:#888">No stories available for this category today.</p>'

    logger.info("Gemini summarization complete.")
    return {
        "executive_summary": executive_summary,
        "categories": categories_dict
    }