# update_cashflow_from_alpaca.py

import os
import pandas as pd
#from alpaca.trading.client import TradingClient
from alpaca_trade_api.rest import REST
#from alpaca.broker.client import BrokerClient
#from alpaca.broker.models import GetAccountActivitiesRequest
#import alpaca_trade_api as tradeapi
from datetime import datetime
from dotenv import load_dotenv

# 🔑 Load .env file
load_dotenv("/home/dave/Stock_app/.env")

API_KEY = os.getenv("ALPACA_API_KEY")
API_SECRET = os.getenv("ALPACA_SECRET_KEY")
BASE_URL = os.getenv("ALPACA_PAPER_BASE_URL")


# Path to your cashflow log
CASHFLOW_FILE = "/home/dave/Stock_app/cashflow.csv"

def update_cashflow_from_alpaca():
    api = REST(API_KEY, API_SECRET, BASE_URL, api_version='v2')
    # Fetch all closed (filled) orders
    orders = api.list_orders(status="closed", limit=500)  # adjust limit as needed

    records = []
    for o in orders:
        # Only include BUY/SELL trades
        if o.side.lower() not in ["buy", "sell"]:
            continue

        records.append({
            "Date": pd.to_datetime(o.filled_at).date(),
            "Type": o.side.upper(),          # BUY or SELL
            "Amount": float(o.filled_avg_price) * float(o.filled_qty),
            "Notes": f"Trade {o.symbol}"
        })

    df_new = pd.DataFrame(records)

    if os.path.exists(CASHFLOW_FILE):
        df_existing = pd.read_csv(CASHFLOW_FILE, parse_dates=["Date"])
    else:
        df_existing = pd.DataFrame(columns=["Date", "Type", "Amount", "Notes"])

    df_all = pd.concat([df_existing, df_new], ignore_index=True)
    df_all.drop_duplicates(subset=["Date", "Type", "Amount", "Notes"], inplace=True)

    df_all.to_csv(CASHFLOW_FILE, index=False)
    print(f"✅ Cashflow updated: {len(df_new)} new entries added")

    return df_all


if __name__ == "__main__":
    update_cashflow_from_alpaca()

