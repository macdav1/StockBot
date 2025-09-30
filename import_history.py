import pandas as pd
from gsheet_logger import _get_ws

def import_portfolio_history(csv_path="portfolio_history.csv", sheet_name="Portfolio_History"):
    # Load the CSV
    df = pd.read_csv(csv_path)

    # Only keep Timestamp + Equity
    df = df[["Timestamp", "Equity"]]

    # Open worksheet
    ws = _get_ws(sheet_name)

    # Write header if sheet is empty
    if len(ws.get_all_values()) == 0:
        ws.append_row(["Timestamp", "Equity"])

    # Append each row
    for _, row in df.iterrows():
        ws.append_row([row["Timestamp"], row["Equity"]])

    print(f"✅ Imported {len(df)} rows into sheet '{sheet_name}'")

if __name__ == "__main__":
    import_portfolio_history()

