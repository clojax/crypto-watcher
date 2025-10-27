from fastapi import FastAPI
import requests

app = FastAPI()

COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price"

def get_price(coin):
    params = {"ids": coin, "vs_currencies": "gbp"}
    r = requests.get(COINGECKO_URL, params=params)
    return r.json().get(coin, {}).get("gbp")

@app.get("/")
def home():
    return {"status": "Crypto Watcher API running"}

@app.get("/price/{coin}")
def price(coin: str):
    price = get_price(coin.lower())
    if price is None:
        return {"error": "Coin not found"}
    return {"coin": coin, "price_gbp": price}

