# sell_executor.py

import pandas as pd
import os
import json
import logging
from datetime import datetime
from dotenv import load_dotenv
import alpaca_trade_api as tradeapi


load_dotenv()

logging.basicConfig(filename="logs/sell_executor.log", level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

API_KEY = os.getenv("ALPACA_API_KEY")
API_SECRET = os.getenv("ALPACA_SECRET_KEY")
BASE_URL = os.getenv("ALPACA_PAPER_BASE_URL")
api = tradeapi.REST(API_KEY, API_SECRET, BASE_URL)

with open("config.json") as f:
    config = json.load(f)

TRADE_AMOUNT_USD = float(config.get("trade_amount", 30))
MIN_SCORE = float(config.get("min_signal_strength", 0.7))
HOLD_DAYS = int(config.get("hold_days", 3))

def has_held_long_enough(ticker, now, hold_days):
    history_file = "trade_log.csv"
    if not os.path.exists(history_file):
        return True  # No data = assume ok

    df = pd.read_csv(history_file)
    df = df[(df["Ticker"] == ticker) & (df["Action"].str.upper() == "BUY")]
    if df.empty:
        return True  # No buys = assume ok

    last_buy_time = max(pd.to_datetime(df["Timestamp"]))
    days_held = (now - last_buy_time).days
    return days_held >= hold_days

def execute_sells():
    try:
        df = pd.read_csv("predictions.csv")
        df = df[df['Signal'].str.lower().str.strip() == 'sell']
        logger.info(f"Processing {len(df)} sell signals.")

        for _, row in df.iterrows():
            ticker = row['Ticker']
            score = float(row.get("Score", 0))

            if score < MIN_SCORE:
                logger.info(f"Skipping {ticker}: score {score} < min {MIN_SCORE}")
                continue

            now = datetime.now()
            if not has_held_long_enough(ticker, now, HOLD_DAYS):
                logger.info(f"Skipping {ticker}: not held long enough ({HOLD_DAYS} days)")
                continue

            try:
                position = api.get_position(ticker)
                qty = float(position.qty)

                if qty <= 0:
                    logger.info(f"No position to sell for {ticker}")
                    continue

                api.submit_order(
                    symbol=ticker,
                    qty=qty,
                    side='sell',
                    type='market',
                    time_in_force='day'
                )
                logger.info(f"SELL {qty} {ticker}")

            except tradeapi.rest.APIError:
                logger.info(f"No open position found for {ticker}, skipping.")
            except Exception as e:
                logger.error(f"Error selling {ticker}: {e}")

    except Exception as e:
        logger.error(f"Critical error in sell_executor: {e}")

if __name__ == "__main__":
    execute_sells()

