import yfinance as yf
import pandas as pd
import numpy as np
import datetime

# Define the stock universe
TICKERS = ['AAPL', 'MSFT', 'GOOG', 'AMZN', 'NVDA', 'META', 'TSLA', 'SHOP']

# Download historical data
def download_data(ticker, period='1y'):
    print(f"Downloading data for {ticker}")
    end_date = datetime.datetime.today().strftime('%Y-%m-%d')
    df = yf.download(ticker, period=period, end=end_date, auto_adjust=False)

    # If multi-level columns, flatten
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # Now, df['Close'] is single-columned
    df.dropna(inplace=True)
    return df

# Feature engineering
def generate_features(df):
    df['Return'] = df['Close'].pct_change()
    df['MA5'] = df['Close'].rolling(window=5).mean()
    df['MA10'] = df['Close'].rolling(window=10).mean()
    df['Volatility'] = df['Close'].rolling(window=10).std()
    df.dropna(inplace=True)
    return df

# Very basic "predictor"
def simple_predictor(df):
    if df['MA5'].iloc[-1] > df['MA10'].iloc[-1]:
        return 'Up'
    else:
        return 'Down'

# Main function
def main():
    today = datetime.date.today().strftime('%Y-%m-%d')
    predictions = []

    for ticker in TICKERS:
        df = download_data(ticker)
        df = generate_features(df)
        prediction = simple_predictor(df)
        predictions.append({'Date': today, 'Ticker': ticker, 'Prediction': prediction})

    predictions_df = pd.DataFrame(predictions)
    predictions_df.to_csv('predictions.csv', index=False)
    print("Predictions saved to predictions.csv")

if __name__ == "__main__":
    main()

