import gspread
from google.oauth2.service_account import Credentials

# Scopes for Google Sheets + Drive
scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# Load the service account credentials
creds = Credentials.from_service_account_file("service_account.json", scopes=scopes)

# Create gspread client
client = gspread.Client(auth=creds)

# Open your spreadsheet
try:
    sh = client.open("Stockbot_Dashboard")
    print("Worksheets in the spreadsheet:")
    for ws in sh.worksheets():
        print("-", ws.title)
except gspread.exceptions.APIError as e:
    print("API Error:", e)
except Exception as e:
    print("Other Error:", e)


