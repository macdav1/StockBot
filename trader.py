import os
import pandas as pd
import alpaca_trade_api as tradeapi
from dotenv import load_dotenv
import time

# Load env variables
load_dotenv()

API_KEY = os.getenv("ALPACA_API_KEY")
API_SECRET = os.getenv("ALPACA_SECRET_KEY")
BASE_URL = os.getenv("ALPACA_PAPER_BASE_URL")

TRADE_AMOUNT = float(os.getenv("ALPACA_TRADE_AMOUNT", 1000))
MIN_CONFIDENCE = float(os.getenv("ALPACA_MIN_CONFIDENCE", 0.65))

api = tradeapi.REST(API_KEY, API_SECRET, BASE_URL, api_version='v2')

def execute_trade(ticker, action, confidence):
    try:
        market_data = api.get_latest_trade(ticker)
        price = market_data.price
        qty = round(TRADE_AMOUNT / price, 2)

        if action == "BUY":
            api.submit_order(symbol=ticker, qty=qty, side="buy", type="market", time_in_force="day")
        elif action == "SELL":
            api.submit_order(symbol=ticker, qty=qty, side="sell", type="market", time_in_force="day")

        log_trade(ticker, action, qty, price, confidence)
        print(f"Executed {action} {qty} shares of {ticker} at {price}")

        time.sleep(1)  # small delay to avoid hitting rate limits

    except Exception as e:
        print(f"Error trading {ticker}: {e}")

def log_trade(ticker, action, qty, price, confidence):
    log_exists = os.path.isfile("trade_log.csv")
    with open("trade_log.csv", "a") as f:
        if not log_exists:
            f.write("Date,Ticker,Action,Qty,Price,Confidence\n")
        f.write(f"{pd.Timestamp.now()},{ticker},{action},{qty},{price},{confidence}\n")

def run_trader():
    if not os.path.exists("predictions.csv"):
        print("No predictions file found.")
        return

    df = pd.read_csv("predictions.csv")
    trades_made = []

    for _, row in df.iterrows():
        ticker = row['Ticker']
        prediction = row['Prediction']
        confidence = float(row['Score'])

        if confidence >= MIN_CONFIDENCE:
            action = "BUY" if prediction == "Up" else "SELL"
            execute_trade(ticker, action, confidence)
            trades_made.append(f"{action} {ticker} (Confidence: {confidence})")

    return trades_made

