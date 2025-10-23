import pandas as pd
from yahooquery import Ticker
import numpy as np

def get_nyse_tickers():
    """
    Load NYSE tickers from public CSV.
    Replace with your own list if you have one.
    """
    url = "https://datahub.io/core/nyse-other-listings/r/nyse-listed.csv"
    df = pd.read_csv(url)
    return df['ACT Symbol'].dropna().unique().tolist()

def get_price_and_history(symbol):
    """
    Return current price and last 7 days of close prices for a ticker.
    """
    try:
        t = Ticker(symbol)
        price = t.price[symbol]["regularMarketPrice"]
        if price is None:
            return None

        if not (2 <= price <= 20):
            return None

        hist = t.history(period="7d", interval="1d")
        if hist.empty:
            return None

        closes = hist["close"].values[-7:]
        if len(closes) < 7:
            return None

        # simple spike score: last close vs avg of prior 6
        last = closes[-1]
        mean = np.mean(closes[:-1])
        spike_score = (last - mean) / mean

        return {
            "symbol": symbol,
            "price": price,
            "spike": spike_score
        }
    except Exception:
        return None

def main():
    tickers = get_nyse_tickers()
    print(f"Checking {len(tickers)} NYSE tickers...")

    results = []
    for i, sym in enumerate(tickers, 1):
        row = get_price_and_history(sym)
        if row:
            results.append(row)

        if i % 100 == 0:
            print(f"Processed {i} tickers...")

    df = pd.DataFrame(results)
    if df.empty:
        print("No tickers found in range.")
        return

    df_sorted = df.sort_values(by="spike", ascending=False).head(100)
    df_sorted.to_csv("top_100_stocks.txt", index=False, columns=["symbol"])
    print("✅ Saved top 100 stocks to top_100_stocks.txt")

if __name__ == "__main__":
    main()

