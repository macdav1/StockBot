import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score
import xgboost as xgb
import joblib
import os
import json
from logger import logger
import re

# Load config
with open("config.json") as f:
    config = json.load(f)

score_threshold = config["score_threshold"]
accuracy_threshold = config["accuracy_threshold"]
model_path = config["model_path"]
scaler_path = config["scaler_path"]
data_period = config.get("data_period", "6mo")

# Load tickers from file
with open("top_100_stocks.txt", "r") as f:
    tickers = [line.strip() for line in f.readlines() if line.strip()]

# Load portfolio tickers
portfolio_df = pd.read_csv("portfolio.csv")
portfolio_tickers = set(portfolio_df["Ticker"].astype(str).str.strip())

# --- Exclusion: explicit list + heuristic pattern detection for leveraged ETFs
EXCLUDE_TICKERS = {
    "SQQQ", "TQQQ", "UVXY", "SOXS", "SOXL", "SPXL", "SPXS",
    "LABU", "LABD", "TECL", "TECS", "FNGU", "FNGD", "UDOW", "SDOW"
}
_LEVERAGED_PATTERNS = re.compile(
    r'(2x|3x|Ultra|UltraShort|Ultra Pro|Ultra-Pro|Direxion|ProShares|Inverse|Daily|Leveraged|Short)', 
    re.IGNORECASE
)

def generate_features(df):
    df['Return'] = df['Close'].pct_change()
    df['MA5'] = df['Close'].rolling(window=5).mean()
    df['MA10'] = df['Close'].rolling(window=10).mean()
    df['Label'] = (df['Close'].shift(-1) > df['Close']).astype(int)
    df.dropna(inplace=True)
    return df

def get_training_data(tickers):
    all_data = []
    for ticker in tickers:
        try:
            logger.info(f"Downloading training data for {ticker}")
            df = yf.download(ticker, period="1y", auto_adjust=False)
            df = generate_features(df)
            df['Ticker'] = ticker
            all_data.append(df)
        except Exception as e:
            logger.warning(f"Failed to get data for {ticker}: {e}")
    if not all_data:
        raise RuntimeError("No training data available for any tickers.")
    return pd.concat(all_data)

def train_model():
    df = get_training_data(tickers)
    X = df[['Return', 'MA5', 'MA10']]
    y = df['Label']
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    X_train, X_test, y_train, y_test = train_test_split(X_scaled, y, test_size=0.2, random_state=42)

    model = xgb.XGBClassifier(use_label_encoder=False, eval_metric="logloss")
    model.fit(X_train, y_train)

    accuracy = accuracy_score(y_test, model.predict(X_test))
    model.save_model(model_path)
    joblib.dump(scaler, scaler_path)
    return model, scaler, accuracy

def load_model():
    if os.path.exists(model_path) and os.path.exists(scaler_path):
        model = xgb.XGBClassifier()
        model.load_model(model_path)
        scaler = joblib.load(scaler_path)
        return model, scaler, 0.60  # Conservative fallback
    else:
        return train_model()

def download_data(ticker):
    logger.info(f"Downloading data for {ticker}")
    df = yf.download(ticker, period=data_period, auto_adjust=False)
    df.dropna(inplace=True)
    return df

def looks_like_leveraged(ticker):
    if ticker in EXCLUDE_TICKERS:
        return True
    try:
        info = yf.Ticker(ticker).info or {}
        name = info.get('longName') or info.get('shortName') or ""
        if name and _LEVERAGED_PATTERNS.search(name):
            logger.info("Excluding %s because name matches leveraged pattern: %s", ticker, name)
            return True
    except Exception:
        logger.debug("Could not fetch metadata for %s to check leveraged pattern", ticker)
    return False

def filter_by_signal_and_price(predictions_df, confidence_threshold=0.7, limit=10, min_price=10, max_price=20):
    df = predictions_df.copy()
    df['Score'] = pd.to_numeric(df.get('Score'), errors='coerce')
    df['Close'] = pd.to_numeric(df.get('Close'), errors='coerce')
    df = df.dropna(subset=['Score', 'Close'])

    sell_signals = df[df['Signal'] == 'SELL']

    buy_signals = df[
        (df['Signal'] == 'BUY') &
        (df['Score'] >= confidence_threshold) &
        (df['Close'] >= min_price) &
        (df['Close'] <= max_price)
    ]

    if buy_signals.empty and sell_signals.empty:
        logger.info("filter_by_signal_and_price: no BUYs or SELLs passed filters.")
        return df.head(0)

    combined = pd.concat([buy_signals, sell_signals])
    combined_sorted = combined.sort_values(by='Score', ascending=False).head(limit)

    return combined_sorted

def main():
    model, scaler, accuracy = load_model()
    predictions = []

    for ticker in tickers:
        if looks_like_leveraged(ticker):
            logger.info("Skipping leveraged/inverse ETF: %s", ticker)
            continue

        df = download_data(ticker)
        if df.empty:
            logger.warning(f"Insufficient data for {ticker}")
            continue

        df = generate_features(df)
        if df.empty:
            logger.warning(f"No feature rows after generate_features for {ticker}")
            continue

        latest = df[['Return', 'MA5', 'MA10']].iloc[-1:]
        scaled = scaler.transform(latest)
        prob = model.predict_proba(scaled)[0]

        prediction = "Up" if prob[1] > prob[0] else "Down"
        score = round(float(prob[1] if prediction == "Up" else prob[0]), 2)

        close_price_raw = df['Close'].iloc[-1]
        try:
            if isinstance(close_price_raw, pd.Series):
                close_price_raw = close_price_raw.iloc[0]
            close_price = float(close_price_raw)
        except Exception:
            logger.warning(f"Could not parse close price for {ticker}: {close_price_raw!r}; skipping ticker")
            continue

        # --- Signal logic with portfolio-aware SELLs ---
        if score >= score_threshold and accuracy >= accuracy_threshold:
            if prediction == "Up":
                signal = "BUY"
            else:  # prediction == "Down"
                if ticker in portfolio_tickers:
                    signal = "SELL"
                else:
                    signal = "-"
        else:
            signal = "-"

        predictions.append({
            "Date": datetime.now().strftime("%Y-%m-%d"),
            "Ticker": ticker,
            "Prediction": prediction,
            "Score": score,
            "Accuracy": round(accuracy, 4),
            "Signal": signal,
            "Close": close_price
        })

    # --- Build DataFrames ---
    df_all = pd.DataFrame(predictions)  # all tickers
    # Only actionable BUY/SELL signals that pass thresholds
    df_signals = df_all[
        (df_all["Signal"].isin(["BUY", "SELL"])) &
        (df_all["Score"] >= score_threshold) &
        (df_all["Accuracy"] >= accuracy_threshold)
    ]

    # --- Save outputs ---
    df_all.to_csv("all_predictions.csv", index=False)
    df_signals.to_csv("predictions.csv", index=False)

    logger.info("Predictions completed!")
    logger.info("All predictions saved to all_predictions.csv")
    logger.info("Actionable signals saved to predictions.csv")
    logger.info("Sample actionable signals:\n%s", df_signals.head(10).to_dict(orient="records"))


if __name__ == "__main__":
    main()

