#!/usr/bin/env python3
import os
import csv
import requests
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

API_KEY = os.getenv("ALPACA_API_KEY")
API_SECRET = os.getenv("ALPACA_SECRET_KEY")
BASE_URL = os.getenv("ALPACA_PAPER_BASE_URL", "https://paper-api.alpaca.markets")

if not API_KEY or not API_SECRET:
    raise ValueError("❌ Missing API key or secret. Check your .env file.")

# Headers for Alpaca API
headers = {
    "APCA-API-KEY-ID": API_KEY,
    "APCA-API-SECRET-KEY": API_SECRET,
}

def get_them_orders():
    url = f"{BASE_URL}/v2/orders?status=all&limit=500"
    print(f"📡 Fetching orders from: {url}")

    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        print(f"❌ Error: {response.status_code} - {response.text}")
        return

    data = response.json()

    if not data:
        print("⚠️ No orders found.")
        return

    # Save orders to CSV
    csv_file = "alpaca_orders.csv"
    fieldnames = data[0].keys()

    with open(csv_file, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for order in data:
            writer.writerow(order)

    print(f"✅ Exported {len(data)} orders to {csv_file}")

if __name__ == "__main__":
    get_them_orders()

