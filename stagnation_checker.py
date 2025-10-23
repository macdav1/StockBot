import os
import json
import pandas as pd
import datetime as dt
from dotenv import load_dotenv
import alpaca_trade_api as tradeapi
from alpaca_trade_api.rest import REST, TimeFrame
from utils.holding import has_held_long_enough

load_dotenv()

API_KEY = os.getenv("ALPACA_API_KEY")
API_SECRET = os.getenv("ALPACA_SECRET_KEY")
BASE_URL = os.getenv("ALPACA_PAPER_BASE_URL")
api = tradeapi.REST(API_KEY, API_SECRET, BASE_URL, api_version="v2")

# Load config
with open("config.json") as f:
    config = json.load(f)

HOLD_DAYS = config.get("hold_days", 7)  # default to 7 if not in config

def is_stagnant(ticker, days=7, threshold=0.02):
    """
    Check if a stock's price has stagnated.
    """
    end = dt.datetime.now().date()
    start = end - dt.timedelta(days=days*2)  # buffer for weekends/holidays

    # Alpaca daily bars only need YYYY-MM-DD
    bars = api.get_bars(
        ticker,
        TimeFrame.Day,
        start.isoformat(),
        end.isoformat(),
        feed="iex"
    ).df

    if bars.empty or len(bars) < days:
        return False  # not enough data

    recent = bars.tail(days)
    high, low = recent['close'].max(), recent['close'].min()
    pct_range = (high - low) / low

    return pct_range < threshold




def check_portfolio_stagnation(portfolio_path="portfolio.csv", days=7, threshold=0.02):
    """
    Check all portfolio stocks for stagnation.

    Args:
        portfolio_path (str): Path to portfolio.csv
        days (int): Days to check for stagnation
        threshold (float): Price movement threshold

    Returns:
        stagnant_stocks (list): Tickers flagged as stagnant
    """
    df = pd.read_csv(portfolio_path)
    stagnant = []

    for _, row in df.iterrows():
        ticker = row["Ticker"]
        pl = row.get("P/L($)", 0)

        # Skip if not held long enough
        if not has_held_long_enough(ticker, dt.datetime.now(), HOLD_DAYS):
            continue

        if pl > 0 and is_stagnant(ticker, days=days, threshold=threshold):
            stagnant.append(ticker)

    return stagnant


if __name__ == "__main__":
    ##print(f"- {BASE_URL}")
    stagnant_stocks = check_portfolio_stagnation()
    if stagnant_stocks:
        print("📉 Stagnant stocks to consider for fallback sales:")
        for t in stagnant_stocks:
            print(f"- {t}")
    else:
        print("✅ No stagnant stocks detected.")

