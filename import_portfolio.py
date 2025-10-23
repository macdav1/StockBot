import alpaca_trade_api as tradeapi
import pandas as pd
import os
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables from .env
load_dotenv()

# --- CONFIGURATION ---
API_KEY = os.getenv("ALPACA_API_KEY")
API_SECRET = os.getenv("ALPACA_SECRET_KEY")

BASE_URL = os.getenv("ALPACA_PAPER_BASE_URL", "https://paper-api.alpaca.markets")
OUTPUT_FILE = "portfolio.csv"

def importportfolio():
    # --- CONNECT TO ALPACA ---
    api = tradeapi.REST(API_KEY, API_SECRET, BASE_URL, api_version='v2')

    # --- FETCH ACCOUNT POSITIONS ---
    positions = api.list_positions()

    # --- PROCESS DATA ---
    today = datetime.now().strftime("%Y-%m-%d")
    portfolio_data = []
    for p in positions:
        ticker = p.symbol
        shares = float(p.qty)
        avg_cost = float(p.avg_entry_price)
        current_price = float(p.current_price)
        pl = float(p.unrealized_pl)
        print(f"{p.symbol}:")
        print(f"  Today P/L %: {float(p.unrealized_intraday_plpc) * 100:.2f}%")
        print(f"  Total P/L %: {float(p.unrealized_plpc) * 100:.2f}%")
        portfolio_data.append([today, ticker, shares, avg_cost, current_price, pl])

    # --- CREATE DATAFRAME ---
    df = pd.DataFrame(portfolio_data, columns=["Date", "Ticker", "Shares", "Average Cost", "Current Price", "P/L($)"])

    # --- SAVE TO CSV (overwrite) ---
    df.to_csv(OUTPUT_FILE, index=False)
    print(f"✅ Portfolio saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    importportfolio()

