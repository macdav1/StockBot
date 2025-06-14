import alpaca_trade_api as tradeapi

key_file_path = '/home/dave/Stock_app/alpaca_keys.txt'
with open(key_file_path, 'r') as f:
    lines = f.readlines()
    API_KEY = lines[0].strip()
    API_SECRET = lines[1].strip()

BASE_URL = 'https://paper-api.alpaca.markets'

api = tradeapi.REST(API_KEY, API_SECRET, BASE_URL, api_version='v2')

account = api.get_account()
print(account)

