# test_portfolio_dates_full.py
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials

# ==========================
# CONFIG
# ==========================
SERVICE_ACCOUNT_FILE = "service_account.json"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1zHsk03oQtXiIBupZp6ZfRHpmaSKr3ikGuHYNKDw3emQ/edit#gid=1622366173"
WORKSHEET_NAME = "Portfolio_History"

# ==========================
# Authenticate & read sheet
# ==========================
creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
client = gspread.authorize(creds)
ws = client.open_by_url(SPREADSHEET_URL).worksheet(WORKSHEET_NAME)

data = ws.get_all_records()
df = pd.DataFrame(data)

# ==========================
# Check all Date entries
# ==========================
print(f"Total rows: {len(df)}\n")

df["Date_converted"] = pd.to_datetime(df["Date"].astype(str), errors="coerce")

# Iterate through all rows and print type info
for idx, row in df.iterrows():
    original_value = row["Date"]
    original_type = type(original_value)
    converted_value = row["Date_converted"]
    converted_type = type(converted_value)
    if pd.isna(converted_value):
        status = "❌ Invalid date"
    else:
        status = "✅ Valid"
    print(f"Row {idx+1:03d}: Original='{original_value}' ({original_type.__name__}) -> Converted='{converted_value}' ({converted_type.__name__}) {status}")

# Summary
invalid_count = df["Date_converted"].isna().sum()
print(f"\nTotal invalid dates: {invalid_count}")

