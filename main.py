from fastapi import FastAPI
import requests

app = FastAPI()

def get_price(coin):
    try:
        url = f"https://api.coingecko.com/api/v3/coins/{coin.lower()}"
        r = requests.get(url, timeout=10)
        data = r.json()
        return data["market_data"]["current_price"]["gbp"]
    except:
        return None

@app.get("/")
def home():
    return {"status": "Crypto Watcher API running"}

@app.get("/price/{coin}")
def price(coin: str):
    p = get_price(coin)
    if p is None:
        return {"coin": coin, "price_gbp": None, "info": "Coin not found or no data returned"}
    return {"coin": coin, "price_gbp": p}
