# gsheet_logger.py
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import pandas as pd

# ==========================
# CONFIG
# ==========================
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1zHsk03oQtXiIBupZp6ZfRHpmaSKr3ikGuHYNKDw3emQ/edit"
SERVICE_ACCOUNT_FILE = "service_account.json"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# ==========================
# AUTHENTICATION
# ==========================
def get_gspread_client():
    """
    Authenticate and return a gspread client using service account credentials.
    """
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    client = gspread.Client(auth=creds)
    return client

# Create a global client to use in helper functions
client = get_gspread_client()

# ==========================
# HELPERS
# ==========================
def _get_ws(sheet_name):
    """Return a worksheet object by name"""
    return client.open_by_url(SPREADSHEET_URL).worksheet(sheet_name)

def _today():
    """Return today's date as YYYY-MM-DD"""
    return datetime.now().strftime("%Y-%m-%d")

def read_google_sheet(spreadsheet_name, worksheet_name):
    """Reads a Google Sheet worksheet into a Pandas DataFrame"""
    sheet = client.open(spreadsheet_name).worksheet(worksheet_name)
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    return df

# ==========================
# LOGGING FUNCTIONS
# ==========================
def log_metric(accuracy, avg_confidence, total_trades, win_rate, pnl):
    ws = _get_ws("Metrics")
    ws.append_row([_today(), accuracy, avg_confidence, total_trades, win_rate, pnl])

def log_metrics(metrics: dict):
    ws = _get_ws("Metrics")

    mapping = {
        "portfolio_value": "Portfolio Value",
        "monthly_profit_pct": "Monthly Profit %",
        "ytd_profit_pct": "YTD Profit %",
        "monthly_profit": "Monthly Profit",
        "ytd_profit": "YTD Profit",
        "trade_accuracy": "Trade Accuracy"   # ✅ New metric added
    }

    for key, metric_name in mapping.items():
        value = metrics.get(key, "")
        cell = ws.find(metric_name)
        if cell:
            value_cell = f"B{cell.row}"  # Column B = "Value"
            print(f"DEBUG: Writing {value} to {metric_name} at {value_cell}")
            value = metrics.get(key, "")
            ws.update(value_cell, [[value]])  # ✅ Use 2D list
        else:
            print(f"WARNING: Could not find metric '{metric_name}' in the sheet")

def log_prediction(symbol, predicted, confidence):
    ws = _get_ws("Predictions")
    ws.append_row([_today(), symbol, predicted, confidence])

def log_trade(symbol, action, qty, price, pnl):
    ws = _get_ws("Trades")
    ws.append_row([_today(), symbol, action, qty, price, pnl])

def log_portfolio(total_value, cash, positions, unrealized_pnl):
    ws = _get_ws("Portfolio")
    ws.append_row([_today(), total_value, cash, positions, unrealized_pnl])

