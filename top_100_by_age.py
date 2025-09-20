import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

# Load NYSE-listed companies (update path/URL if needed)
df_nyse = pd.read_csv("https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt", sep="|")

# Remove last summary row if present
if "File Creation Time" in df_nyse.columns:
    df_nyse = df_nyse.iloc[:-1]

# Apply filters if columns exist
if "ETF" in df_nyse.columns:
    df_nyse = df_nyse[df_nyse["ETF"] == "N"]

if "Test Issue" in df_nyse.columns:
    df_nyse = df_nyse[df_nyse["Test Issue"] == "N"]

# Define cutoff (1 year ago)
one_year_ago = datetime.now() - timedelta(days=365)

valid_tickers = []

for ticker in df_nyse["Symbol"]:
    try:
        stock = yf.Ticker(ticker)
        ipo_date_str = stock.info.get("firstTradeDateEpochUtc")
        if ipo_date_str:
            ipo_date = datetime.utcfromtimestamp(ipo_date_str)
            if ipo_date < one_year_ago:
                valid_tickers.append(ticker)
    except Exception as e:
        print(f"Skipping {ticker}: {e}")

# Save filtered tickers
output_file = "nyse_tickers_older_than_1_year.csv"
pd.DataFrame(valid_tickers, columns=["Symbol"]).to_csv(output_file, index=False)

print(f"Filtered tickers saved to {output_file}. Total: {len(valid_tickers)}")

