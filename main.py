from fastapi import FastAPI
import requests
import json
import time
import threading
import os


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

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
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

