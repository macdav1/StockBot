import yfinance as yf
import pandas as pd

def get_market_sentiment():
    ticker = "^GSPC"  # S&P 500 index
    data = yf.download(ticker, period="5d", interval="1d", progress=False)

    if data.empty or len(data) < 2:
        return "⚪ Market data unavailable"

    # Extract close prices safely as scalar floats
    try:
        yesterday_close = float(data["Close"].iloc[-1])
        prev_close = float(data["Close"].iloc[-2])
    except Exception as e:
        return f"⚪ Data error: {e}"

    change = (yesterday_close - prev_close) / prev_close * 100

    # Ensure change is a plain float, not Series
    if isinstance(change, (pd.Series, pd.DataFrame)):
        change = float(change.iloc[0])

    if change > 0.3:
        sentiment = f"🟢 Market up {change:.2f}% — good day for stocks"
    elif change < -0.3:
        sentiment = f"🔴 Market down {change:.2f}% — tough day for stocks"
    else:
        sentiment = f"🟡 Market flat ({change:.2f}%) — neutral session"

    return sentiment


# Optional: test when running directly
if __name__ == "__main__":
    print(get_market_sentiment())

