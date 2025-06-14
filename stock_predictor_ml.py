import yfinance as yf
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split
import joblib
import datetime

# Load stock list
stock_list = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA', 'SHOP']

# Set prediction date
today = datetime.date.today()

# Storage for predictions
results = []

def download_data(ticker, period='1y'):
    print(f"Downloading data for {ticker}")
    df = yf.download(ticker, period=period, interval='1d', auto_adjust=False)
    df.dropna(inplace=True)
    return df

def generate_features(df):
    df['Return'] = df['Close'].pct_change()
    df['MA5'] = df['Close'].rolling(window=5).mean()
    df['MA10'] = df['Close'].rolling(window=10).mean()
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['Volume'] = df['Volume']
    df['Target'] = (df['Close'].shift(-1) > df['Close']).astype(int)
    df.dropna(inplace=True)
    return df

def train_model(X_train, y_train):
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    return model

for ticker in stock_list:
    df = download_data(ticker)
    df = generate_features(df)
    
    feature_cols = ['MA5', 'MA10', 'MA20', 'Volume', 'Return']
    X = df[feature_cols]
    y = df['Target']
    
    # Split for training and testing
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    model = train_model(X_train, y_train)
    
    # Evaluate accuracy
    y_pred = model.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    
    # Predict next day
    latest_data = df.iloc[-1:][feature_cols]
    prediction = model.predict(latest_data)[0]
    proba = model.predict_proba(latest_data)[0][1]
    
    results.append({
        'Date': today,
        'Ticker': ticker,
        'Prediction': 'Up' if prediction == 1 else 'Down',
        'Score': round(proba, 4),
        'Accuracy': round(acc, 4)
    })
    
    # Save model for future reuse if needed
    joblib.dump(model, f'{ticker}_model.joblib')

# Save predictions
predictions_df = pd.DataFrame(results)
predictions_df.to_csv('predictions.csv', index=False)

print("Predictions completed!")
print(predictions_df)

