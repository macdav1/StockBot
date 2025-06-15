import pandas as pd
import alpaca_trade_api as tradeapi
import os
import logging
from dotenv import load_dotenv

load_dotenv()

# Setup logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
fh = logging.FileHandler("logs/trading.log")
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
logger.addHandler(fh)

# Alpaca credentials
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
ALPACA_BASE_URL = os.getenv("ALPACA_PAPER_BASE_URL")

api = tradeapi.REST(ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_BASE_URL, api_version='v2')

BUY_THRESHOLD = 0.7
SELL_THRESHOLD = 0.3
TRADE_AMOUNT_USD = 1000

def execute_trades():
    trades_executed = []
    
    try:
        df = pd.read_csv("predictions.csv")
    except Exception as e:
        logger.error(f"Failed to load predictions: {e}")
        return trades_executed

    for _, row in df.iterrows():
        ticker = row['Ticker']
        score = row['Score']

        try:
            position_qty = 0
            try:
                position = api.get_position(ticker)
                position_qty = float(position.qty)
            except tradeapi.rest.APIError:
                position_qty = 0  # No position

            latest_price = float(api.get_latest_trade(ticker).price)
            qty = round(TRADE_AMOUNT_USD / latest_price, 4)

            if score >= BUY_THRESHOLD:
                api.submit_order(
                    symbol=ticker,
                    qty=qty,
                    side='buy',
                    type='market',
                    time_in_force='day'  # DAY required for fractional trades
                )
                trades_executed.append(f"BUY {qty} shares of {ticker} at {latest_price}")
                logger.info(f"BUY {qty} shares of {ticker} at {latest_price}")

            elif score <= SELL_THRESHOLD:
                if position_qty > 0:
                    sell_qty = min(position_qty, qty)
                    api.submit_order(
                        symbol=ticker,
                        qty=sell_qty,
                        side='sell',
                        type='market',
                        time_in_force='day'
                    )
                    trades_executed.append(f"SELL {sell_qty} shares of {ticker} at {latest_price}")
                    logger.info(f"SELL {sell_qty} shares of {ticker} at {latest_price}")
                else:
                    logger.warning(f"Skipping SELL for {ticker} due to zero holdings (wash trade prevention).")
            else:
                logger.info(f"No trade for {ticker} (Score: {score})")

        except tradeapi.rest.APIError as e:
            logger.error(f"Error trading {ticker}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error for {ticker}: {e}")

    logger.info("✅ Trade execution completed.")
    return trades_executed

