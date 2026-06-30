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


def _call_groq(prompt: str, max_tokens: int = 2000) -> str:
    """Call Groq with retry on 429 TPM errors using exponential backoff."""
    wait_times = [30, 60, 90]  # seconds to wait on successive 429s
    last_err = None
    for attempt, wait in enumerate([0] + wait_times):
        if wait:
            logger.info(f"  Groq TPM limit hit — waiting {wait}s before retry {attempt}...")
            time.sleep(wait)
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=0.3,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            if "429" in str(e) or "rate_limit" in str(e).lower():
                last_err = e
                continue
            raise
    raise last_err


def _rebuild_story_html(raw_html: str) -> str:
    """
    GUARANTEED LAYOUT FIX: Instead of trusting Groq's raw HTML structure
    (which can drift into side-by-side columns under load/retries), this
    extracts the actual content (title, summary, why-it-matters, link,
    source) via regex and re-emits clean, guaranteed-correct vertical
    <div class="story"> blocks using our own template — ignoring whatever
    wrapper/layout Groq may have generated around them.
    Falls back to the sanitized raw HTML if no stories can be extracted.
    """
    story_pattern = re.compile(
        r'<h4[^>]*class="story-title"[^>]*>(.*?)</h4>\s*'
        r'(?:<p[^>]*class="story-summary"[^>]*>(.*?)</p>\s*)?'
        r'(?:<p[^>]*class="story-why"[^>]*>(.*?)</p>\s*)?'
        r'.*?'
        r'<a[^>]*class="story-link"[^>]*href="([^"]*)"[^>]*>.*?</a>\s*'
        r'(?:<span[^>]*class="story-source"[^>]*>(.*?)</span>)?',
        re.DOTALL
    )

    matches = story_pattern.findall(raw_html)
    if not matches:
        # Fallback: strip inline styles and return as-is
        cleaned = re.sub(r'\s+style="[^"]*"', '', raw_html)
        cleaned = re.sub(r"\s+style='[^']*'", '', cleaned)
        return cleaned

    rebuilt = []
    for title, summary, why, link, source in matches:
        title   = title.strip()
        summary = summary.strip()
        why     = why.strip()
        link    = link.strip() or "#"
        source  = source.strip() or "Source"

        why_text = re.sub(r'</?strong>', '', why).replace("Why it matters:", "").strip()
        why_html = f'<p class="story-why"><strong>Why it matters:</strong> {why_text}</p>' if why_text else ""
        summary_html = f'<p class="story-summary">{summary}</p>' if summary else ""

        rebuilt.append(f'''<div class="story">
    <h4 class="story-title">{title}</h4>
    {summary_html}
    {why_html}
    <div class="story-link-row">
      <a class="story-link" href="{link}">Read article →</a>
      <span class="story-source">{source}</span>
    </div>
  </div>''')

    return "\n  ".join(rebuilt)


def _extract_investor_tips(raw_html: str) -> str:
    """Extracts the 'What To Tell Investors' block content and re-emits it cleanly."""
    m = re.search(
        r'<div[^>]*class="investor-tips"[^>]*>.*?<ul[^>]*>(.*?)</ul>.*?</div>',
        raw_html, re.DOTALL
    )
    if not m:
        return ""
    items_html = m.group(1)
    items = re.findall(r'<li[^>]*>(.*?)</li>', items_html, re.DOTALL)
    items = [i.strip() for i in items if i.strip()]
    if not items:
        return ""
    li_html = "\n      ".join(f"<li>{i}</li>" for i in items)
    return f'''<div class="investor-tips">
    <div class="investor-tips-heading">💬 What To Tell Investors</div>
    <ul>
      {li_html}
    </ul>
  </div>'''


def _sanitize_category_html(html: str) -> str:
    """
    GUARANTEED LAYOUT FIX: Rebuilds each category's HTML from scratch using
    only the actual content Groq generated (titles, summaries, links, tips),
    discarding any wrapper structure that could cause side-by-side/column
    rendering. This guarantees every story stacks vertically regardless of
    what HTML structure Groq actually returned.
    """
    stories_html = _rebuild_story_html(html)
    tips_html    = _extract_investor_tips(html)

    if tips_html:
        return f"{stories_html}\n  {tips_html}"
    return stories_html


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
    executive_summary = _call_groq(exec_prompt, max_tokens=1500)

    time.sleep(45)  # wait after exec summary before starting category calls

    # ── CALLS 2+: Categories one at a time to stay under 12k TPM ────────
    category_names = list(all_news.keys())
    batch_size = 1  # one category per call — keeps each request well under TPM limit
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

        # Check if Mutual Funds is in this batch
        mf_instructions = ""
        if "Mutual Funds" in cats:
            mf_instructions = """
SPECIAL RULE for "Mutual Funds" category:
Focus on mutual fund news — SIP trends, AMC announcements, SEBI regulations, fund performance.
Do NOT generate an NFO table — NFO data is handled separately via AMFI's official live feed.
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
Pick exactly 3 articles covering a MIX of:
  1. A Federal Reserve specific story — interest rate decisions, FOMC meeting outcomes, Fed Chair statements, US jobs/employment data, or US monetary policy direction (Federal Reserve is the US central bank, equivalent to India's RBI)
  2. How global developments (Fed policy, US markets, global liquidity) are impacting India specifically
  3. Any other significant global market development affecting Indian investors (S&P 500, Nasdaq, Dow, global indices)
Prioritize Fed/FOMC/US interest rate/US jobs articles when available in the source list — these are high priority for this category.
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
- CRITICAL: Every story MUST be its own separate <div class="story">...</div> block, stacked vertically one after another. NEVER wrap multiple stories in a single shared container, NEVER use flexbox, NEVER use CSS Grid, NEVER add a "style" attribute to any element, and NEVER place stories side-by-side in columns. Each story div must be 100% width and appear below the previous one, exactly like the template example above.
- Do NOT add any class names other than the ones shown in the template above (story, story-title, story-summary, story-why, story-link-row, story-link, story-source, investor-tips, investor-tips-heading).
- Return ONLY HTML. No markdown. No code fences. No extra text."""

    categories_html_parts = []
    for idx, batch in enumerate(batches, 1):
        logger.info(f"Calling Groq ({idx+1}/{len(batches)+1}): Categories batch {idx} ({', '.join(batch)})...")
        html_part = _call_groq(_build_categories_prompt(batch))
        categories_html_parts.append(html_part)
        if idx < len(batches):
            time.sleep(45)  # 45s between categories keeps TPM well under 12k/min limit

    categories_html = "\n".join(categories_html_parts)

    # ── Parse response into per-category dict ────────────────────────────
    # Split on the opening tag of each category block — avoids nested </div> issues
    categories_dict = {}
    parts = re.split(r'(?=<div class="category-stories" data-category=")', categories_html)
    for part in parts:
        part = part.strip()
        if not part:
            continue
        m = re.match(r'<div class="category-stories" data-category="([^"]+)">(.*)', part, re.DOTALL)
        if not m:
            continue
        cat_name   = m.group(1).strip()
        inner_html = m.group(2).strip()

        # Remove only the single outermost closing </div> that wraps category-stories.
        # We do this by counting div depth to find the correct closing tag position.
        depth = 0
        close_pos = len(inner_html)
        i = 0
        while i < len(inner_html):
            if inner_html[i:i+4] == "<div":
                depth += 1
                i += 4
            elif inner_html[i:i+6] == "</div>":
                if depth == 0:
                    close_pos = i
                    break
                depth -= 1
                i += 6
            else:
                i += 1
        inner_html = inner_html[:close_pos].strip()

        for known_cat in all_news.keys():
            if known_cat.lower() in cat_name.lower() or cat_name.lower() in known_cat.lower():
                categories_dict[known_cat] = _sanitize_category_html(inner_html)
                logger.info(f"  Parsed category: {known_cat} ({len(inner_html)} chars)")
                break

    if not categories_dict:
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