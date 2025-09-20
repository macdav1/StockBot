import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import time
import json
import os

# --- CONFIG ---
CACHE_FILE = "nyse_ipo_cache.json"
OUTPUT_FILE = "nyse_tickers_older_than_1_year.csv"
ONE_YEAR_AGO = datetime.now() - timedelta(days=365)

# --- Load NYSE tickers ---
print("Loading NYSE tickers...")
nyse_url = "https://raw.githubusercontent.com/datasets/nyse-listings/master/data/nyse-listed.csv"
df_nyse = pd.read_csv(nyse_url)
tickers = df_nyse['ACT Symbol'].tolist()
print(f"Total tickers found: {len(tickers)}")

# --- Load cache ---
if os.path.exists(CACHE_FILE):
    with open(CACHE_FILE, 'r') as f:
        ipo_cache = json.load(f)
else:
    ipo_cache = {}

filtered_tickers = []

# --- Process tickers ---
for i, ticker in enumerate(tickers, start=1):
    print(f"[{i}/{len(tickers)}] Checking {ticker}...")
    
    # Check cache first
    if ticker in ipo_cache:
        ipo_date_str = ipo_cache[ticker]
    else:
        try:
            info = yf.Ticker(ticker).info
            ipo_date_str = info.get('ipoDate') or None
            # Some tickers return firstTradeDateEpochUtc
            if not ipo_date_str and 'firstTradeDateEpochUtc' in info:
                ipo_date_str = datetime.fromtimestamp(info['firstTradeDateEpochUtc']).strftime("%Y-%m-%d")
            ipo_cache[ticker] = ipo_date_str
            # Save cache periodically
            if i % 50 == 0:
                with open(CACHE_FILE, 'w') as f:
                    json.dump(ipo_cache, f)
        except Exception as e:
            print(f"  Error fetching {ticker}: {e}")
            ipo_cache[ticker] = None
            ipo_date_str = None

    if ipo_date_str:
        try:
            ipo_date = datetime.strptime(ipo_date_str, "%Y-%m-%d")
            if ipo_date <= ONE_YEAR_AGO:
                filtered_tickers.append(ticker)
        except Exception as e:
            print(f"  Could not parse IPO date for {ticker}: {ipo_date_str}")

# Save final filtered list
pd.DataFrame(filtered_tickers, columns=['Ticker']).to_csv(OUTPUT_FILE, index=False)
print(f"Filtered tickers saved to {OUTPUT_FILE}. Total: {len(filtered_tickers)}")

