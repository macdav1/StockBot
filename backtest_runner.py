import pandas as pd
import yfinance as yf
import numpy as np
import datetime
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
from logger import logger


# ===== CONFIGURATION =====

tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "SHOP"]
backtest_start = "2023-01-01"
backtest_end = datetime.date.today().strftime("%Y-%m-%d")
results_file = "backtest_results.csv"

# ===== FEATURE ENGINEERING =====

def download_data(ticker, start, end):
    logger.info(f"Downloading data for {ticker} from {start} to {end}")
    df = yf.download(ticker, start=start, end=end)
    df.dropna(inplace=True)
    return df

def generate_features(df):
    df['Return'] = df['Close'].pct_change()
    df['MA5'] = df['Close'].rolling(window=5).mean()
    df['MA10'] = df['Close'].rolling(window=10).mean()
    df['EMA10'] = df['Close'].ewm(span=10, adjust=False).mean()
    df['Momentum'] = df['Close'] - df['Close'].shift(10)
    df['Volatility'] = df['Return'].rolling(window=10).std()

    # Bollinger Bands
    df['BB_upper'] = df['MA10'] + 2 * df['Volatility']
    df['BB_lower'] = df['MA10'] - 2 * df['Volatility']

    # MACD
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp1 - exp2

    # RSI
    delta = df['Close'].diff()
    up, down = delta.copy(), delta.copy()
    up[up < 0] = 0
    down[down > 0] = 0
    roll_up = up.rolling(14).mean()
    roll_down = down.abs().rolling(14).mean()
    rs = roll_up / roll_down
    df['RSI'] = 100 - (100 / (1 + rs))

    df.dropna(inplace=True)
    return df

def create_labels(df):
    df['Target'] = np.where(df['Close'].shift(-1) > df['Close'], 1, 0)
    return df

# ===== BACKTESTING =====

all_results = []

for ticker in tickers:
    try:
        df = download_data(ticker, backtest_start, backtest_end)
        df = generate_features(df)
        df = create_labels(df)

        features = ['Return', 'MA5', 'MA10', 'EMA10', 'Momentum', 'Volatility',
                    'BB_upper', 'BB_lower', 'MACD', 'RSI']
        X = df[features]
        y = df['Target']

        split_index = int(len(df) * 0.8)
        X_train, X_test = X[:split_index], X[split_index:]
        y_train, y_test = y[:split_index], y[split_index:]

        model = RandomForestClassifier(n_estimators=100, random_state=42)
        model.fit(X_train, y_train)

        y_pred = model.predict(X_test)
        acc = accuracy_score(y_test, y_pred)

        all_results.append({
            "Ticker": ticker,
            "Backtest Accuracy": round(acc, 4),
            "Samples": len(df)
        })

    except Exception as e:
        logger.error(f"Error processing {ticker}: {e}")

result_df = pd.DataFrame(all_results)
if not result_df.empty:
    logger.info(result_df)
    result_df.to_csv(results_file, index=False)
else:
    logger.info("No backtest results generated.")

