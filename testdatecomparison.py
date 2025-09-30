# test_first_of_month.py
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials

SERVICE_ACCOUNT_FILE = "service_account.json"
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1zHsk03oQtXiIBupZp6ZfRHpmaSKr3ikGuHYNKDw3emQ/edit"

# Authenticate
scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scopes)
client = gspread.authorize(creds)

# Load worksheet
ws = client.open_by_url(SPREADSHEET_URL).worksheet("Portfolio_History")
data = ws.get_all_records()
df = pd.DataFrame(data)

# Convert Date column to Timestamp
df["Date_converted"] = pd.to_datetime(df["Date"], errors="coerce")

# Set first of month as Timestamp
first_of_month = pd.Timestamp.today().replace(day=1)

# Compare and output results
df["is_before_first_of_month"] = df["Date_converted"] <= first_of_month

# Output
print("First of month:", first_of_month)
print(df[["Date", "Date_converted", "is_before_first_of_month"]])

