# order_executor.py

import alpaca_trade_api as tradeapi
import pandas as pd
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get API credentials from .env
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
ALPACA_PAPER_URL = os.getenv("ALPACA_PAPER_URL")

# Connect to Alpaca paper trading account
api = tradeapi.REST(ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_PAPER_URL, api_version='v2')

def execute_trades(signals_file='signals.csv'):
    df = pd.read_csv(signals_file)

    for index, row in df.iterrows():
        symbol = row['Ticker']
        action = row['Action']

        if action == 'BUY':
            qty = 1
            print(f"[DRY-RUN] Would BUY {qty} share(s) of {symbol}")
            # api.submit_order(symbol=symbol, qty=qty, side='buy', type='market', time_in_force='gtc')
        elif action == 'SELL':
            qty = 1
            print(f"[DRY-RUN] Would SELL {qty} share(s) of {symbol}")
            # api.submit_order(symbol=symbol, qty=qty, side='sell', type='market', time_in_force='gtc')
        else:
            print(f"No action for {symbol}")

    print("✅ Trade execution simulation complete (DRY RUN)")

