# Nifty50 Premarket (NSE Pre-Open) Tracker

A Streamlit app version of the Colab notebook — pulls NSE's pre-open market
data (9:00–9:15 AM IST), shows gainers/losers, an order-imbalance watchlist,
and interactive charts.

## ⚠️ Important caveat before you deploy

NSE's website blocks many **datacenter IPs** as a bot-check measure. This
affected Colab, and it can also affect **Streamlit Community Cloud**, since
both run on cloud provider IP ranges (AWS/GCP). Symptoms: repeated 401/403
errors from the app.

Workarounds, in order of reliability:
1. **Run it locally** (steps below) — your home/office IP is far less likely to be blocked.
2. Deploy on a VPS with a residential/India-based IP, or behind a proxy service.
3. On Streamlit Cloud, just hit "Refresh now" a few times — NSE's bot-check is inconsistent, so it sometimes succeeds.

None of this is code you need to change — the app already retries and
refreshes its session automatically, same as your original notebook.

---

## Step 1 — Get the code into a GitHub repository

1. Create a new folder locally (or use the one you download from this chat) with these files:
   - `app.py`
   - `requirements.txt`
   - `.gitignore`
   - `README.md`

2. Create a new GitHub repo:
   - Go to https://github.com/new
   - Name it e.g. `nifty50-premarket-tracker`
   - Leave it empty (no README/license — you already have files)

3. Push your code:
   ```bash
   cd nifty50-premarket-tracker
   git init
   git add .
   git commit -m "Initial commit: Nifty50 premarket tracker"
   git branch -M main
   git remote add origin https://github.com/<your-username>/nifty50-premarket-tracker.git
   git push -u origin main
   ```

   (If you don't have `git` set up, install it and run `git config --global user.name "..."` and `git config --global user.email "..."` first.)

## Step 2 — Deploy on Streamlit Community Cloud

1. Go to https://share.streamlit.io and sign in with your GitHub account.
2. Click **"New app"**.
3. Choose:
   - **Repository**: `<your-username>/nifty50-premarket-tracker`
   - **Branch**: `main`
   - **Main file path**: `app.py`
4. Click **"Deploy"**. Streamlit Cloud will install `requirements.txt` automatically and start the app.
5. You'll get a public URL like `https://nifty50-premarket-tracker-<hash>.streamlit.app`.

That's it — no server config needed. Every time you `git push` to `main`, Streamlit Cloud auto-redeploys.

## Step 3 — Run it locally instead (recommended if NSE blocks the cloud IP)

```bash
git clone https://github.com/<your-username>/nifty50-premarket-tracker.git
cd nifty50-premarket-tracker
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

This opens the app at `http://localhost:8501`.

## Using the app

- **Sidebar**: pick the index/segment (NIFTY, BANKNIFTY, etc.), how many gainers/losers to show, watchlist size, and whether to auto-refresh every 30s.
- **Main panel**: summary metrics, bar chart of all stocks' % change, market-breadth donut, the "must-check" watchlist ranked by move size + order-imbalance conviction, top gainers/losers, and a full raw-data table in an expander.
- The app only shows genuinely live data during **9:00–9:15 AM IST** on trading days; outside that window it warns you the snapshot is stale.

## Notes on the conversion from your Colab notebook

- All the original logic (session/cookie handling, retries, `add_trade_signals`, `WatchScore`, circuit-flag heuristic) is unchanged — just wrapped in `load_data()` and cached for 25 seconds (`st.cache_data(ttl=25)`) so the app doesn't hammer NSE on every widget interaction.
- Matplotlib was swapped for **Plotly** since it renders natively and interactively in Streamlit (`st.plotly_chart`).
- The `track_live()` polling loop from Cell 7 is replaced by the sidebar's **"Auto-refresh every 30s"** checkbox, which uses `st.rerun()`.
