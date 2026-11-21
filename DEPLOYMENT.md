# Deploying PatentDiff to Render (Cache-First Mode)

This guide walks you through deploying the PatentDiff evaluation workbench to [Render.com](https://render.com) in **cache-first mode**, which:

- ✅ **Fast cold starts** (1–2 seconds, not 5–10)
- ✅ **No API key required** (safe for portfolio)
- ✅ **Fully interactive** Dashboard, Traces, Comparison tabs
- ✅ **Demo mode banner** at the top
- ✅ **Free tier** available

---

## Prerequisites

1. **GitHub account** — your PatentDiff repo must be on GitHub (public or private)
2. **Render account** — sign up at [render.com](https://render.com)
3. **Cached data** — ensure `traces/traces.jsonl`, `traces/citation_text_eval_full.jsonl`, `traces/phosita_eval_full.jsonl` are committed to Git

---

## Step 1: Prepare Your Repository

Make sure the following files are in your repo root:

- ✅ `Procfile` — tells Render how to start the app
- ✅ `.python-version` — pins Python 3.13.9 (Render ignores runtime.txt)
- ✅ `.env.example` — documents environment variables
- ✅ `requirements.txt` — dependencies (should already exist)

**Check these are committed:**

```bash
git add Procfile .python-version .env.example DEPLOYMENT.md
git commit -m "deployment: add Procfile, runtime.txt, .env.example for Render"
git push origin main
```

---

## Step 2: Create a Render Web Service

1. Go to [dashboard.render.com](https://dashboard.render.com)
2. Click **"New +"** → **"Web Service"**
3. **Connect your GitHub account** (if not already connected)
4. **Select the PatentDiff repository**
5. Fill in the form:

| Field | Value |
|-------|-------|
| **Name** | `patentdiff-demo` (or your preferred name) |
| **Environment** | `Python 3` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `gunicorn app_unified.app:server --bind 0.0.0.0:$PORT --workers 1 --timeout 120` |
| **Instance Type** | Free (or paid if you want faster startup) |

6. Click **"Advanced"** to add environment variables

---

## Step 3: Set Environment Variables

Under **Advanced → Environment**:

| Key | Value | Notes |
|-----|-------|-------|
| `DEMO_MODE` | `true` | Enables cache-first mode |

**That's it.** You don't need `GROQ_API_KEY` in demo mode.

If you ever want to test live API calls on Render, add:
| `GROQ_API_KEY` | `your_key_here` | (optional) |

---

## Step 4: Deploy

Click **"Create Web Service"** — Render will:

1. ✅ Clone your repo
2. ✅ Install dependencies from `requirements.txt`
3. ✅ Read `.python-version`
4. ✅ Set environment variables
5. ✅ Start the app

**Deployment typically takes 2–3 minutes.**

Watch the logs on the Render dashboard. When you see:

```
🚀 Demo mode: pre-loading cached data...
   Loaded 87 traces
   Loaded 87 citation evals
   Loaded 87 phosita evals
   ...
```

Your app is ready. You'll get a live URL like:

```
https://patentdiff-demo.onrender.com
```

---

## Step 5: Test the Live App

1. Open your Render URL
2. You should see:
   - **Info strip at top:** "Demo mode: every number here is recorded from real runs. Live model calls are off."
   - **Dashboard tab** (`/eval`) — fully interactive with cached heatmaps
   - **Traces tab** (`/eval/traces`) — click to view cached traces
   - **Comparison tab** (`/eval/comparison`) — see experiment results (if any)
   - **PatentDiff prototype** (`/prototype`) — "Load example" fills a real patent pair and Analyze replays its recorded output. `/` redirects to the Dashboard.
   - **Experiment Agent** (`/eval/agent`) — Analyze shows the recorded plan; Approve shows the recorded stage-1 result.

---

## Step 6: Link from Your Portfolio

In your Astro portfolio, add a project card:

```astro
---
// src/pages/projects/patentdiff.astro
---

<div class="project">
  <h1>PatentDiff</h1>
  <p>End-to-end evaluation framework for LLM-based patent analysis.</p>
  
  <div class="links">
    <a href="https://patentdiff-demo.onrender.com" target="_blank">
      🔗 Live Dashboard
    </a>
    <a href="https://github.com/yourusername/PatentDiff" target="_blank">
      📖 GitHub
    </a>
    <a href="/patentdiff-demo.mp4" target="_blank">
      ▶️ Demo Video (5 min)
    </a>
  </div>
</div>
```

---

## Troubleshooting

### "Cold start is slow (10+ seconds)"

**Expected on Render's free tier.** The first visitor waits 10–15 seconds while the dyno wakes up. Subsequent visitors get instant responses. For a portfolio, this is acceptable — most hiring managers won't notice.

**To reduce cold start:**
- Upgrade to a **paid tier** (Render's $7/month starter plan keeps the dyno warm)
- Or use the free tier and accept the 10–15s first-visitor delay

### "Demo mode banner doesn't appear"

Check the Render logs. You should see:

```
🚀 Demo mode: pre-loading cached data...
```

If not, verify `DEMO_MODE=true` is set in Render's environment variables.

### "Traces tab is empty"

Ensure your cached `.jsonl` files are committed to Git:

```bash
git status traces/
# Should show no uncommitted changes
```

If files are large, check your `.gitignore` isn't excluding them.

### "I want to test live API calls"

1. Add `GROQ_API_KEY` to Render's environment
2. Set `DEMO_MODE=false`
3. Redeploy

Render will rebuild and restart the app.

---

## Going Live → Using Paid Plans

If you want to use this for a real product (not just portfolio):

1. **Upgrade Render plan** to avoid cold-start sleeps
2. **Keep `DEMO_MODE=false`** (or toggle per environment)
3. **Set `GROQ_API_KEY`** securely in Render's vault
4. Consider **caching traces** in a database (Redis) for faster dashboard loads

---

## Understanding Cache-First Mode

When `DEMO_MODE=true`:

1. **On app startup:**
   - `core/demo_mode.py` loads all `.jsonl` files into memory
   - No live model calls: the prototype and Experiment Agent replay recorded results
   - Dashboard, Traces, Comparison tabs serve cached data

2. **Performance:**
   - Cold start: 1–2 sec (just loading Python + cache)
   - Interactions: instant (no API calls)
   - Render free tier: wakes after 15 min of inactivity, then instant again

3. **Why this works for portfolios:**
   - No secrets exposed (no API key needed)
   - Fully interactive (not screenshots or videos)
   - Shows the real Dash app architecture
   - Impressive UX (instant interactions)

---

## Next Steps

- 🎥 **Record your demo video** walking through the methodology → Dashboard → results
- 📄 **Write a 2-page portfolio context** (see [README.md](README.md) for overview)
- 🔗 **Link from your Astro portfolio** (see Step 6 above)
- 🚀 **Share the live URL** with hiring managers

---

## Questions?

Refer to [README.md](README.md) for project overview or [docs/superpowers/](docs/superpowers/) for the full evaluation methodology.
