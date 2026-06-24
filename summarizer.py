"""
summarizer.py - Uses Groq instead of Gemini.
Model: llama-3.3-70b-versatile — fast, accurate, great for financial summaries.
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
        source = a.get("source", "")
        source_str = f"  [{source}]" if source else ""
        lines.append(f"{i}. {a['title']}{source_str}  {a.get('link','')}")
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
  <h3 class="exec-heading">🌐 Opportunities</h3>
  <ul class="exec-list">
    <li>Opportunity 1 — test placeholder</li>
    <li>Opportunity 2 — test placeholder</li>
    <li>Opportunity 3 — test placeholder</li>
  </ul>
</div>
<div class="exec-section">
  <h3 class="exec-heading">⚠️ Risks to Watch</h3>
  <ul class="exec-list">
    <li>Risk 1 — test placeholder</li>
    <li>Risk 2 — test placeholder</li>
    <li>Risk 3 — test placeholder</li>
  </ul>
</div>
<div class="exec-section">
  <h3 class="exec-heading">📊 Market Outlook</h3>
  <p class="exec-outlook">This is a test email. Real market intelligence will appear here when TEST_MODE is set to False.</p>
</div>
<div class="investor-tips">
  <div class="investor-tips-heading">💬 What To Tell Investors</div>
  <ul>
    <li>Test pipeline is running — real talking points will appear in production.</li>
    <li>All systems are functional; set TEST_MODE = False when ready.</li>
  </ul>
</div>
<div class="faq-block">
  <div class="faq-heading">🙋 Common Investor FAQs</div>
  <div class="faq-item">
    <div class="faq-q">Q: Is this a real email?</div>
    <div class="faq-a">A: This is a test run. Real FAQs will appear once TEST_MODE is disabled.</div>
  </div>
</div>
""",
            "categories": {
                cat: f"""
<div class="story">
  <h4 class="story-title">Test Story for {cat}</h4>
  <p class="story-summary">This is a placeholder summary for testing purposes. Real news will appear here in production.</p>
  <p class="story-why"><strong>Why it matters:</strong> This confirms the email pipeline is working end-to-end.</p>
  <div class="story-link-row">
    <a class="story-link" href="#">Read article →</a>
    <span class="story-source">Test Source</span>
  </div>
</div>
<div class="investor-tips">
  <div class="investor-tips-heading">💬 What To Tell Investors</div>
  <ul>
    <li>Test placeholder — real talking points will appear in production.</li>
  </ul>
</div>
""" for cat in all_news.keys()
            }
        }

    # ── PRODUCTION MODE ───────────────────────────────────────────────────

    # Short title-only text for exec summary prompt
    exec_text = ""
    for category, articles in all_news.items():
        exec_text += f"\n\n=== {category} ===\n"
        titles = [a["title"] for a in articles[:5]]
        exec_text += "\n".join(f"- {t}" for t in titles)

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
  <h3 class="exec-heading">🌐 Opportunities</h3>
  <ul class="exec-list">
    <li>Opportunity 1</li>
    <li>Opportunity 2</li>
    <li>Opportunity 3</li>
  </ul>
</div>
<div class="exec-section">
  <h3 class="exec-heading">⚠️ Risks to Watch</h3>
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
<div class="investor-tips">
  <div class="investor-tips-heading">💬 What To Tell Investors</div>
  <ul>
    <li>Specific, actionable talking point a wealth manager can say to a client today — drawn from the news above.</li>
    <li>Talking point 2</li>
    <li>Talking point 3</li>
    <li>Talking point 4</li>
    <li>Talking point 5</li>
  </ul>
</div>
<div class="faq-block">
  <div class="faq-heading">🙋 Common Investor FAQs</div>
  <div class="faq-item">
    <div class="faq-q">Q: [Question an investor is likely to ask their advisor today, based on the news]</div>
    <div class="faq-a">A: [Clear, reassuring, factual answer a wealth manager would give]</div>
  </div>
  <div class="faq-item">
    <div class="faq-q">Q: [Second likely investor question]</div>
    <div class="faq-a">A: [Answer]</div>
  </div>
  <div class="faq-item">
    <div class="faq-q">Q: [Third likely investor question]</div>
    <div class="faq-a">A: [Answer]</div>
  </div>
</div>

Rules:
- "What To Tell Investors" bullets must be ready-to-use phrases a relationship manager can speak to a client, synthesised across ALL categories.
- FAQs must reflect questions real investors ask based on today's specific headlines — not generic questions.
- Return ONLY the HTML above. Be specific and data-aware. No markdown, no code fences."""

    logger.info("Calling Groq (1/N): Executive summary...")
    executive_summary = _call_groq(exec_prompt)

    time.sleep(20)

    # ── CALLS 2+: Categories in batches of 2 ─────────────────────────────
    category_names = list(all_news.keys())
    batch_size = 2
    batches = [category_names[i:i + batch_size] for i in range(0, len(category_names), batch_size)]

    def _articles_per_category(cat: str) -> int:
        """Different categories get different article counts."""
        counts = {
            "Indian Stock Market":     2,
            "Global Markets":          3,
            "Geopolitics & Trade":     3,
            "Mutual Funds":            4,  # extra for NFO tracker
            "Commodities & Currency":  4,
            "Economy & Policy":        3,
            "Health & Term Insurance": 4,
        }
        return counts.get(cat, 3)

    def _build_categories_text(cats: list[str]) -> str:
        text = ""
        for category in cats:
            articles = all_news[category]
            n = _articles_per_category(category)
            text += f"\n\n=== {category} ===\n"
            text += _articles_text(articles[:n])
        return text

    def _build_categories_prompt(cats: list[str]) -> str:
        cats_text = _build_categories_text(cats)

        # Check if Mutual Funds is in this batch — if so, add NFO table instructions
        mf_instructions = ""
        if "Mutual Funds" in cats:
            mf_instructions = """
SPECIAL RULE for "Mutual Funds" category:
After the story divs, add an NFO Tracker table if any NFO is mentioned in the articles.
Use EXACTLY this structure (if no NFO found, omit this block entirely):

<div class="nfo-table-wrap">
  <div class="nfo-table-heading">📋 NFO Tracker</div>
  <table class="nfo-table">
    <thead>
      <tr>
        <th>NFO Name</th>
        <th>Fund House</th>
        <th>Open Date</th>
        <th>Close Date</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td>NFO name here</td>
        <td>Fund house here</td>
        <td>Open date or "—" if unknown</td>
        <td>Close date or "—" if unknown</td>
      </tr>
    </tbody>
  </table>
</div>
"""

        # Check if Indian Stock Market is in this batch — 2 specific articles
        ism_instructions = ""
        if "Indian Stock Market" in cats:
            ism_instructions = """
SPECIAL RULE for "Indian Stock Market" category:
Pick exactly 2 articles:
  1. A broad market/index overview story (Nifty/Sensex performance, breadth, FII/DII activity)
  2. A sector-specific or stock-specific story
"""

        # Check if Global Markets is in this batch — 3 specific articles
        gm_instructions = ""
        if "Global Markets" in cats:
            gm_instructions = """
SPECIAL RULE for "Global Markets" category:
Pick exactly 3 articles:
  1. A US-markets specific story (Fed, S&P, Nasdaq, Dow)
  2. How global developments are impacting India specifically
  3. Any other significant global market development affecting Indian investors
"""

        # Check if Commodities & Currency is in this batch
        cc_instructions = ""
        if "Commodities & Currency" in cats:
            cc_instructions = """
SPECIAL RULE for "Commodities & Currency" category:
Pick exactly 3–4 articles covering:
  1. Gold price update
  2. Crude oil update
  3. Silver or other commodity
  4. INR/USD or broader currency/forex update
"""

        # Check if Economy & Policy is in this batch
        ep_instructions = ""
        if "Economy & Policy" in cats:
            ep_instructions = """
SPECIAL RULE for "Economy & Policy" category:
Pick exactly 3 articles covering:
  1. RBI Watch — anything on rates, liquidity, monetary policy
  2. India economy mood — GDP, inflation, fiscal data
  3. Global or private investor view of India (FDI, sovereign ratings, investor sentiment)
"""

        # Check if Health & Term Insurance is in this batch
        hi_instructions = ""
        if "Health & Term Insurance" in cats:
            hi_instructions = """
SPECIAL RULE for "Health & Term Insurance" category:
Pick exactly 3–4 articles covering:
  1. Health insurance news (new plans, IRDAI regulations, claim settlement, premium changes)
  2. Term insurance news (new products, coverage trends, mortality charges, rider updates)
  3. Any broader insurance sector development relevant to Indian retail investors
Why it matters should address how the development affects a policyholder or someone considering buying cover.
"""

        special_rules = mf_instructions + ism_instructions + gm_instructions + cc_instructions + ep_instructions + hi_instructions

        return f"""You are a senior financial analyst for Etica, a wealth management firm in India.

Below are news articles grouped by category. For EACH category, pick the most important stories and return HTML.

{cats_text}

For EACH category, use EXACTLY this HTML structure:

<div class="category-stories" data-category="EXACT CATEGORY NAME">
  <div class="story">
    <h4 class="story-title">Exact headline from the article</h4>
    <p class="story-summary">2-sentence factual summary. Do NOT repeat words from the headline in the first sentence.</p>
    <p class="story-why"><strong>Why it matters:</strong> 1 sentence on relevance to Indian investors.</p>
    <div class="story-link-row">
      <a class="story-link" href="ACTUAL_URL_FROM_ARTICLE">Read article →</a>
      <span class="story-source">Source Name Here</span>
    </div>
  </div>
</div>

After the story divs (but still inside the category-stories div), add a "What To Tell Investors" block:

  <div class="investor-tips">
    <div class="investor-tips-heading">💬 What To Tell Investors</div>
    <ul>
      <li>Specific, ready-to-use phrase a relationship manager can say to a client about this category today.</li>
      <li>Talking point 2</li>
      <li>Talking point 3</li>
    </ul>
  </div>

{special_rules}

Rules:
- "story-source" must be the actual source name from the article list (e.g. "Economic Times", "Mint", "Reuters").
- story-summary must NOT repeat the headline's key nouns/verbs in the opening phrase — rephrase to add context.
- "What To Tell Investors" bullets must be conversational, reassuring, and specific to today's news in this category.
- Generate one <div class="category-stories"> block for EVERY category listed above.
- Return ONLY HTML. No markdown. No code fences. No extra text."""

    categories_html_parts = []
    for idx, batch in enumerate(batches, 1):
        logger.info(f"Calling Groq ({idx+1}/{len(batches)+1}): Categories batch {idx} ({', '.join(batch)})...")
        html_part = _call_groq(_build_categories_prompt(batch))
        categories_html_parts.append(html_part)
        if idx < len(batches):
            time.sleep(20)

    categories_html = "\n".join(categories_html_parts)

    # ── Parse response into per-category dict ────────────────────────────
    categories_dict = {}
    pattern = r'<div class="category-stories" data-category="([^"]+)">(.*?)</div>\s*(?=<div class="category-stories"|$)'
    matches = re.findall(pattern, categories_html, re.DOTALL)

    if matches:
        for cat_name, stories_html in matches:
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