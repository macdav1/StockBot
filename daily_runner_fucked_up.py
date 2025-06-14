import subprocess
import os
import datetime
import pandas as pd
import alpaca_trade_api as tradeapi
from email_notifier import send_email  # your existing email module

# Paths
project_dir = '/home/dave/Stock_app'
predictions_file = os.path.join(project_dir, 'predictions.csv')
alpaca_keys_file = os.path.join(project_dir, 'alpaca_keys.txt')

def main():
    # STEP 1: Run stock predictor
    print("Running stock predictor...")
    subprocess.run(['python3', os.path.join(project_dir, 'stock_predictor.py')])

    # STEP 2: Run backtester
    print("Running backtest...")
    subprocess.run(['python3', os.path.join(project_dir, 'backtest_runner.py')])

    # STEP 3: Load today's predictions
    if not os.path.exists(predictions_file):
        print("No predictions found. Exiting trading step.")
        send_email(f"StockBot Daily Run - {datetime.date.today()}",
                   "No predictions file found. Daily run stopped.")
        return

    predictions = pd.read_csv(predictions_file)
    today = datetime.date.today().strftime("%Y-%m-%d")
    today_preds = predictions[predictions['Date'] == today]

    if today_preds.empty:
        print("No predictions for today. Exiting trading step.")
        send_email(f"StockBot Daily Run - {datetime.date.today()}",
                   "No predictions for today. Daily run stopped.")
        return

    # STEP 4: Setup Alpaca trading
    with open(alpaca_keys_file, 'r') as f:
        lines = f.readlines()
        API_KEY = lines[0].strip()
        API_SECRET = lines[1].strip()

    BASE_URL = 'https://paper-api.alpaca.markets'
    api = tradeapi.REST(API_KEY, API_SECRET, BASE_URL, api_version='v2')

    # STEP 5: Process predictions for trading
    print("Processing today's trades...")

    trade_summary = []

    for index, row in today_preds.iterrows():
        ticker = row['Ticker']
        prediction = row['Prediction']

        if '.AX' in ticker:
            print(f"Skipping {ticker} (non-US stock)")
            trade_summary.append(f"Skipped {ticker} (non-US stock)")
            continue

        try:
            position = api.get_position(ticker)
            current_qty = int(position.qty)
            print(f"Already holding {ticker}: {current_qty} shares")
        except:
            current_qty = 0

        if prediction == 'Up' and current_qty == 0:
            print(f"Placing BUY order for {ticker}")
            api.submit_order(
                symbol=ticker,
                qty=1,
                side='buy',
                type='market',
                time_in_force='gtc'
            )
            trade_summary.append(f"BUY order placed for {ticker}")
        elif prediction == 'Down' and current_qty > 0:
            print(f"Placing SELL order for {ticker}")
            api.submit_order(
                symbol=ticker,
                qty=current_qty,
                side='sell',
                type='market',
                time_in_force='gtc'
            )
            trade_summary.append(f"SELL order placed for {ticker}")
        else:
            print(f"No action for {ticker}")
            trade_summary.append(f"No action for {ticker}")

    # Compose email report body
    email_body = "Daily Run Completed:\n\n"
    email_body += "Stock Predictor and Backtester ran successfully.\n\n"
    email_body += "Trading Summary:\n"
    email_body += "\n".join(trade_summary)

    # Send summary email
    send_email(f"StockBot Daily Run - {datetime.date.today()}", email_body)

    print("Daily run completed successfully!")

if __name__ == "__main__":
    main()

