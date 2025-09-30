# debug_metrics.py
import pandas as pd
from datetime import datetime

def calculate_metrics(
    portfolio_path="portfolio.csv",
    trades_path="trade_log.csv"
):
    # --- Load portfolio ---
    portfolio = pd.read_csv(portfolio_path)
    print("\n=== Raw Portfolio Data ===")
    print(portfolio)

    # Compute portfolio value
    portfolio["Value"] = portfolio["Shares"] * portfolio["Current Price"]
    print("\n=== Portfolio with Value ===")
    print(portfolio[["Ticker", "Shares", "Current Price", "Value"]])

    portfolio_value = portfolio["Value"].sum()
    print(f"\n>>> Portfolio Value: {portfolio_value:.2f}")

    # --- Load trades ---
    trades = pd.read_csv(trades_path, parse_dates=["Timestamp"])
    trades["Date"] = trades["Timestamp"].dt.date
    print("\n=== Raw Trade Log ===")
    print(trades)

    # --- Debug cutoffs ---
    today = datetime.today().date()
    first_of_month = today.replace(day=1)
    first_of_year = today.replace(month=1, day=1)
    print(f"\n>>> Today: {today}")
    print(f">>> First of month: {first_of_month}")
    print(f">>> First of year: {first_of_year}")

    # --- SELL trades only ---
    sell_trades = trades[trades["Action"].str.upper() == "SELL"].copy()
    print("\n=== SELL Trades Only ===")
    print(sell_trades)

    # Compute proceeds (just sell value for now)
    sell_trades["Proceeds"] = sell_trades["Qty"] * sell_trades["Price"]
    print("\n=== SELL Trades with Proceeds ===")
    print(sell_trades[["Timestamp", "Ticker", "Qty", "Price", "Proceeds"]])

    realised_profit = sell_trades["Proceeds"].sum()
    print(f"\n>>> Total Realised Profit (raw proceeds): {realised_profit:.2f}")

    # --- Monthly filter ---
    month_trades = sell_trades[sell_trades["Date"] >= first_of_month]
    print("\n=== Monthly SELL Trades ===")
    print(month_trades)

    monthly_profit = month_trades["Proceeds"].sum()
    print(f">>> Monthly Realised Profit: {monthly_profit:.2f}")

    # --- YTD filter ---
    ytd_trades = sell_trades[sell_trades["Date"] >= first_of_year]
    print("\n=== YTD SELL Trades ===")
    print(ytd_trades)

    ytd_profit = ytd_trades["Proceeds"].sum()
    print(f">>> YTD Realised Profit: {ytd_profit:.2f}")

    # --- Percentages ---
    monthly_profit_pct = (monthly_profit / portfolio_value * 100) if portfolio_value else None
    ytd_profit_pct = (ytd_profit / portfolio_value * 100) if portfolio_value else None
    print(f">>> Monthly Profit %: {monthly_profit_pct}")
    print(f">>> YTD Profit %: {ytd_profit_pct}")

    # Return metrics (still, for consistency)
    metrics = {
        "portfolio_value": portfolio_value,
        "realised_profit": realised_profit,
        "monthly_profit": monthly_profit,
        "monthly_profit_pct": monthly_profit_pct,
        "ytd_profit": ytd_profit,
        "ytd_profit_pct": ytd_profit_pct,
    }

    return metrics


if __name__ == "__main__":
    calculate_metrics()

