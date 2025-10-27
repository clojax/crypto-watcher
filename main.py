from fastapi import FastAPI
import requests

app = FastAPI()

COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price"

def get_price(coin):
    try:
        url = f"https://api.coingecko.com/api/v3/coins/{coin}"
        r = requests.get(url, timeout=10)
        data = r.json()
        return data["market_data"]["current_price"]["gbp"]
    except Exception as e:
        print("Error:", e)
        return None

@app.get("/")
def home():
    return {"status": "Crypto Watcher API running"}

@app.get("/price/{coin}")
def price(coin: str):
    price = get_price(coin.lower())
    if price is None:
        return {"error": "Coin not found"}
    return {"coin": coin, "price_gbp": price}

