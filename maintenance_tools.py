import pandas as pd
import os

# Clean predictions.csv if needed
pred_path = '/home/dave/predictions.csv'

if os.path.exists(pred_path):
    df = pd.read_csv(pred_path)
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    df = df.dropna(subset=['Date'])
    df = df[['Date', 'Ticker', 'Prediction', 'Score', 'Accuracy']]
    df = df.sort_values('Date')
    df.to_csv(pred_path, index=False)
    print("✅ predictions.csv cleaned successfully.")
else:
    print("No predictions.csv found.")

