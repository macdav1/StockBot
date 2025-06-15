import yfinance as yf
import pandas as pd
from datetime import datetime
from logger import logger


# Parameters
score_threshold = 0.60
accuracy_threshold = 0.55

# List of tickers to analyze
tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "SHOP", "ANF"]

# Dummy model - same as previous
def predict(df):
    import random
    prediction = random.choice(["Up", "Down"])
    score = round(random.uniform(0.05, 0.95), 2)
    accuracy = round(random.uniform(0.35, 0.65), 4)
    return prediction, score, accuracy

# Feature engineering (simplified as before)
def generate_features(df):
    df['Return'] = df['Close'].pct_change()
    df['MA5'] = df['Close'].rolling(window=5).mean()
    df['MA10'] = df['Close'].rolling(window=10).mean()
    df.dropna(inplace=True)
    return df

# Download data function
def download_data(ticker, period='1y'):
    logger.info(f"Downloading data for {ticker}")
    df = yf.download(ticker, period=period, auto_adjust=False)
    df.dropna(inplace=True)
    return df

# Main logic
def main():
    predictions = []

    for ticker in tickers:
        df = download_data(ticker)
        df = generate_features(df)
        prediction, score, accuracy = predict(df)

        # Determine signal
        if score >= score_threshold and accuracy >= accuracy_threshold:
            signal = "BUY" if prediction == "Up" else "SELL"
        else:
            signal = "-"

        predictions.append({
            "Date": datetime.now().strftime("%Y-%m-%d"),
            "Ticker": ticker,
            "Prediction": prediction,
            "Score": score,
            "Accuracy": accuracy,
            "Signal": signal
        })

    # Save predictions to CSV
    df_pred = pd.DataFrame(predictions)
    df_pred.to_csv("predictions.csv", index=False)

    logger.info("Predictions completed!")
    logger.info(df_pred)

if __name__ == "__main__":
    main()

