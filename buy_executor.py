import os
import json
import logging
import pandas as pd
import datetime
from dotenv import load_dotenv
import alpaca_trade_api as tradeapi
from email_notifier import send_email  # Make sure this module exists

# Load environment
load_dotenv()

# Logging
log_file = "logs/buy_executor.log"
os.makedirs(os.path.dirname(log_file), exist_ok=True)

logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger()

# Alpaca API
API_KEY = os.getenv("ALPACA_API_KEY")
API_SECRET = os.getenv("ALPACA_SECRET_KEY")
BASE_URL = os.getenv("ALPACA_PAPER_BASE_URL")
api = tradeapi.REST(API_KEY, API_SECRET, BASE_URL, api_version='v2')

# Config
with open("config.json") as f:
    config = json.load(f)

TRADE_AMOUNT_USD = float(config.get("trade_amount", 30))
MIN_SCORE = float(config.get("min_signal_strength", 0.7))
MAX_POSITION_VALUE = float(config.get("max_position_value", 200))

def execute_buys():
    trades_executed = []

    try:
        df = pd.read_csv("predictions.csv")
        df = df[df['Signal'].str.strip().str.lower() == 'buy']
        logger.info(f"Loaded {len(df)} buy signals.")

        for _, row in df.iterrows():
            ticker = row['Ticker'].strip().upper()
            score = float(row.get("Score", 0))

            if score < MIN_SCORE:
                logger.info(f"Skipping {ticker}: score {score} below threshold {MIN_SCORE}")
                continue

            try:
                # Get current position
                try:
                    position = api.get_position(ticker)
                    position_qty = float(position.qty)
                except tradeapi.rest.APIError:
                    position_qty = 0

                latest_price = float(api.get_latest_trade(ticker).price)
                asset = api.get_asset(ticker)

                # Determine qty
                if asset.fractionable:
                    qty = round(TRADE_AMOUNT_USD / latest_price, 4)
                else:
                    qty = int(TRADE_AMOUNT_USD // latest_price)
                    if qty == 0:
                        logger.info(f"Skipping {ticker}: not fractionable and insufficient funds.")
                        continue

                # Skip if already holding over limit
                current_value = position_qty * latest_price
                if current_value >= MAX_POSITION_VALUE:
                    logger.info(f"Skipping BUY for {ticker}: holding ${current_value:.2f}, exceeds max allowed.")
                    continue

                # Place order
                api.submit_order(
                    symbol=ticker,
                    qty=qty,
                    side='buy',
                    type='market',
                    time_in_force='day'
                )
                logger.info(f"BUY {qty} shares of {ticker} at ${latest_price:.2f}")
                trades_executed.append(f"BUY {qty} {ticker} @ ${latest_price:.2f} (Score: {score:.2f})")

            except Exception as e:
                logger.error(f"❌ Failed to buy {ticker}: {e}")

    except Exception as e:
        logger.error(f"❌ Failed to execute buy logic: {e}")

    # Email results
    if trades_executed:
        subject = f"Buy Trades Executed - {datetime.date.today()}"
        body = "\n".join(trades_executed)
    else:
        subject = f"No Buy Trades Executed - {datetime.date.today()}"
        body = "No trades met the criteria today."

    send_email(subject, body)
    return trades_executed


if __name__ == "__main__":
    logger.info("▶️ Starting Buy Executor")
    execute_buys()
    logger.info("✅ Buy Executor finished")

