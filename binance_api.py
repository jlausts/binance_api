import pandas as pd, requests, time, pickle
from datetime import datetime, timezone
from pathlib import Path
from tqdm import tqdm

class CryptoBinance:

    def __init__(self, path: str = "crypto_1m"):
        self.base = "https://api.binance.com"
        self.output_folder = Path(path)
        self.output_folder.mkdir(exist_ok=True)
        self.session = requests.Session()

    def get_all_symbols(self, all_symbols=True):
        info = self.session.get(f"{self.base}/api/v3/exchangeInfo", timeout=30).json()
        if all_symbols:
            return [x["symbol"] for x in info["symbols"] if x["quoteAsset"] == "USDT"]
        else:
            return [
                x["symbol"]
                for x in info["symbols"]
                if x["status"] == "TRADING"
                and x["quoteAsset"] == "USDT"
            ]

    def download_one_ticker_1m(self, symbol: str = "BTCUSDT", start: str = "2026-09-05", use_tqdm=True) -> pd.DataFrame:
        url = "https://api.binance.com/api/v3/klines"
        start_ms = int(datetime.fromisoformat(start).replace(tzinfo=timezone.utc).timestamp() * 1000)
        end_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        rows = []

        total_minutes = max((end_ms - start_ms) // 60_000, 1)

        if use_tqdm:
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
                        }, timeout=30)
                    except requests.Timeout:
                        print(f'timeout {symbol}')
                        continue
                    except requests.exceptions.ConnectionError:
                        print(f'lost connection {symbol}')
                        continue
                    try:
                        data.raise_for_status()
                    except Exception as e:
                        print(f'{e} for {symbol}')
                    data = [i[:-1] for i in data.json()]
                    rows.extend(data)
                    last_ms = data[-1][0]

                    bar.update(len(data))
                    bar.set_postfix_str(pd.to_datetime(last_ms, unit="ms", utc=True).strftime("%Y-%m-%d %H:%M"))

                    start_ms = last_ms + 60_000

                    if len(data) < 1000:
                        break   
        else:
            while True:
                try:
                    data = requests.get(
                    url,
                    params={
                        "symbol": symbol,
                        "interval": "1m",
                        "startTime": start_ms,
                        "limit": 1000,
                    }, timeout=30)
                except requests.Timeout:
                    print(f'timeout {symbol}')
                    continue
                except requests.exceptions.ConnectionError:
                    print(f'lost connection {symbol}')
                    continue
                try:
                    data.raise_for_status()
                except Exception as e:
                    print(f'{e} on {symbol}\n')
                data = [i[:-1] for i in data.json()]
                rows.extend(data)
                last_ms = data[-1][0]

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

    def download_all_crypto_1m(self, start='2026-09-05') -> None:
        for n, symbol in enumerate(self.get_all_symbols(), 1):
            if (self.output_folder / f'{symbol}.xz').exists(): continue
            self.download_one_ticker_1m(symbol, start).to_pickle(self.output_folder / f'{symbol}.xz', compression="xz")

    def get_snapshot(self):
        joiner = '","'
        base = f"{self.base}/api/v3"
        symbols = self.get_all_symbols()

        data = requests.get(f'{base}/ticker/price?symbols=["{joiner.join(symbols)}"]', timeout=30).json()
        return pd.DataFrame(data).set_index('symbol').astype({'price': 'float32'})

    def save_snapshot(self):
        date = Path('snapshots') / pd.to_datetime(time.time(), unit='s').strftime("%Y-%M-%d")
        date.mkdir(exist_ok=True, parents=True)
        ts = (date / pd.to_datetime(time.time(), unit='s').strftime("%H_%M")).with_suffix('.xz')
        self.get_snapshot().to_pickle(ts)

    def update_one_ticker(self, symbol: Path, use_tqdm=False):
            if symbol.name.startswith('_'): return
            df = pd.read_pickle(symbol)
            start = df.iloc[-1].name.strftime('%Y-%m-%d')
            df = pd.concat([df, self.download_one_ticker_1m(symbol.stem, start, use_tqdm=use_tqdm)])
            df[~df.index.duplicated(keep="last")].to_pickle(symbol)

    def update_all_crypto_1m(self) -> None:
        for symbol in tqdm(list(self.output_folder.iterdir())):
            self.update_one_ticker(symbol)

    def ffill_crypto_data(self):
        dfs: dict[str, pd.DataFrame] = {i.stem: pd.read_pickle(i) for i in tqdm(list(self.output_folder.iterdir()))}

        for ind, df in tqdm(dfs.items()):
            dfs[ind] = df[['open', 'high', 'low', 'close']].reindex(pd.date_range(df.index[0], df.index[-1], freq="1min")).ffill()

        with open('ffilled_crypto.pkl', 'wb') as fp:
            pickle.dump(dfs, fp)

