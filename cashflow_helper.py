import pandas as pd
import sys

def get_monthly_cashflow(csv_path="cashflow.csv", year=None, month=None):
    """
    Calculate net cashflow (deposits - withdrawals).
    
    Parameters:
        csv_path (str): Path to cashflow CSV file
        year (int): Year to filter (required)
        month (int, optional): Month to filter (1-12). If None, calculate full year.
        
    Returns:
        float: Net cashflow (positive = more deposits, negative = more withdrawals)
    """
    if year is None:
        raise ValueError("Year must be provided")

    df = pd.read_csv(csv_path, parse_dates=["Date"])
    
    # Filter by year
    df_filtered = df[df["Date"].dt.year == year]
    
    # Filter by month if provided
    if month is not None:
        df_filtered = df_filtered[df_filtered["Date"].dt.month == month]
    
    # Assign signs: deposits = +Amount, withdrawals = -Amount
    df_filtered["SignedAmount"] = df_filtered.apply(
        lambda row: row["Amount"] if row["Type"] == "DEPOSIT" else
                    -row["Amount"] if row["Type"] == "WITHDRAWAL" else 0,
        axis=1
    )
    
    return df_filtered["SignedAmount"].sum()


if __name__ == "__main__":
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print("Usage: python cashflow_helper.py <year> [month]")
        sys.exit(1)
    
    year = int(sys.argv[1])
    month = int(sys.argv[2]) if len(sys.argv) == 3 else None
    
    result = get_monthly_cashflow("cashflow.csv", year=year, month=month)
    
    if month:
        print(f"Net cashflow for {year}-{month:02d}: {result}")
    else:
        print(f"Net cashflow for {year}: {result}")

