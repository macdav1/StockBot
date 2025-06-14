import pandas as pd
import yfinance as yf
import datetime

# Load today's predictions
today = datetime.date.today().strftime("%Y-%m-%d")
predictions = pd.read_csv('predictions.csv')
today_preds = predictions[predictions['Date'] == today]

# Function to download and clean price data
def download_data(ticker, period='1mo'):
    print(f"Downloading historical data for {ticker}...")
    df = yf.download(ticker, period=period, auto_adjust=False)

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df.dropna(inplace=True)
    return df

# Very simple backtest logic: did price move up or down after prediction?
results = []

for index, row in today_preds.iterrows():
    ticker = row['Ticker']
    prediction = row['Prediction']

    df = download_data(ticker)
    df['Return'] = df['Close'].pct_change()

    actual_return = df['Return'].iloc[-1]

    if (prediction == 'Up' and actual_return > 0) or (prediction == 'Down' and actual_return < 0):
        result = 'Correct'
    else:
        result = 'Incorrect'

    results.append({
        'Date': today,
        'Ticker': ticker,
        'Prediction': prediction,
        'ActualReturn': actual_return,
        'Result': result
    })

results_df = pd.DataFrame(results)
results_df.to_csv('backtest_results.csv', index=False)
print("Backtest completed and saved to backtest_results.csv")

