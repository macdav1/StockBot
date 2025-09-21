import os
import time
import logging
from datetime import datetime
import pandas as pd
from dotenv import load_dotenv
from alpaca_trade_api.rest import REST

# === Setup logger ===
log_path = "/home/dave/Stock_app/logs/get_top_stocks.log"
logger = logging.getLogger("get_top_stocks")
logger.setLevel(logging.INFO)
if logger.hasHandlers():
    logger.handlers.clear()
file_handler = logging.FileHandler(log_path, mode='a')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)

# === Load API keys ===
load_dotenv()
API_KEY = os.getenv("ALPACA_API_KEY")
API_SECRET = os.getenv("ALPACA_SECRET_KEY")
BASE_URL = os.getenv("ALPACA_PAPER_BASE_URL")
rest_api = REST(API_KEY, API_SECRET, base_url=BASE_URL)

def get_top_stocks():
    logger.info("🔍 Getting active stock list...")
    try:
        assets = rest_api.list_assets(status="active")
        tradable_stocks = [
            a.symbol for a in assets
            if a.tradable and a.exchange in ["NASDAQ", "NYSE"]
        ]
        logger.info(f"✅ Found {len(tradable_stocks)} tradable stocks.")
    except Exception as e:
        logger.error(f"❌ Error fetching assets: {e}")
        return

    logger.info("🔍 Fetching snapshot data to rank stocks by dollar volume...")
    bar_data = []
    for symbol in tradable_stocks:
        try:
            snapshot = rest_api.get_snapshot(symbol)
            if snapshot and snapshot.daily_bar:
                volume = snapshot.daily_bar.volume
                close = snapshot.daily_bar.close
                bar_data.append((symbol, volume, close))
            else:
                logger.warning(f"⚠️ No daily bar data for {symbol}")
            time.sleep(0.25)  # Respect rate limits
        except Exception as e:
            logger.warning(f"⚠️ Error fetching snapshot for {symbol}: {e}")
            continue

    if not bar_data:
        logger.error("❌ No snapshot data collected.")
        return

    df = pd.DataFrame(bar_data, columns=["Symbol", "Volume", "Close"])
    df["DollarVolume"] = df["Volume"] * df["Close"]
    df = df.sort_values(by="DollarVolume", ascending=False)

    top_100 = df.head(100)
    top_10 = top_100.head(10)

    # Save top 100
    with open("top_100_stocks.txt", "w") as f:
        for symbol in top_100["Symbol"]:
            f.write(symbol + "\n")
    logger.info(f"📁 top_100_stocks.txt updated with: {top_100['Symbol'].tolist()}")

    # Save top 10 for daily predictions
    with open("daily_stocks.txt", "w") as f:
        for symbol in top_10["Symbol"]:
            f.write(symbol + "\n")
    logger.info(f"📁 daily_stocks.txt updated with: {top_10['Symbol'].tolist()}")

# === Allow command-line execution ===
if __name__ == "__main__":
    get_top_stocks()

