# Etica Daily Intelligence Brief

Automated morning news briefing — fetches, filters, and summarizes financial news via Gemini AI, then emails a professional HTML report to the team every day at 8:00 AM IST.

---

## How It Works

```
8:00 AM IST → GitHub Actions triggers
→ Fetch ~140 articles (20 × 7 categories) from Google News RSS
→ Deduplicate similar headlines
→ Gemini picks top 5 stories per category + writes executive summary
→ Assemble HTML email
→ Send to all recipients
→ Done. No human involvement needed.
```

---

## File Structure

```
etica-daily-intelligence/
│
├── main.py              ← Orchestrator (run this)
├── news_fetcher.py      ← RSS collection + deduplication
├── summarizer.py        ← Gemini AI integration
├── email_sender.py      ← HTML assembly + SMTP delivery
│
├── templates/
│   └── report.html      ← Email template (edit to re-brand)
│
├── requirements.txt
│
└── .github/
    └── workflows/
        └── daily_news.yml  ← Automation schedule
```

---

## Setup (One Time)

### 1. Get a Gemini API Key

1. Go to [aistudio.google.com](https://aistudio.google.com)
2. Click **Get API Key** → Create API Key
3. Copy it

### 2. Set Up Gmail App Password

Gmail requires an **App Password** (not your regular password):

1. Go to your Google Account → **Security**
2. Enable **2-Step Verification** (if not already)
3. Search for **App Passwords**
4. Select app: *Mail* → device: *Other* → type `Etica Automation`
5. Copy the 16-character password

### 3. Add GitHub Secrets

In your GitHub repo → **Settings → Secrets and variables → Actions → New repository secret**

| Secret Name       | Value                              |
|-------------------|------------------------------------|
| `GEMINI_API_KEY`  | Your Gemini API key                |
| `EMAIL_USER`      | your-gmail@gmail.com               |
| `EMAIL_PASSWORD`  | 16-char Gmail App Password         |
| `RECIPIENT_1`     | ceo@etica.in                       |
| `RECIPIENT_2`     | advisor1@etica.in                  |
| `RECIPIENT_3`     | advisor2@etica.in                  |
| `RECIPIENT_4`     | (add more as needed)               |

### 4. Push to GitHub

```bash
git init
git add .
git commit -m "Initial: Etica Daily Intelligence"
git remote add origin https://github.com/YOUR_ORG/etica-daily-intelligence.git
git push -u origin main
```

GitHub Actions will now run automatically at **6:00 AM IST, Monday–Friday**.

---

## Manual Test Run

```bash
# Install dependencies
pip install -r requirements.txt

# Set env vars (use your real keys)
export GEMINI_API_KEY="your-key"
export EMAIL_USER="you@gmail.com"
export EMAIL_PASSWORD="your-app-password"
export RECIPIENT_1="you@gmail.com"

# Run
python main.py
```

---

## Customisation

### Change categories
Edit `CATEGORIES` dict in `news_fetcher.py`

### Change recipients
Add/remove `RECIPIENT_N` secrets in GitHub and update `email_sender.py`

### Change schedule
Edit the `cron` line in `.github/workflows/daily_news.yml`
- Run every day (including weekends): remove the `1-5` restriction
- Change time: `30 0 * * *` = 6:00 AM IST (00:30 UTC)

### Change email design
Edit `templates/report.html` — it's plain HTML + CSS, easy to modify.

---

## Failure Alerts

If the script crashes (network error, Gemini outage, SMTP issue), it automatically sends a failure email to all recipients with the full error traceback and a link to GitHub Actions logs.

---

## Cost

| Service        | Cost                          |
|----------------|-------------------------------|
| GitHub Actions | Free (2,000 min/month)        |
| Gemini API     | Free tier covers daily usage  |
| Gmail SMTP     | Free                          |
| **Total**      | **₹0/month**                  |
