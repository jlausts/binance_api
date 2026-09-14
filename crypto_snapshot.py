import requests, pandas as pd, time
from pathlib import Path

def get_snapshot():
    joiner = '","'
    base = "https://api.binance.com/api/v3"
    info = requests.get(f"{base}/exchangeInfo", timeout=30).json()
    symbols = [x["symbol"] for x in info["symbols"] if x["status"] == "TRADING" and x["quoteAsset"] == "USDT"]

    data = requests.get(f'{base}/ticker/price?symbols=["{joiner.join(symbols)}"]', timeout=30).json()
    return pd.DataFrame(data).set_index('symbol').astype({'price': 'float32'})

def save_snapshot():
    date = Path('snapshots') / pd.to_datetime(time.time(), unit='s').strftime("%Y-%M-%d")
    date.mkdir(exist_ok=True, parents=True)
    ts = (date / pd.to_datetime(time.time(), unit='s').strftime("%H_%M")).with_suffix('.xz')
    get_snapshot().to_pickle(ts)

if __name__ == '__main__':
    save_snapshot()