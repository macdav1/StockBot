import os
import json
import logging
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv
import alpaca_trade_api as tradeapi
from email_notifier import send_email
from alpaca_trade_api.rest import REST, TimeFrame
from track_stock_peaks import update_peak, remove_peak

load_dotenv()

log_file = "logs/sell_executor.log"
os.makedirs(os.path.dirname(log_file), exist_ok=True)
logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger()

API_KEY = os.getenv("ALPACA_API_KEY")
API_SECRET = os.getenv("ALPACA_SECRET_KEY")
BASE_URL = os.getenv("ALPACA_PAPER_BASE_URL")
api = tradeapi.REST(API_KEY, API_SECRET, BASE_URL, api_version='v2')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

with open(CONFIG_PATH) as f:
    config = json.load(f)

HOLD_DAYS = int(config.get("hold_days", 3))
TRADE_AMOUNT_USD = float(config.get("trade_amount", 30))
portfolio_file = "portfolio.csv"


def has_held_long_enough(ticker, now, hold_days):
    history_file = "trade_log.csv"
    if not os.path.exists(history_file):
        return True

    df = pd.read_csv(history_file)
    df = df[(df["Ticker"] == ticker) & (df["Action"].str.upper() == "BUY")]
    if df.empty:
        return True

    last_buy_time = max(pd.to_datetime(df["Timestamp"]))
    days_held = (now - last_buy_time).days
    return days_held >= hold_days


def execute_sells():
    trades_executed = []
    try:
        df = pd.read_csv("predictions.csv")
        df = df[df['Signal'].str.strip().str.lower() == 'sell']
        logger.info(f"Loaded {len(df)} sell signals.")

        for _, row in df.iterrows():
            ticker = row['Ticker'].strip().upper()
            score = float(row.get("Score", 0))
            
            try:
                bars = api.get_bars(
                    ticker,
                    TimeFrame.Day,
                    start=(datetime.now() - timedelta(days=40)).strftime("%Y-%m-%d"),
                    limit=30
                ).df

                if len(bars) < 10:
                    logger.info(f"Skipping {ticker}: insufficient historical data for filters")
                    continue

                close_prices = bars['close'][-20:] if len(bars) >= 20 else bars['close']
                volumes = bars['volume'][-20:] if len(bars) >= 20 else bars['volume']

                moving_avg = close_prices.mean()
                avg_volume = volumes.mean()
                latest_price = close_prices.iloc[-1]
                latest_volume = volumes.iloc[-1]

                if latest_price < moving_avg:
                    logger.info(f"Skipping SELL for {ticker}: price below moving average ({latest_price:.2f} < {moving_avg:.2f})")
                    continue

                if latest_volume < avg_volume:
                    logger.info(f"Skipping SELL for {ticker}: volume below average ({latest_volume:.0f} < {avg_volume:.0f})")
                    continue

            except Exception as e:
                logger.warning(f"Could not apply sell filters for {ticker}: {e}")
                continue

            try:
                try:
                    position = api.get_position(ticker)
                    position_qty = float(position.qty)
                    avg_cost = float(position.avg_entry_price)
                except tradeapi.rest.APIError:
                    logger.info(f"No position to sell for {ticker}, skipping.")
                    continue

                if position_qty <= 0.01:
                    logger.info(f"Skipping {ticker}: position too small to sell")
                    continue

                now = datetime.now()
                if not has_held_long_enough(ticker, now, HOLD_DAYS):
                    logger.info(f"Skipping sell for {ticker}: not held for {HOLD_DAYS} days yet")
                    continue

                latest_price = float(api.get_latest_trade(ticker).price)

                peak_price = update_peak(ticker, latest_price)
                gain = (peak_price - avg_cost) / avg_cost
                drop_from_peak = (peak_price - latest_price) / peak_price

                # --- SELL LOGIC ---

                # 1. Trailing stop
                if gain >= 0.20 and drop_from_peak > 0.05:
                    logger.info(
                        f"📉 SELL TRIGGERED (trailing stop): {ticker} gained {gain:.2%}, "
                        f"but dropped {drop_from_peak:.2%} from peak {peak_price:.2f}"
                    )
                    sell_qty = min(position_qty, round(TRADE_AMOUNT_USD / latest_price, 4))

                # 2. Profit exit (take small wins after hold_days)
                elif gain >= 0.02:
                    logger.info(
                        f"💰 SELL TRIGGERED (profit exit): {ticker} gained {gain:.2%}, "
                        f"selling to free capital"
                    )
                    sell_qty = min(position_qty, round(TRADE_AMOUNT_USD / latest_price, 4))

                # 3. 🔥 NEW RULE: Minimum profit exit after X days
                elif has_held_long_enough(ticker, now, HOLD_DAYS) and gain < 0.02:
                    logger.info(
                        f"⚠️ SELL TRIGGERED (min profit rule): {ticker} held {HOLD_DAYS}+ days, "
                        f"but gain only {gain:.2%} (<2%). Selling FULL position."
                    )
                    sell_qty = position_qty  # ✅ dump everything

                else:
                    logger.info(
                        f"Skipping {ticker}: Gain {gain:.2%}, drop {drop_from_peak:.2%} — no sell trigger"
                    )
                    continue


                sell_qty = min(position_qty, round(TRADE_AMOUNT_USD / latest_price, 4))

                api.submit_order(
                    symbol=ticker,
                    qty=sell_qty,
                    side='sell',
                    type='market',
                    time_in_force='day'
                )
                logger.info(f"SELL {sell_qty} shares of {ticker} at {latest_price}")
                trades_executed.append(f"SELL {sell_qty} {ticker}")
                remove_peak(ticker)

                log_entry = {
                    "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "Ticker": ticker,
                    "Action": "SELL",
                    "Qty": round(sell_qty, 4),
                    "Price": round(latest_price, 2),
                    "Score": round(score, 4)
                }
                df_log = pd.DataFrame([log_entry])
                df_log.to_csv("trade_log.csv", mode='a', header=not os.path.exists("trade_log.csv"), index=False)

            except Exception as e:
                logger.error(f"Error selling {ticker}: {e}")

    except Exception as e:
        logger.error(f"Unexpected error in sell_executor: {e}")

    try:
        positions = api.list_positions()
        portfolio_data = []
        for p in positions:
            current_price = float(p.current_price)
            avg_price = float(p.avg_entry_price)
            shares = float(p.qty)
            pl = (current_price - avg_price) * shares

            portfolio_data.append({
                "Ticker": p.symbol,
                "Shares": shares,
                "Average Cost": avg_price,
                "Current Price": current_price,
                "P/L($)": round(pl, 2)
            })

        df_portfolio = pd.DataFrame(portfolio_data)
        df_portfolio.to_csv("portfolio.csv", index=False)
        print("💾 portfolio.csv updated with current positions.")

    except Exception as e:
        logger.error(f"❌ Failed to update portfolio.csv: {e}")
        print(f"⚠️ Error while updating portfolio.csv: {e}")

    try:
        portfolio = pd.read_csv(portfolio_file)

        for _, row in portfolio.iterrows():
            ticker = row["Ticker"]
            avg_cost = float(row["Average Cost"])

            try:
                position = api.get_position(ticker)
                shares = float(position.qty)
            except tradeapi.rest.APIError:
                shares = 0

            if shares <= 0:
                logger.info(f"Fallback skipped for {ticker}: no actual position held.")
                continue

            if not has_held_long_enough(ticker, datetime.now(), HOLD_DAYS):
                logger.info(f"Fallback skipped for {ticker}: not held long enough.")
                continue

            current_price = float(api.get_latest_trade(ticker).price)
            gain = (current_price - avg_cost) / avg_cost

            # --- APPLY MIN-PROFIT RULE TO ALL HOLDINGS ---
            if gain < 0.02:  # < +2% gain after HOLD_DAYS
                logger.info(
                    f"⚠️ FALLBACK SELL TRIGGERED (min profit rule): {ticker} held {HOLD_DAYS}+ days, "
                    f"but gain only {gain:.2%} (<2%). Selling FULL position."
                )
                    # ✅ use Alpaca’s actual qty, floored to 4 decimals
                sell_qty = round(shares - 1e-6, 4)
            # --- ELSE: standard fallback rule for losers ---
            elif current_price < avg_cost:
                logger.info(
                    f"FALLBACK SELL TRIGGERED: {ticker} is below cost ({current_price:.2f} < {avg_cost:.2f})"
                )
                sell_qty = round(shares - 1e-6, 4)
            else:
                logger.info(f"Fallback skipped for {ticker}: gain {gain:.2%}, no trigger.")
                continue

            # Submit sell
            try:
                api.submit_order(
                    symbol=ticker,
                    qty=round(sell_qty, 4),
                    side='sell',
                    type='market',
                    time_in_force='day'
                )
                trades_executed.append(f"Fallback SELL {round(sell_qty, 4)} {ticker}")
                logger.info(f"✅ FALLBACK SELL {sell_qty} shares of {ticker} at {current_price}")

                log_entry = {
                    "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "Ticker": ticker,
                    "Action": "FALLBACK_SELL",
                    "Qty": round(sell_qty, 4),
                    "Price": round(current_price, 2),
                    "Score": "N/A"
                }
                pd.DataFrame([log_entry]).to_csv("trade_log.csv", mode='a',
                                                header=not os.path.exists("trade_log.csv"), index=False)

            except Exception as e:
                logger.error(f"Fallback SELL failed for {ticker}: {e}")
                continue

    except Exception as e:
        logger.error(f"Error during fallback sell logic: {e}")


    if trades_executed:
        subject = f"Sell Trades Executed - {datetime.today().date()}"
        body = "\n".join(trades_executed)
    else:
        subject = f"No Sell Trades Executed - {datetime.today().date()}"
        body = "No sell trades were made today."

    send_email(subject, body)


if __name__ == "__main__":
    logger.info("▶️ Starting Sell Executor")
    execute_sells()
    logger.info("✅ Sell Executor finished")

