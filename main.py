from fastapi import FastAPI
import requests
import json
import time
import threading
import os
from datetime import datetime, timedelta, time as dtime
from zoneinfo import ZoneInfo  # built-in on Python 3.9+


app = FastAPI()

def get_price(coin):
    try:
        url = f"https://api.coingecko.com/api/v3/coins/{coin.lower()}"
        headers = {"User-Agent": "Mozilla/5.0"}  # <-- Important
        r = requests.get(url, headers=headers, timeout=10)
        data = r.json()
        return data["market_data"]["current_price"]["gbp"]
    except:
        return None

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
CHAT_ID = "8260198146"  # your chat ID

def send_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": message})


@app.get("/")
def home():
    return {"status": "Crypto Watcher API running"}

@app.get("/price/{coin}")
def price(coin: str):
    p = get_price(coin)
    if p is None:
        return {"coin": coin, "price_gbp": None, "info": "Coin not found or no data returned"}
    return {"coin": coin, "price_gbp": p}

prices = {}

def update_prices():
    while True:
        try:
            with open("watchlist.json") as f:
                watchlist = json.load(f)["coins"]

            for coin in watchlist:
                prices[coin] = get_price(coin)
        except:
            pass

        time.sleep(60)  # update every 60 seconds

threading.Thread(target=update_prices, daemon=True).start()

@app.get("/watchlist")
def get_watchlist_prices():
    return prices

@app.get("/testalert")
def testalert():
    send_alert("Crypto Watcher Connected ✅")
    return {"sent": True}

# ====== LONG-TERM DAILY ALERT ENGINE (07:00 Europe/London) ======

def cg_market_chart_gbp(coin_id: str, days: int = 400):
    """Return daily GBP closes; safe on rate-limits or bad responses."""
    try:
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
        headers = {"User-Agent": "Mozilla/5.0"}
        params = {"vs_currency": "gbp", "days": str(days), "interval": "daily"}
        r = requests.get(url, headers=headers, params=params, timeout=20)
        if r.status_code != 200:
            return []  # treat as no data
        j = r.json()
        prices = j.get("prices")
        if not isinstance(prices, list):
            return []
        return [p[1] for p in prices if isinstance(p, list) and len(p) >= 2]
    except Exception:
        return []

def recent_swing_high(values, lookback: int = 180):
    if not values:
        return None
    subset = values[-lookback:] if len(values) >= lookback else values
    return max(subset) if subset else None

def pct(a, b):
    if b is None or b == 0 or a is None:
        return None
    return round((a - b) / b * 100, 2)

def load_json(path, default):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return default

def save_json(path, obj):
    try:
        with open(path, "w") as f:
            json.dump(obj, f)
    except Exception:
        pass

LAST_ALERTS_PATH = "last_alerts.json"

def daily_longterm_check():
    """
    Runs once when called.
    For each coin in watchlist.json:
      - fetch last ~400 days of daily prices (GBP)
      - compute 200D SMA (trend anchor)
      - compute drawdown from recent swing high (180-day window)
      - send ONE daily alert if in accumulation (-30% to -40%) or extended above trend (profit-taking)
    """
    # read watchlist
    try:
        with open("watchlist.json") as f:
            watchlist = json.load(f)["coins"]
    except Exception:
        watchlist = []

    last_alerts = load_json(LAST_ALERTS_PATH, {})  # {coin: {"date":"YYYY-MM-DD","type":"accumulation|profit"}}
    today_str = datetime.now(tz=DATA_TZ).date().isoformat()

    for coin in watchlist:
        try:
            series = cg_market_chart_gbp(coin, days=400)
            if not series or len(series) < 210:
                continue

            current = series[-1]
            sma200 = sma(series, 200)
            swing = recent_swing_high(series, lookback=180)

            # percentages
            dd = pct(current, swing)  # negative when below swing high
            ext = pct(current, sma200)  # positive when above trend

            # Decide signal
            signal_type = None
            msg = None

            # Accumulation: 30–40% below recent swing high AND under 200D trend
            if dd is not None and sma200 is not None and ext is not None:
                if dd <= -30.0 and dd >= -40.0 and ext < 0:
                    signal_type = "accumulation"
                    msg = (
                        f"Accumulation Opportunity Identified.\n\n"
                        f"{coin.upper()} is {abs(dd)}% below its recent swing high and "
                        f"{abs(ext)}% below its long-term trend (200D).\n\n"
                        f"This aligns with your plan (30–40% retrace zone).\n"
                        f"No urgency. Execute a controlled, strategic add."
                    )
                # Profit-taking: meaningfully extended above trend
                elif ext is not None and ext >= 25.0:
                    signal_type = "profit"
                    msg = (
                        f"Profit Management Signal.\n\n"
                        f"{coin.upper()} is {ext}% above its long-term trend (200D) and pressing into strength.\n\n"
                        f"Protect gains. Take a measured reduction per plan.\n"
                        f"This is discipline, not emotion."
                    )

            # Only send once per day per coin & type
            if signal_type and msg:
                prev = last_alerts.get(coin, {})
                if prev.get("date") != today_str or prev.get("type") != signal_type:
                    send_alert(msg)
                    last_alerts[coin] = {"date": today_str, "type": signal_type}

        except Exception:
            # Never crash the loop on a single coin
            continue

    save_json(LAST_ALERTS_PATH, last_alerts)

def seconds_until_next_7am_london():
    now = datetime.now(tz=DATA_TZ)
    target = datetime.combine(now.date(), dtime(hour=7, minute=0, second=0), tzinfo=DATA_TZ)
    if now >= target:
        target = target + timedelta(days=1)
    return (target - now).total_seconds()

def daily_scheduler_thread():
    # Initial wait to the next 07:00 London run
    time.sleep(max(1, int(seconds_until_next_7am_london())))
    while True:
        daily_longterm_check()
        # Then sleep ~24h to next day 07:00
        time.sleep(24 * 60 * 60)

# Start the daily scheduler (daemon thread)
threading.Thread(target=daily_scheduler_thread, daemon=True).start()

# Manual endpoint to test the daily logic immediately
@app.get("/run-daily-now")
def run_daily_now():
    try:
        daily_longterm_check()
        return {"ok": True, "ran": True}
    except Exception as e:
        # Optional: send a silent self-notification for debugging
        try:
            send_alert(f"Daily check error (handled): {type(e).__name__}")
        except Exception:
            pass
        return {"ok": False, "error": str(e)}


@app.get("/run-weekly-now")
def run_weekly_now():
    weekly_summary()
    return {"ok": True, "weekly": True}


# ====== WEEKLY SUMMARY (SUNDAY 09:00 LONDON) ======

def weekly_summary():
    try:
        with open("watchlist.json") as f:
            watchlist = json.load(f)["coins"]
    except:
        return

    summary_lines = ["WEEKLY OUTLOOK — LONG-TERM POSITIONING\n"]

    for coin in watchlist:
        try:
            series = cg_market_chart_gbp(coin, days=400)
            if not series or len(series) < 210:
                continue

            current = series[-1]
            sma200 = sma(series, 200)
            swing = recent_swing_high(series, lookback=180)

            dd = pct(current, swing)  # drawdown from high
            ext = pct(current, sma200)  # extension vs trend

            # Determine state
            if dd is not None and dd <= -30 and dd >= -40 and ext < 0:
                status = "ACCUMULATE"
            elif ext is not None and ext >= 25:
                status = "PROFIT MANAGEMENT"
            else:
                status = "HOLD"

            summary_lines.append(
                f"{coin.upper()} — {status}\n"
                f"• Drawdown: {dd}% from swing high\n"
                f"• Trend Extension: {ext}% vs 200D\n"
            )

        except:
            continue

    send_alert("\n".join(summary_lines))


def weekly_scheduler_thread():
    while True:
        now = datetime.now(tz=DATA_TZ)
        if now.weekday() == 6 and now.hour == 9:  # Sunday = 6
            weekly_summary()
            time.sleep(3600)  # avoid repeat within the same hour
        time.sleep(300)  # check every 5 minutes


threading.Thread(target=weekly_scheduler_thread, daemon=True).start()

