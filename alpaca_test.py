import os
from dotenv import load_dotenv
import requests

# Load your .env variables
load_dotenv()

# Read Alpaca credentials from .env
ALPACA_API_KEY = os.getenv('ALPACA_API_KEY')
ALPACA_SECRET_KEY = os.getenv('ALPACA_SECRET_KEY')
ALPACA_BASE_URL = os.getenv('ALPACA_PAPER_BASE_URL')  # should be https://paper-api.alpaca.markets

# Test connection: get account info
url = f"{ALPACA_BASE_URL}/v2/account"
headers = {
    'APCA-API-KEY-ID': ALPACA_API_KEY,
    'APCA-API-SECRET-KEY': ALPACA_SECRET_KEY
}

response = requests.get(url, headers=headers)

if response.status_code == 200:
    print("✅ Connection successful!")
    account_info = response.json()
    print("Account Info:")
    print(account_info)
else:
    print("❌ Connection failed!")
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")

