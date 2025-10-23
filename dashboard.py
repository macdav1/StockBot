import gspread
from google.oauth2.service_account import Credentials
import streamlit as st
import pandas as pd
import os
import plotly.express as px


st.title("📊 Stock Prediction Dashboard V6.5")


predictions_path = '/home/dave/Stock_app/predictions.csv'


# ---- Google Sheets setup ----
# Make sure you have your service account JSON file
SERVICE_ACCOUNT_FILE = "/home/dave/Stock_app/service_account.json"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",  # read/write
    "https://www.googleapis.com/auth/drive.readonly"
]

creds = Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
)
gc = gspread.authorize(creds)

# Open the sheet and worksheet
sh = gc.open("Stockbot_Dashboard")
ws = sh.worksheet("Metrics")

# Get all data
data = ws.get_all_records()  # returns a list of dicts: [{"Metric": ..., "Value": ...}, ...]

# Convert to a dict for easy lookup
metrics_dict = {row["Metric"]: row["Value"] for row in data}

# ---- Streamlit display ----
col1, col2, col3, col4 = st.columns(4)
col1.metric(label="Portfolio Value", value=metrics_dict.get("Portfolio Value", "N/A"))
col2.metric(label="YTD Profit %", value=metrics_dict.get("YTD Profit %", "N/A"))
col3.metric(label="Monthly Profit %", value=metrics_dict.get("Monthly Profit %", "N/A"))
col3.metric(label="Trade Accuracy", value=metrics_dict.get("Trade Accuracy", "N/A"))
st.markdown("🟢 August was a good month to start, lots of upward trading and enough money in the kitty to buy in. Ended the month at 26% up so far.")
st.markdown("🔴September was a bad month. Lost all my programs and had to start again and missed some valuable trades because there was no avaialable cash to buy. Ended the month on 3% profit which brought down YTD profit to 18.9%")
st.markdown("🟡 October made changes to only deal with stocks in the $2 to $20 price range as they seem to be more volatile. So far flat but its early. Oct 12th, Profit YTD down to 11.35%, changed to Claude and much happier with the result. Added another $500")

# Load predictions
if os.path.exists(predictions_path):
    try:
        df = pd.read_csv(predictions_path)

        # If Date column exists but is not needed, drop it
        if "Date" in df.columns:
            df = df.drop(columns=["Date"], errors="ignore")

        st.subheader("Recent Daily Predictions")
        from market_overnight import get_market_sentiment
        st.markdown(f"**{get_market_sentiment()}**")
        st.dataframe(df.head(20))
    except Exception as e:
        st.error(f"Error loading predictions.csv: {e}")
else:
    st.warning("No prediction data found. Run stock predictor first.")



