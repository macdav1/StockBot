import alpaca_trade_api as tradeapi
import pandas as pd
import datetime
import os

# Load keys from your saved file for extra safety
key_file_path = '/home/dave/Stock_app/alpaca_keys.txt'

with open(key_file_path, 'r') as f:
    lines = f.readlines()
    API_KEY = lines[0].strip()
    API_SECRET = lines[1].strip()

BASE_URL = 'https://paper-api.alpaca.markets'

api = tradeapi.REST(API_KEY, API_SECRET, BASE_URL, api_version='v2')

# Read today's predictions
predictions_path = '/home/dave/predictions.csv'

if not os.path.exists(predictions_path):
    print("No predictions found. Exiting.")
    exit()

predictions = pd.read_csv(predictions_path)

# Filter today's predictions only
today = datetime.date.today().strftime("%Y-%m-%d")
today_preds = predictions[predictions['Date'] == today]

if today_preds.empty:
    print("No predictions for today. Exiting.")
    exit()

# Loop through today's predictions
for index, row in today_preds.iterrows():
    ticker = row['Ticker']
    prediction = row['Prediction']

    # Skip non-US tickers (ASX stocks)
    if '.AX' in ticker:
        print(f"Skipping {ticker} (non-US)")
        continue

    try:
        position = api.get_position(ticker)
        print(f"Already holding {ticker}, qty: {position.qty}")
    except:
        position = None

    if prediction == 'Up':
        if not position:
            print(f"Placing BUY order for {ticker}")
            api.submit_order(
                symbol=ticker,
                qty=1,
                side='buy',
                type='market',
                time_in_force='gtc'
            )
        else:
            print(f"Already holding {ticker}, skipping buy.")
    elif prediction == 'Down':
        if position:
            print(f"Placing SELL order for {ticker}")
            api.submit_order(
                symbol=ticker,
                qty=position.qty,
                side='sell',
                type='market',
                time_in_force='gtc'
            )
        else:
            print(f"Not holding {ticker}, skipping sell.")

