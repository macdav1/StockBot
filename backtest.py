import yfinance as yf
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score

def backtest(ticker):
    data = yf.download(ticker, period="5y")

    if data.empty:
        print(f"No data for {ticker}")
        return None

    data['Target'] = np.where(data['Close'].shift(-1) > data['Close'], 1, 0)
    data = data.iloc[:-1]

    features = ['Open', 'High', 'Low', 'Close', 'Volume']
    scaler = StandardScaler()
    X = scaler.fit_transform(data[features])
    y = data['Target']

    model = LogisticRegression()
    model.fit(X, y)

    predictions = model.predict(X)
    accuracy = accuracy_score(y, predictions)

    return accuracy

