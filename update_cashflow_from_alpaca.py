# update_cashflow_from_alpaca.py

import os
import pandas as pd
from alpaca.trading.client import TradingClient
from datetime import datetime
from dotenv import load_dotenv

# 🔑 Load .env file
load_dotenv("/home/dave/Stock_app/.env")

API_KEY = os.getenv("ALPACA_API_KEY")
API_SECRET = os.getenv("ALPACA_SECRET_KEY")
BASE_URL = os.getenv("ALPACA_PAPER_BASE_URL")
api = tradeapi.REST(API_KEY, API_SECRET, BASE_URL, api_version='v2')

# Path to your cashflow log
CASHFLOW_FILE = "/home/dave/Stock_app/cashflow.csv"

def update_cashflow_from_alpaca():
    client = TradingClient(API_KEY, API_SECRET, paper=True)

    try:
        history = client.get_funding_history()
    except Exception as e:
        print(f"⚠️ Could not fetch funding history: {e}")
        return

    records = []
    for h in history:
        if h.status != "completed":
            continue
        records.append({
            "Date": pd.to_datetime(h.created_at).date(),
            "Type": "DEPOSIT" if h.type == "deposit" else "WITHDRAWAL",
            "Amount": abs(float(h.amount)),  # Always positive
            "Notes": f"Auto-sync {h.type.capitalize()}"
        })

    df_new = pd.DataFrame(records)

    if os.path.exists(CASHFLOW_FILE):
        df_existing = pd.read_csv(CASHFLOW_FILE, parse_dates=["Date"])
    else:
        df_existing = pd.DataFrame(columns=["Date", "Type", "Amount", "Notes"])

    df_all = pd.concat([df_existing, df_new], ignore_index=True)
    df_all.drop_duplicates(subset=["Date", "Type", "Amount"], inplace=True)

    df_all.to_csv(CASHFLOW_FILE, index=False)
    print(f"✅ Cashflow updated: {len(df_new)} new entries added")

    return df_all


if __name__ == "__main__":
    update_cashflow_from_alpaca()

