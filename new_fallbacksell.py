import os
import json
import logging
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
import alpaca_trade_api as tradeapi
from utils.trade_logger import log_trade
from email_notifier import send_email

load_dotenv()

log_file = "logs/fallback_sell_executor.log"
os.makedirs(os.path.dirname(log_file), exist_ok=True)
logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger()

API_KEY = os.getenv("ALPACA_API_KEY")
API_SECRET = os.getenv("ALPACA_SECRET_KEY")
BASE_URL = os.getenv("ALPACA_PAPER_BASE_URL")
api = tradeapi.REST(API_KEY, API_SECRET, BASE_URL, api_version="v2")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

with open(CONFIG_PATH) as f:
    config = json.load(f)

HOLD_DAYS = int(config.get("hold_days", 3))
portfolio_file = "portfolio.csv"


def has_held_long_enough(ticker, now, hold_days):
    history_file = "trade_log.csv"
    if not os.path.exists(history_file):
        return True
    df = pd.read_csv(history_file)
    df = df[(df["Ticker"] == ticker) & (df["Action"].str.upper() == "BUY")]
    if df.empty:
        return True
    last_buy_time = max(pd.to_datetime(df["Timestamp"]))
    return (now - last_buy_time).days >= hold_days


def execute_fallback_sells():
    trades_executed = []
    try:
        portfolio = pd.read_csv(portfolio_file)
        for _, row in portfolio.iterrows():
            ticker = row["Ticker"]
            avg_cost = float(row["Average Cost"])

            try:
                position = api.get_position(ticker)
                shares = float(position.qty)
            except tradeapi.rest.APIError:
                shares = 0

            if shares <= 0:
                logger.info(f"Fallback skipped for {ticker}: no position held.")
                continue

            if not has_held_long_enough(ticker, datetime.now(), HOLD_DAYS):
                logger.info(f"Fallback skipped for {ticker}: not held long enough.")
                continue

            current_price = float(api.get_latest_trade(ticker).price)
            gain = (current_price - avg_cost) / avg_cost

            if gain < 0.02:  # < +2% gain after HOLD_DAYS
                logger.info(
                    f"⚠️ FALLBACK SELL: {ticker} held {HOLD_DAYS}+ days, gain {gain:.2%} (<2%). Selling FULL position."
                )
                sell_qty = round(shares - 1e-6, 4)

            elif current_price < avg_cost:  # losing trade
                logger.info(
                    f"⚠️ FALLBACK SELL: {ticker} is below cost ({current_price:.2f} < {avg_cost:.2f}). Selling FULL position."
                )
                sell_qty = round(shares - 1e-6, 4)

            else:
                logger.info(f"Fallback skipped for {ticker}: gain {gain:.2%}, no trigger.")
                continue

            try:
                api.submit_order(
                    symbol=ticker,
                    qty=sell_qty,
                    side="sell",
                    type="market",
                    time_in_force="day"
                )
                trades_executed.append(f"Fallback SELL {sell_qty} {ticker}")
                logger.info(f"✅ FALLBACK SELL {sell_qty} {ticker} at {current_price:.2f}")
                log_trade(ticker, "FALLBACK_SELL", sell_qty, current_price, score=None)

            except Exception as e:
                logger.error(f"Fallback SELL failed for {ticker}: {e}")
                continue

    except Exception as e:
        logger.error(f"Error during fallback sell logic: {e}")

    if trades_executed:
        subject = f"Fallback Sell Trades - {datetime.today().date()}"
        body = "\n".join(trades_executed)
    else:
        subject = f"No Fallback Sells - {datetime.today().date()}"
        body = "No fallback sells were made today."

    send_email(subject, body)


if __name__ == "__main__":
    logger.info("▶️ Starting Fallback Sell Executor")
    execute_fallback_sells()
    logger.info("✅ Fallback Sell Executor finished")

