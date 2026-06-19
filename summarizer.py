"""
summarizer.py - Uses Groq (free, no billing required) instead of Gemini.
Model: llama3-70b-8192 — fast, accurate, great for financial summaries.
"""

import os
import re
import time
import logging
from groq import Groq

logger = logging.getLogger(__name__)

client = Groq(api_key=os.environ["GROQ_API_KEY"])
MODEL = "llama-3.3-70b-versatile"

# ── SET TO True TO TEST EMAIL PIPELINE WITHOUT USING GROQ API ────────────────
TEST_MODE = False


def _call_groq(prompt: str) -> str:
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=4000,
        temperature=0.3,
    )
    return response.choices[0].message.content.strip()


def _articles_text(articles: list[dict]) -> str:
    lines = []
    for i, a in enumerate(articles, 1):
        lines.append(f"{i}. {a['title']}  [{a.get('source','')}]  {a.get('link','')}")
    return "\n".join(lines)


def summarize_all(all_news: dict[str, list[dict]]) -> dict:

    # ── TEST MODE ─────────────────────────────────────────────────────────
    if TEST_MODE:
        logger.info("TEST MODE enabled — skipping Groq, using dummy data.")
        return {
            "executive_summary": """
<div class="exec-section">
  <h3 class="exec-heading">📌 Today's Key Takeaways</h3>
  <ul class="exec-list">
    <li>This is a TEST RUN of the Etica Daily Intelligence pipeline.</li>
    <li>Groq AI was not called — dummy data is being used.</li>
    <li>If you received this email, the pipeline is working correctly.</li>
    <li>Email assembly, SMTP delivery, and GitHub Actions are all functional.</li>
    <li>Set TEST_MODE = False to enable real AI summaries.</li>
  </ul>
</div>
<div class="exec-section">
  <h3 class="exec-heading">📊 Market Outlook</h3>
  <p class="exec-outlook">This is a test email. Real market intelligence will appear here when TEST_MODE is set to False.</p>
</div>
""",
            "categories": {
                cat: f"""
<div class="story">
  <h4 class="story-title">Test Story for {cat}</h4>
  <p class="story-summary">This is a placeholder summary for testing purposes. Real news will appear here in production.</p>
  <p class="story-why"><strong>Why it matters:</strong> This confirms the email pipeline is working end-to-end.</p>
  <a class="story-link" href="#">Read article →</a>
</div>
""" for cat in all_news.keys()
            }
        }

    # ── PRODUCTION MODE ───────────────────────────────────────────────────
    # Short version (titles only, no links) for the executive summary call
    exec_text = ""
    for category, articles in all_news.items():
        exec_text += f"\n\n=== {category} ===\n"
        titles = [a["title"] for a in articles[:5]]
        exec_text += "\n".join(f"- {t}" for t in titles)

    # Fuller version (titles + links) for the category story call, fewer articles
    all_categories_text = ""
    for category, articles in all_news.items():
        all_categories_text += f"\n\n=== {category} ===\n"
        all_categories_text += _articles_text(articles[:4])

    # ── CALL 1: Executive Summary ─────────────────────────────────────────
    exec_prompt = f"""You are a chief market strategist for Etica, a wealth management firm in India.

Here are today's top headlines across all categories:
{exec_text}

Generate a concise executive intelligence brief in HTML using EXACTLY this structure (no markdown, no code fences, only HTML):

<div class="exec-section">
  <h3 class="exec-heading">📌 Today's Key Takeaways</h3>
  <ul class="exec-list">
    <li>Specific insight 1</li>
    <li>Specific insight 2</li>
    <li>Specific insight 3</li>
    <li>Specific insight 4</li>
    <li>Specific insight 5</li>
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
  <p class="exec-outlook">2-3 sentence market outlook for Indian investors today.</p>
</div>

Return ONLY the HTML above. Be specific and data-aware."""

    logger.info("Calling Groq (1/2): Executive summary...")
    executive_summary = _call_groq(exec_prompt)

    time.sleep(20)

    # ── CALL 2: All Categories ────────────────────────────────────────────
    categories_prompt = f"""You are a senior financial analyst for Etica, a wealth management firm in India.

Below are news articles grouped by category. For EACH category, pick the 3 most important stories and return HTML.

{all_categories_text}

For EACH category, use EXACTLY this HTML structure:

<div class="category-stories" data-category="EXACT CATEGORY NAME">
  <div class="story">
    <h4 class="story-title">Exact headline from the article</h4>
    <p class="story-summary">2-sentence factual summary of the story.</p>
    <p class="story-why"><strong>Why it matters:</strong> 1 sentence on relevance to Indian investors.</p>
    <a class="story-link" href="ACTUAL_URL_FROM_ARTICLE">Read article →</a>
  </div>
  <div class="story">...</div>
  <div class="story">...</div>
</div>

Generate one <div class="category-stories"> block for EVERY category.
Return ONLY HTML. No markdown. No code fences. No extra text."""

    logger.info("Calling Groq (2/2): All category summaries...")
    categories_html = _call_groq(categories_prompt)

    # ── Parse response into per-category dict ────────────────────────────
    categories_dict = {}
    pattern = r'<div class="category-stories" data-category="([^"]+)">(.*?)</div>\s*(?=<div class="category-stories"|$)'
    matches = re.findall(pattern, categories_html, re.DOTALL)

    if matches:
        for cat_name, stories_html in matches:
            # Match against known categories (case-insensitive)
            for known_cat in all_news.keys():
                if known_cat.lower() in cat_name.lower() or cat_name.lower() in known_cat.lower():
                    categories_dict[known_cat] = stories_html.strip()
                    break
    else:
        logger.warning("Could not parse categories, using full response as fallback")
        for category in all_news.keys():
            categories_dict[category] = categories_html

    for category in all_news.keys():
        if category not in categories_dict:
            categories_dict[category] = '<p style="color:#888">No stories available for this category today.</p>'

    logger.info("Groq summarization complete.")
    return {
        "executive_summary": executive_summary,
        "categories": categories_dict
    }