import pandas as pd
from datetime import datetime

OUTPUT_FILE = "trade_log.csv"

# Load predictions history once
pred_df = pd.read_csv("predictions_history.csv", parse_dates=["Date"])
pred_df["Date"] = pred_df["Date"].dt.date  # only keep date for matching


def rebuild_trade_log(start_date="2025-08-01"):
    print(f"📥 Reading orders from alpaca_orders.csv (from {start_date} onwards)...")

    # Load Alpaca orders from local CSV
    orders_df = pd.read_csv("alpaca_orders.csv", parse_dates=["filled_at"])

    # Filter to only filled orders after start_date
    start_date = pd.to_datetime(start_date).date()
    orders_df = orders_df[
        (orders_df["status"] == "filled") &
        (orders_df["filled_at"].notna())
    ]
    orders_df["filled_date"] = pd.to_datetime(orders_df["filled_at"]).dt.date
    orders_df = orders_df[orders_df["filled_date"] >= start_date]

    records = []
    for _, order in orders_df.iterrows():
        try:
            action = order["side"].upper()  # BUY / SELL
            qty = float(order["filled_qty"]) if pd.notna(order["filled_qty"]) else 0.0
            price = float(order["filled_avg_price"]) if pd.notna(order["filled_avg_price"]) else None

            # Look up the score for this ticker and date
            matching = pred_df[(pred_df["Ticker"] == order["symbol"]) & (pred_df["Date"] == order["filled_date"])]
            score = matching["Score"].values[0] if not matching.empty else "0"

            if qty == 0 or price is None:
                continue  # skip unfilled/cancelled orders

            record = {
                "Timestamp": pd.to_datetime(order["filled_at"]).strftime("%Y-%m-%d %H:%M:%S"),
                "Ticker": order["symbol"],
                "Action": action,
                "Qty": round(qty, 4),
                "Price": round(price, 2),
                "Score": score
            }
            records.append(record)
        except Exception as e:
            print(f"⚠️ Error processing order {order['id']}: {e}")

    if not records:
        print("⚠️ No trades found in the given period.")
        return

    df = pd.DataFrame(records)
    df = df.sort_values(by="Timestamp")
    df.to_csv(OUTPUT_FILE, index=False)

    print(f"✅ Rebuilt {OUTPUT_FILE} with {len(df)} trades.")


if __name__ == "__main__":
    rebuild_trade_log("2025-08-01")

