"""
Nifty50 Premarket (NSE Pre-Open) Tracker — Streamlit app
==========================================================
Deployed on Streamlit Community Cloud (or run locally with `streamlit run app.py`).

NSE pre-open session is live 9:00–9:15 AM IST. Outside that window this will
show a STALE (previous session's) snapshot — the app warns you when that's the case.

NOTE: NSE blocks many datacenter IPs (this includes Streamlit Cloud's servers,
same as Colab). If you get repeated 401/403 errors, see the README for
workarounds (run locally, or route through a proxy).
"""

import time
from datetime import datetime

import numpy as np
import pandas as pd
import pytz
import requests
import streamlit as st
import plotly.graph_objects as go

# -------------------------------------------------------------------
# Page config
# -------------------------------------------------------------------
st.set_page_config(page_title="Nifty50 Premarket Tracker", layout="wide")

KEY_OPTIONS = ["NIFTY 50", "NIFTY BANK", "NIFTYNEXT50", "FNO", "ALL", "SME", "OTHERS"]


# -------------------------------------------------------------------
# NSE session / fetch helpers
# -------------------------------------------------------------------
def get_nse_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://www.nseindia.com/market-data/pre-open-market-cotation",
        }
    )
    session.get("https://www.nseindia.com", timeout=10)
    time.sleep(1)
    return session


def fetch_preopen_data(session: requests.Session, key: str = "NIFTY 50", retries: int = 3):
    url = f"https://www.nseindia.com/api/market-data-pre-open?key={key}"
    last_exc = None
    for _ in range(retries):
        try:
            resp = session.get(url, timeout=10)
            if resp.status_code == 200:
                return resp.json()
        except requests.RequestException as exc:
            last_exc = exc
        time.sleep(2)
        session = get_nse_session()
    if last_exc:
        raise last_exc
    resp.raise_for_status()


def parse_preopen(data: dict) -> pd.DataFrame:
    rows = []
    for item in data.get("data", []):
        meta = item.get("metadata", {})
        pre = item.get("detail", {}).get("preOpenMarket", {})
        rows.append(
            {
                "Symbol": meta.get("symbol"),
                "PrevClose": meta.get("previousClose"),
                "IEP": pre.get("IEP", meta.get("iep")),
                "Change": meta.get("change"),
                "PctChange": meta.get("pChange"),
                "YearHigh": meta.get("yearHigh"),
                "YearLow": meta.get("yearLow"),
                "FinalQuantity": pre.get("finalQuantity"),
                "TotalTradedVolume": pre.get("totalTradedVolume"),
                "TotalTurnover": meta.get("totalTurnover"),
                "MarketCap": meta.get("marketCap"),
                "TotalBuyQuantity": pre.get("totalBuyQuantity"),
                "TotalSellQuantity": pre.get("totalSellQuantity"),
            }
        )
    return pd.DataFrame(rows)


def add_trade_signals(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    buy = df["TotalBuyQuantity"].fillna(0)
    sell = df["TotalSellQuantity"].fillna(0)
    total_qty = buy + sell

    df["OrderImbalance"] = np.where(total_qty > 0, (buy - sell) / total_qty, np.nan)
    df["BuySellRatio"] = np.where(sell > 0, buy / sell, np.nan)
    df["DistFrom52WHighPct"] = np.where(
        df["YearHigh"] > 0, (df["IEP"] - df["YearHigh"]) / df["YearHigh"] * 100, np.nan
    )
    df["DistFrom52WLowPct"] = np.where(
        df["YearLow"] > 0, (df["IEP"] - df["YearLow"]) / df["YearLow"] * 100, np.nan
    )
    df["NearCircuitFlag"] = df["PctChange"].abs() >= 9
    df["WatchScore"] = df["PctChange"].abs() * (1 + df["OrderImbalance"].abs().fillna(0))
    return df


def is_preopen_session_live():
    ist = pytz.timezone("Asia/Kolkata")
    now = datetime.now(ist)
    if now.weekday() >= 5:
        return False, "Weekend — market closed, data is stale.", now
    start = now.replace(hour=9, minute=0, second=0, microsecond=0)
    end = now.replace(hour=9, minute=15, second=0, microsecond=0)
    if start <= now <= end:
        return True, "Live pre-open window.", now
    return (
        False,
        "Outside 9:00–9:15 AM IST window — this is a STALE/previous-session snapshot, not live premarket.",
        now,
    )


@st.cache_data(ttl=25, show_spinner=False)
def load_data(key: str) -> pd.DataFrame:
    session = get_nse_session()
    raw = fetch_preopen_data(session, key=key)
    df = parse_preopen(raw)
    df = df.dropna(subset=["PctChange"]).sort_values("PctChange", ascending=False)
    df = add_trade_signals(df)
    return df


# -------------------------------------------------------------------
# Chart builders (Plotly, renders natively in Streamlit)
# -------------------------------------------------------------------
def make_bar_chart(df: pd.DataFrame) -> go.Figure:
    plot_df = df.dropna(subset=["PctChange"]).sort_values("PctChange", ascending=True)
    colors = ["#2ecc71" if v >= 0 else "#e74c3c" for v in plot_df["PctChange"]]
    labels = [
        f"{row.PctChange:+.2f}%  (₹{row.Change:+.2f})" if pd.notna(row.Change) else f"{row.PctChange:+.2f}%"
        for row in plot_df.itertuples()
    ]

    fig = go.Figure(
        go.Bar(
            x=plot_df["PctChange"],
            y=plot_df["Symbol"],
            orientation="h",
            marker_color=colors,
            text=labels,
            textposition="outside",
            hovertemplate="%{y}: %{x:.2f}%<extra></extra>",
        )
    )
    fig.update_layout(
        title="Premarket Movement — All Stocks",
        xaxis_title="% Change (Premarket vs Prev Close)",
        height=max(500, 22 * len(plot_df)),
        margin=dict(l=10, r=80, t=50, b=40),
        showlegend=False,
    )
    fig.add_vline(x=0, line_color="black", line_width=1)
    return fig


def make_donut_chart(df: pd.DataFrame) -> go.Figure:
    up = int((df["PctChange"] > 0).sum())
    down = int((df["PctChange"] < 0).sum())
    flat = int((df["PctChange"] == 0).sum())
    values, labels, colors = [], [], []
    for v, l, c in zip([up, down, flat], [f"Up ({up})", f"Down ({down})", f"Flat ({flat})"], ["#2ecc71", "#e74c3c", "#95a5a6"]):
        if v > 0:
            values.append(v)
            labels.append(l)
            colors.append(c)
    fig = go.Figure(go.Pie(values=values, labels=labels, hole=0.5, marker_colors=colors))
    fig.update_layout(title="Market Breadth", height=400, margin=dict(l=10, r=10, t=50, b=10))
    return fig


# -------------------------------------------------------------------
# UI
# -------------------------------------------------------------------
st.title("📈 Nifty50 Premarket (NSE Pre-Open) Tracker")

with st.sidebar:
    st.header("Settings")
    key = st.selectbox("Index / segment", KEY_OPTIONS, index=0)
    top_n = st.slider("Top N gainers/losers to show", 5, 50, 30)
    watch_n = st.slider("Watchlist size", 5, 30, 15)
    auto_refresh = st.checkbox("Auto-refresh every 30s (during 9:00–9:15 AM IST)")
    manual_refresh = st.button("🔄 Refresh now")

if manual_refresh:
    st.cache_data.clear()

live, note, now = is_preopen_session_live()
st.caption(f"Snapshot time: {now.strftime('%Y-%m-%d %H:%M:%S IST')}")
if not live:
    st.warning(f"⚠️ {note}")

try:
    with st.spinner("Fetching data from NSE..."):
        df = load_data(key)
except Exception as e:
    st.error(
        "Could not fetch data from NSE. This usually means NSE's bot-check blocked "
        "this server's IP (common on cloud-hosted deployments). Try 'Refresh now', "
        "or run the app locally — see the README for details.\n\n"
        f"Error: {e}"
    )
    st.stop()

if df.empty:
    st.info("No premarket data returned. Try again closer to 9:00–9:15 AM IST on a trading day.")
    st.stop()

# --- Summary metrics ---
up = int((df["PctChange"] > 0).sum())
down = int((df["PctChange"] < 0).sum())
flat = int((df["PctChange"] == 0).sum())
total = len(df)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total stocks", total)
c2.metric("Up", up, f"{up/total*100:.1f}%")
c3.metric("Down", down, f"{down/total*100:.1f}%")
c4.metric("Flat", flat)

# --- Charts ---
col1, col2 = st.columns([3, 1])
with col1:
    st.plotly_chart(make_bar_chart(df), use_container_width=True)
with col2:
    st.plotly_chart(make_donut_chart(df), use_container_width=True)

# --- Watchlist ---
st.subheader(f"🎯 Must-check Watchlist (Top {watch_n} by move + order-imbalance conviction)")
watch_cols = [
    "Symbol", "IEP", "PctChange", "OrderImbalance", "BuySellRatio",
    "DistFrom52WHighPct", "DistFrom52WLowPct", "NearCircuitFlag", "WatchScore",
]
watch_cols = [c for c in watch_cols if c in df.columns]
watchlist_df = df.dropna(subset=["WatchScore"]).sort_values("WatchScore", ascending=False).head(watch_n)
st.dataframe(watchlist_df[watch_cols].round(2), use_container_width=True, hide_index=True)

circuit_hits = df[df["NearCircuitFlag"] == True]  # noqa: E712
if len(circuit_hits) > 0:
    st.warning(f"{len(circuit_hits)} stock(s) showing premarket move ≥9% — verify circuit limit before trading.")
    st.dataframe(circuit_hits[["Symbol", "PctChange"]].round(2), use_container_width=True, hide_index=True)

# --- Gainers / Losers ---
gcol, lcol = st.columns(2)
with gcol:
    st.subheader(f"🟢 Top Gainers ({min(top_n, up)} of {up})")
    gainers = df[df["PctChange"] > 0].sort_values("PctChange", ascending=False).head(top_n)
    st.dataframe(gainers[["Symbol", "PrevClose", "IEP", "PctChange"]].round(2), use_container_width=True, hide_index=True)
with lcol:
    st.subheader(f"🔴 Top Losers ({min(top_n, down)} of {down})")
    losers = df[df["PctChange"] < 0].sort_values("PctChange", ascending=True).head(top_n)
    st.dataframe(losers[["Symbol", "PrevClose", "IEP", "PctChange"]].round(2), use_container_width=True, hide_index=True)

# --- Full data table ---
with st.expander("📋 Full premarket data — every stock, every field"):
    st.dataframe(df.sort_values("PctChange", ascending=False), use_container_width=True, hide_index=True)

st.caption(
    "Data source: NSE India pre-open API. This is descriptive market data, not investment advice. "
    "Always verify live price/quantity before placing an order."
)

# --- Auto-refresh loop (simple, Streamlit-friendly) ---
if auto_refresh:
    time.sleep(30)
    st.cache_data.clear()
    st.rerun()
