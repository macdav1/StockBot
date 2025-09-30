import pandas as pd
import os
from datetime import datetime, timedelta
import logging
from alpaca_trade_api.rest import REST
from email_notifier import send_email
from dotenv import load_dotenv
from gsheet_logger import log_metrics, _get_ws
from utils.metric_calc import calculate_metrics
import pprint

load_dotenv()

API_KEY = os.getenv("ALPACA_API_KEY")
API_SECRET = os.getenv("ALPACA_SECRET_KEY")
BASE_URL = os.getenv("ALPACA_PAPER_BASE_URL")
api = REST(API_KEY, API_SECRET, BASE_URL, api_version='v2')

# Logger setup
logger = logging.getLogger("trade_accuracy")
logger.setLevel(logging.INFO)
fh = logging.FileHandler("/home/dave/Stock_app/logs/trade_accuracy.log", mode='a')
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
if logger.hasHandlers():
    logger.handlers.clear()
fh.setFormatter(formatter)
logger.addHandler(fh)


def compute_profit_percentages():
    """
    Reads Portfolio_History sheet and computes Monthly% and YTD% profit.
    Returns dict with 'monthly_profit_pct' and 'ytd_profit_pct'.
    """
    ws = _get_ws("Portfolio_History")
    data = ws.get_all_records()   # returns list of dicts
    if not data:
        return {"monthly_profit_pct": 0, "ytd_profit_pct": 0}

    df = pd.DataFrame(data)
        # Handle inconsistent date formats
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce", format="mixed")
    df = df.dropna(subset=["Date"])  # drop rows that failed to parse
    df = df.sort_values("Date")

    latest_value = df.iloc[-1]["Portfolio Value"]

    # --- Monthly ---
    month_start = datetime.today().replace(day=1)
    month_df = df[df["Date"] >= month_start]
    if not month_df.empty:
        first_month_value = month_df.iloc[0]["Portfolio Value"]
        monthly_profit_pct = ((latest_value - first_month_value) / first_month_value) * 100
    else:
        monthly_profit_pct = 0

    # --- YTD ---
    ytd_start = datetime.today().replace(month=1, day=1)
    ytd_df = df[df["Date"] >= ytd_start]
    if not ytd_df.empty:
        first_ytd_value = ytd_df.iloc[0]["Portfolio Value"]
        ytd_profit_pct = ((latest_value - first_ytd_value) / first_ytd_value) * 100
    else:
        ytd_profit_pct = 0

    return {
        "monthly_profit_pct": round(monthly_profit_pct, 2),
        "ytd_profit_pct": round(ytd_profit_pct, 2),
    }

def log_daily_portfolio(metrics):
    """
    Appends daily portfolio value & profit numbers into 'Portfolio_History' tab.
    """
    today = datetime.now().strftime("%Y-%m-%d")  # just the date, no time
    ws = _get_ws("Portfolio_History")

    # Check if today's entry already exists
    existing_dates = ws.col_values(1)  # first column = Date
    if today in existing_dates:
        return  # Already logged for today, skip

    # Prepare row
    row = [
        today,
        metrics.get("portfolio_value", 0),
        metrics.get("realized_profit", 0),
        metrics.get("unrealized_profit", 0),
    ]
    ws.append_row(row, value_input_option="USER_ENTERED")


def evaluate_trades_and_email(days_recent=3):
    try:
        trade_log_file = "/home/dave/Stock_app/trade_log.csv"
        if not os.path.exists(trade_log_file):
            msg = "⚠️ trade_log.csv does not exist. Skipping evaluation."
            logger.warning(msg)
            send_email("Daily Trade Prediction Accuracy", msg)
            return

        df = pd.read_csv(trade_log_file, parse_dates=["Timestamp"])

        # If "Price" column is missing (old logs), add it as NaN
        if "Price" not in df.columns:
            df["Price"] = float("nan")

        # If "Score" is missing, add it
        if "Score" not in df.columns:
            df["Score"] = float("nan")  
      
        df["Action"] = df["Action"].str.upper()
        df["Action"] = df["Action"].replace({"FALLBACK_SELL": "SELL"})
        df = df[df["Action"] == "BUY"]

        if df.empty:
            msg = "⚠️ No BUY trades found in trade_log.csv."
            logger.info(msg)
            send_email("Daily Trade Prediction Accuracy", msg)
            return

        def evaluate(trades_df):
            details = []
            tp = fp = 0
            for _, row in trades_df.iterrows():
                ticker = row["Ticker"]
                buy_price = float(row["Price"])
                try:
                    latest_trade = api.get_latest_trade(ticker)
                    latest_price = float(latest_trade.price)
                    pct_change = ((latest_price - buy_price) / buy_price) * 100.0
                    result = "✅" if latest_price > buy_price else "❌"
                    if result == "✅":
                        tp += 1
                    else:
                        fp += 1
                    details.append({
                        "Ticker": ticker,
                        "Buy Price": round(buy_price, 2),
                        "Current Price": round(latest_price, 2),
                        "% Change": round(pct_change, 2),
                        "Result": result
                    })
                except Exception as e:
                    logger.warning(f"Error checking {ticker}: {e}")

            # Build DF with explicit columns so empty still has the expected headers
            cols = ["Ticker", "Buy Price", "Current Price", "% Change", "Result"]
            details_df = pd.DataFrame(details, columns=cols)

            # Sort safely
            if not details_df.empty and "% Change" in details_df.columns:
                details_df = details_df.sort_values(by="% Change", ascending=False)

            precision = (tp / (tp + fp) * 100.0) if (tp + fp) > 0 else 0.0
            return tp, fp, tp + fp, precision, details_df

        cutoff_recent = datetime.now() - timedelta(days=days_recent)
        df_recent = df[df["Timestamp"] >= cutoff_recent]

        tp_recent, fp_recent, total_recent, precision_recent, details_recent = evaluate(df_recent)
        tp_all, fp_all, total_all, precision_all, details_all = evaluate(df)

        recent_block = (
            details_recent.to_string(index=False)
            if not details_recent.empty
            else f"No BUY trades in the last {days_recent} day(s)."
        )
        all_block = (
            details_all.to_string(index=False)
            if not details_all.empty
            else "No BUY trades on record."
        )

        result_text = (
            f"📊 BUY Prediction Precision (Last {days_recent} Days): "
            f"{precision_recent:.2f}% ({tp_recent} correct / {total_recent} total)\n"
            f"📊 BUY Prediction Precision (All Time): "
            f"{precision_all:.2f}% ({tp_all} correct / {total_all} total)\n\n"
            "----- Recent Trades -----\n"
            f"{recent_block}\n\n"
            "----- All-Time Trades -----\n"
            f"{all_block}"
        )

        # Example metrics payload (replace with your real calculations if available)
        # from gsheet_logger import log_metrics
        # metrics = {
        #     "avg_confidence": round(avg_conf, 2),
        #     "median_confidence": round(median_conf, 2),
        #     "symbols_tracked": int(symbols),
        #     "win_rate": round(precision_all / 100.0, 2),
        #     "portfolio_value": round(portfolio_value, 2),
        #     "Monthly Profit %": round(monthly_profit, 2),
        #     "YTD Profit %": round(YTD_profit, 2),
        # }
        # log_metrics(metrics)
        try:        
            metrics = calculate_metrics(
                #trade_log_path="trade_log.csv"#,
                #portfolio_path="portfolio.csv"
            )
            log_daily_portfolio(metrics)
            # 2. Compute monthly & YTD % from history
            #profit_percents = compute_profit_percentages()
            #metrics.update(profit_percents)
            logger.info(f"✅ Metrics calculated: {metrics}")
        except Exception as e:
            logger.error(f"❌ Failed to calculate metrics: {e}", exc_info=True)
            metrics = {}

        try:
            if metrics:
                print("📊 Metrics about to be logged:")
                pprint.pprint(metrics)

                logger.info(f"📊 Metrics about to be logged: {metrics}")
                log_metrics(metrics)
                logger.info("✅ Metrics logged to Google Sheets")
            else:
                logger.warning("⚠️ No metrics to log, skipping Google Sheets update")
        except Exception as e:
            logger.error(f"❌ Failed to log metrics to Google Sheets: {e}", exc_info=True)

        logger.info(result_text)

        logger.info(f"📧 Preparing email text:\n{result_text}")
        send_email("Detailed Trade Prediction Accuracy", result_text)
        logger.info("✅ Email sent successfully")

    except Exception as e:
        logger.error(f"Unexpected error in evaluate_trades_and_email: {e}")
        send_email("Trade Evaluation Error", f"⚠️ Error evaluating trades:\n{e}")


if __name__ == "__main__":
    evaluate_trades_and_email()

