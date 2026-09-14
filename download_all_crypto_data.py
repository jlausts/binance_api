from datetime import datetime, timezone
import pandas as pd
import requests
from tqdm import tqdm
from pathlib import Path


def download_binance_1m(symbol: str = "BTCUSDT", start: str = "2026-09-05") -> pd.DataFrame:
    url = "https://api.binance.com/api/v3/klines"
    start_ms = int(datetime.fromisoformat(start).replace(tzinfo=timezone.utc).timestamp() * 1000)
    end_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    rows = []

    total_minutes = max((end_ms - start_ms) // 60_000, 1)

    with tqdm(total=total_minutes, desc=symbol, unit="min", dynamic_ncols=True) as bar:
        while True:
            try:
                data = requests.get(
                url,
                params={
                    "symbol": symbol,
                    "interval": "1m",
                    "startTime": start_ms,
                    "limit": 1000,
                },
                timeout=30,
                )
            except requests.Timeout:
                print(f'timeout {symbol}')
                continue
            except requests.exceptions.ConnectionError:
                print(f'lost connection {symbol}')
                continue
            try:
                data.raise_for_status()
            except Exception as e:
                with open('errors.txt', 'a') as fp:
                    fp.write(f'{e} on {symbol}\n')
            data = [i[:-1] for i in data.json()]
            rows.extend(data)

            last_ms = data[-1][0]
            bar.update(len(data))
            bar.set_postfix_str(pd.to_datetime(last_ms, unit="ms", utc=True).strftime("%Y-%m-%d %H:%M"))

            start_ms = last_ms + 60_000

            if len(data) < 1000:
                break

    df = pd.DataFrame(rows, columns=[
        "time",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "close_time",
        "quote_volume",
        "trades",
        "taker_buy_volume",
        "taker_buy_quote_volume",
    ])
    
    df["time"] = pd.to_datetime(df["time"], unit="ms", utc=True)
    df = df.set_index("time").drop(columns=['close_time'])
    df = df.astype({"open": "float32", 'high': 'float32', 'low': 'float32', 'close': 'float32', 'volume': 'float32', 
                    'quote_volume': "float32", 'trades': 'uint32', 'taker_buy_volume': 'float32', 'taker_buy_quote_volume': 'float32'})
    return df[~df.index.duplicated(keep="last")]

def download_all_crypto_1m(path: str = "crypto_1m", start='2026-09-05') -> None:
    base = "https://api.binance.com"
    out = Path(path)
    out.mkdir(exist_ok=True)

    session = requests.Session()

    info = session.get(f"{base}/api/v3/exchangeInfo", timeout=30).json()

    symbols = [
        x["symbol"]
        for x in info["symbols"]
        if x["status"] == "TRADING"
        and x["quoteAsset"] == "USDT"
    ]

    for n, symbol in enumerate(symbols, 1):
        if (out / f'{symbol}.xz').exists(): continue
        download_binance_1m(symbol, start).to_pickle(out / f'{symbol}.xz', compression="xz")

download_all_crypto_1m(start='2012-01-01')