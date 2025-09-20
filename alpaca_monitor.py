import os
import time
from datetime import datetime
import pandas as pd
import alpaca_trade_api as tradeapi
from dotenv import load_dotenv

# Load environment
load_dotenv()
# Alpaca API
API_KEY = os.getenv("ALPACA_API_KEY")
API_SECRET = os.getenv("ALPACA_SECRET_KEY")
BASE_URL = os.getenv("ALPACA_PAPER_BASE_URL")
api = tradeapi.REST(API_KEY, API_SECRET, BASE_URL, api_version='v2')

# Stocks to monitor
symbols = ["BABA", "RDDT", "WDAY", "SNDK"]

# File paths
daily_file = "stock_data/stocks_{date}.csv"
weekly_file = "stock_data/stocks_{week}.csv"


def ensure_dir(path):
    """Ensure the directory exists."""
    os.makedirs(os.path.dirname(path), exist_ok=True)


def append_to_csv(path, df):
    """Append to CSV safely, writing header if file is new/empty."""
    ensure_dir(path)
    write_header = not os.path.exists(path) or os.path.getsize(path) == 0
    df.to_csv(path, mode="a", header=write_header, index=False)


def load_csv(path):
    """Load CSV defensively. Return empty DataFrame if missing/empty."""
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return pd.DataFrame(columns=["Datetime", "Symbol", "Price", "Volume"])
    try:
        return pd.read_csv(path, parse_dates=["Datetime"])
    except Exception as e:
        print(f"⚠️ Could not read {path}: {e}")
        return pd.DataFrame(columns=["Datetime", "Symbol", "Price", "Volume"])


def monitor_loop():
    """Fetch latest quotes every minute and save to CSVs."""
    while True:
        now = datetime.now()

        # Build file names
        daily_path = daily_file.format(date=now.strftime("%Y%m%d"))
        week_start = now.strftime("%Y%m%d")  # could also anchor to Monday
        weekly_path = weekly_file.format(week=week_start)

        for symbol in symbols:
            try:
                barset = api.get_bars(symbol, "1Min", limit=1)
                if not barset:
                    print(f"⚠️ No data returned for {symbol}")
                    continue
                bar = barset[0]

                row = {
                    "Datetime": now,
                    "Symbol": symbol,
                    "Price": bar.c,
                    "Volume": bar.v,
                }

                df = pd.DataFrame([row])

                append_to_csv(daily_path, df)
                append_to_csv(weekly_path, df)

                print(f"📈 {symbol} {bar.c} @ {now}")

            except Exception as e:
                print(f"Error fetching {symbol}: {e}")

        # Sleep until next minute
        time.sleep(60)


if __name__ == "__main__":
    monitor_loop()

