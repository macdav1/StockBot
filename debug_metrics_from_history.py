# debug_metrics_from_history.py
import os
import pandas as pd
import numpy as np
from datetime import datetime
from google.oauth2.service_account import Credentials
import gspread

# ---------- CONFIG ----------
SERVICE_ACCOUNT_FILE = "service_account.json"   # adjust if your key is named differently
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1zHsk03oQtXiIBupZp6ZfRHpmaSKr3ikGuHYNKDw3emQ/edit"
WORKSHEET_NAME = "Portfolio_History"
LOCAL_CSV = "portfolio_history.csv"   # optional local fallback
# ----------------------------

def load_portfolio_history():
    """Load portfolio history either from local CSV (if present) or from Google Sheets."""
    if os.path.exists(LOCAL_CSV):
        print(f"Loading local CSV: {LOCAL_CSV}")
        df = pd.read_csv(LOCAL_CSV)
        return df

    print("No local CSV found, reading Google Sheet...")
    scopes = ["https://www.googleapis.com/auth/spreadsheets",
              "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scopes)
    client = gspread.Client(auth=creds)
    ws = client.open_by_url(SPREADSHEET_URL).worksheet(WORKSHEET_NAME)
    data = ws.get_all_records()
    df = pd.DataFrame(data)
    return df

def find_date_and_value_columns(df):
    """Return (date_col, value_col). Raise helpful error if not found."""
    # Remove duplicate columns if present
    df = df.loc[:, ~df.columns.duplicated()]

    # Find date column
    date_candidates = [c for c in df.columns if "date" in c.lower()]
    if not date_candidates:
        # fallback: first column
        date_col = df.columns[0]
        print(f"No 'date' column name found — using first column '{date_col}' as date.")
    else:
        date_col = date_candidates[0]

    # Find portfolio value column
    value_candidates = [c for c in df.columns if ("portfolio" in c.lower() and "value" in c.lower()) or c.lower() in ("value","portfolio_value","total_value","portfolio value")]
    if not value_candidates:
        # fallback: choose first numeric column that isn't the date column
        numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c]) and c != date_col]
        if numeric_cols:
            value_col = numeric_cols[-1]  # last numeric column (common in history: date, value)
            print(f"No explicit 'Portfolio Value' column found — using numeric column '{value_col}' as value.")
        else:
            raise ValueError(f"Could not find portfolio value column. Columns: {list(df.columns)}")
    else:
        value_col = value_candidates[0]

    return date_col, value_col

def compute_metrics_from_history(df):
    """
    Compute metrics from portfolio history DataFrame (must include date and a numeric value).
    Uses last available row as 'current value' and finds last value on-or-before the
    start-of-month and start-of-year to compute monthly/YTD differences and percents.
    """
    # defensive cleanup
    df = df.loc[:, ~df.columns.duplicated()].copy()
    if df.empty:
        raise ValueError("Portfolio history DataFrame is empty")

    date_col, value_col = find_date_and_value_columns(df)

    # convert date -> Timestamp (force strings to handle mixed types)
    df[date_col] = pd.to_datetime(df[date_col].astype(str), errors="coerce")
    if df[date_col].isna().any():
        print("WARNING: Some date rows could not be parsed and became NaT. These rows will be ignored.")
    df = df.dropna(subset=[date_col])
    df.sort_values(by=date_col, inplace=True)
    df.reset_index(drop=True, inplace=True)

    # rename selected value column for convenience
    if value_col != "Portfolio Value":
        df.rename(columns={value_col: "Portfolio Value"}, inplace=True)

    # ensure numeric
    df["Portfolio Value"] = pd.to_numeric(df["Portfolio Value"], errors="coerce")
    if df["Portfolio Value"].isna().any():
        print("WARNING: Some portfolio value rows could not be converted to numeric and became NaN.")

    # Current (most recent) row
    current_row = df.iloc[-1]
    current_date = current_row[date_col]
    current_value = float(current_row["Portfolio Value"])

    # period cutoffs (as Timestamps)
    now = pd.Timestamp.now()
    first_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    first_of_year = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)

    def last_on_or_before(ts):
        """Return (value, row_date, row_index) of the last row with date <= ts. None if no row <= ts."""
        mask = df[date_col] <= ts
        if mask.any():
            r = df.loc[mask].iloc[-1]
            return float(r["Portfolio Value"]), r[date_col], int(r.name)
        else:
            return None, None, None

    start_month_val, start_month_date, start_month_idx = last_on_or_before(first_of_month)
    start_year_val, start_year_date, start_year_idx = last_on_or_before(first_of_year)

    # If no baseline found, we can fallback to earliest row (explicit)
    if start_month_val is None:
        start_month_val = float(df.iloc[0]["Portfolio Value"])
        start_month_date = df.iloc[0][date_col]
        start_month_idx = 0
        print("Note: no row on/before first_of_month — falling back to earliest row as baseline for month.")

    if start_year_val is None:
        start_year_val = float(df.iloc[0]["Portfolio Value"])
        start_year_date = df.iloc[0][date_col]
        start_year_idx = 0
        print("Note: no row on/before first_of_year — falling back to earliest row as baseline for year.")

    # compute diffs and percents
    monthly_profit = current_value - start_month_val
    monthly_profit_pct = (monthly_profit / start_month_val * 100.0) if start_month_val else None

    ytd_profit = current_value - start_year_val
    ytd_profit_pct = (ytd_profit / start_year_val * 100.0) if start_year_val else None

    # Diagnostic printout
    print("\n=== DIAGNOSTICS ===")
    print(f"Total rows in history: {len(df)}")
    print(f"Current row [{len(df)-1}]: date={current_date} value={current_value:.2f}")
    print(f"Start-of-month cutoff (ts): {first_of_month}")
    print(f"Baseline for month: idx={start_month_idx} date={start_month_date} value={start_month_val:.2f}")
    print(f"Start-of-year cutoff (ts): {first_of_year}")
    print(f"Baseline for year: idx={start_year_idx} date={start_year_date} value={start_year_val:.2f}")
    print("--- calculations ---")
    print(f"monthly_profit $ = current - baseline = {current_value:.2f} - {start_month_val:.2f} = {monthly_profit:.2f}")
    print(f"monthly_profit % = {monthly_profit_pct:.4g}")
    print(f"ytd_profit $ = current - baseline = {current_value:.2f} - {start_year_val:.2f} = {ytd_profit:.2f}")
    print(f"ytd_profit % = {ytd_profit_pct:.4g}")
    print("===================\n")

    return {
        "portfolio_value": current_value,
        "monthly_profit": monthly_profit,
        "monthly_profit_pct": monthly_profit_pct,
        "ytd_profit": ytd_profit,
        "ytd_profit_pct": ytd_profit_pct,
        "diagnostic_df": df  # included if you want to inspect further
    }

def main():
    df = load_portfolio_history()
    metrics = compute_metrics_from_history(df)
    print("Returned metrics dict:")
    for k, v in metrics.items():
        if k != "diagnostic_df":
            print(f"  {k}: {v}")
    # if needed, show tail of diagnostic df
    print("\nTail of diagnostic df (last 8 rows):")
    print(metrics["diagnostic_df"].tail(8))

if __name__ == "__main__":
    main()

