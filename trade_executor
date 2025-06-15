import os
import pandas as pd
import alpaca_trade_api as tradeapi
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()

ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
ALPACA_PAPER_BASE_URL = os.getenv("ALPACA_PAPER_BASE_URL")

BUY_THRESHOLD = float(os.getenv("BUY_THRESHOLD", 0.7))
SELL_THRESHOLD = float(os.getenv("SELL_THRESHOLD", 0.7))
TRADE_QTY = int(os.getenv("TRADE_QTY", 1))

# Initialize Alpaca API connection
api = tradeapi.REST(
    key_id=ALPACA_API_KEY,
    secret_key=ALPACA_SECRET_KEY,
    base_url=ALPACA_PAPER_BASE_URL
)

# Load today's predictions
PREDICTIONS_FILE = "predictions.csv"
TRADE_LOG_FILE = "trade_log.csv"

if not os.path.exists(PREDICTIONS_FILE):
    print("No predictions file found for today. Skipping trades.")
    exit()

predictions = pd.read_csv(PREDICTIONS_FILE)

# Prepare log file if it doesn't exist
if not os.path.exists(TRADE_LOG_FILE):
    pd.DataFrame(columns=["Timestamp", "Ticker", "Action", "Qty", "Score"]).to_csv(TRADE_LOG_FILE, index=False)

# Trading logic
for index, row in predictions.iterrows():
    ticker = row["Ticker"]
    prediction = row["Prediction"]
    score = row["Score"]

    try:
        if prediction == "Up" and score >= BUY_THRESHOLD:
            print(f"Buying {TRADE_QTY} shares of {ticker} (Score: {score})")
            api.submit_order(
                symbol=ticker,
                qty=TRADE_QTY,
                side="buy",
                type="market",
                time_in_force="day"
            )
            action = "BUY"
        elif prediction == "Down" and score >= SELL_THRESHOLD:
            print(f"Selling {TRADE_QTY} shares of {ticker} (Score: {score})")
            api.submit_order(
                symbol=ticker,
                qty=TRADE_QTY,
                side="sell",
                type="market",
                time_in_force="day"
            )
            action = "SELL"
        else:
            print(f"No trade for {ticker} (Score: {score})")
            action = "NO TRADE"

        # Append to log
        log_entry = pd.DataFrame([{
            "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Ticker": ticker,
            "Action": action,
            "Qty": TRADE_QTY if action != "NO TRADE" else 0,
            "Score": score
        }])
        log_entry.to_csv(TRADE_LOG_FILE, mode='a', header=False, index=False)

    except Exception as e:
        print(f"Error trading {ticker}: {e}")

print("✅ Trade execution completed.")

