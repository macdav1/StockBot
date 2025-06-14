import streamlit as st
import pandas as pd
import os
import plotly.express as px

st.title("📊 Stock Prediction Dashboard V6.2")

predictions_path = '/home/dave/predictions.csv'
backtest_dir = '/home/dave/backtest/'

# Load predictions
if os.path.exists(predictions_path):
    df = pd.read_csv(predictions_path)
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.sort_values(by='Date', ascending=False)
    st.subheader("Recent Daily Predictions")
    st.dataframe(df.head(20))
else:
    st.warning("No prediction data found. Run stock predictor first.")

# Load backtests
st.subheader("Backtest Results")

backtest_results = []
for file in os.listdir(backtest_dir):
    if file.endswith(".csv"):
        ticker = file.replace("backtest_", "").replace(".csv", "")
        result = pd.read_csv(os.path.join(backtest_dir, file))
        backtest_results.append(result)

if backtest_results:
    backtest_df = pd.concat(backtest_results, ignore_index=True)
    st.dataframe(backtest_df)
    fig = px.bar(backtest_df, x='Ticker', y='Backtest_Accuracy', title="Backtest Accuracy")
    st.plotly_chart(fig)
else:
    st.warning("No backtest results found. Run backtest_runner.py.")

