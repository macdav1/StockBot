import os
import json
import logging
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
import alpaca_trade_api as tradeapi
from utils.trade_logger import log_trade
from email_notifier import send_email
from position_tracker import track_new_position
import argparse

# Add argument parsing for multi-account support
parser = argparse.ArgumentParser(description='Execute buy orders from predictions')
parser.add_argument('--env', default='.env', help='Environment file to use (e.g., .env.dave)')
parser.add_argument('--config', default='config.json', help='Config file to use (e.g., config_dave.json)')
args = parser.parse_args()

# Load specific environment file FIRST
load_dotenv(args.env, override=True)

# Get email recipient from environment
EMAIL_RECIPIENT = os.getenv("EMAIL_TO", os.getenv("EMAIL_USER"))

# Logging
log_file = "logs/buy_executor.log"
os.makedirs(os.path.dirname(log_file), exist_ok=True)

logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger()

# Console output
console = logging.StreamHandler()
console.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(console)

# Alpaca API - uses environment variables loaded above
API_KEY = os.getenv("ALPACA_API_KEY")
API_SECRET = os.getenv("ALPACA_SECRET_KEY")
BASE_URL = os.getenv("ALPACA_PAPER_BASE_URL")
api = tradeapi.REST(API_KEY, API_SECRET, BASE_URL, api_version='v2')

# Load specific config file
with open(args.config) as f:
    config = json.load(f)

TRADE_AMOUNT_USD = float(config.get("trade_amount", 25))

# Log which account we're using
account_name = args.env.replace('.env.', '').replace('.env', 'default')
logger.info(f"="*60)
logger.info(f"Buy Executor starting for account: {account_name}")
logger.info(f"Using config: {args.config}")
logger.info(f"Email recipient: {EMAIL_RECIPIENT}")
logger.info(f"Trade amount: ${TRADE_AMOUNT_USD}")
logger.info(f"="*60)


def execute_buys():
    """
    Execute BUY orders for all signals in predictions.csv
    Signals already passed score/accuracy thresholds in predictor
    """
    trades_executed = []
    trades_failed = []
    
    try:
        # Check if predictions file exists
        if not os.path.exists("predictions.csv"):
            logger.warning("No predictions.csv found")
            send_email(
                f"No Buy Orders - {datetime.today().date()}",
                "No predictions.csv file found. Run predictor first.",
                to_email=EMAIL_RECIPIENT
            )
            return []
        
        # Load BUY signals only
        df = pd.read_csv("predictions.csv")
        buy_signals = df[df['Signal'].str.strip().str.upper() == 'BUY'].copy()
        
        if buy_signals.empty:
            logger.info("No BUY signals in predictions.csv")
            send_email(
                f"No Buy Signals - {datetime.today().date()}",
                "Predictor found no BUY signals today.",
                to_email=EMAIL_RECIPIENT
            )
            return []
        
        logger.info(f"📊 Found {len(buy_signals)} BUY signals to execute")
        
        for _, row in buy_signals.iterrows():
            ticker = row['Ticker'].strip().upper()
            score = float(row['Score'])
            predicted_price = float(row['Close'])
            
            try:
                # Get current price
                latest_price = float(api.get_latest_trade(ticker).price)
                
                # Check if asset is fractionable
                asset = api.get_asset(ticker)
                
                # Calculate quantity
                if asset.fractionable:
                    qty = round(TRADE_AMOUNT_USD / latest_price, 4)
                else:
                    qty = int(TRADE_AMOUNT_USD // latest_price)
                    if qty == 0:
                        logger.warning(f"⚠️  {ticker}: Price ${latest_price:.2f} too high for ${TRADE_AMOUNT_USD} (not fractionable)")
                        trades_failed.append(f"{ticker}: Price too high (${latest_price:.2f})")
                        continue
                
                # Submit market order
                order = api.submit_order(
                    symbol=ticker,
                    qty=qty,
                    side='buy',
                    type='market',
                    time_in_force='day'
                )
                
                logger.info(f"✅ BUY ORDER: {qty} shares of {ticker} @ ~${latest_price:.2f} (Score: {score:.2f})")
                
                trade_summary = (
                    f"BUY {qty} {ticker} @ ${latest_price:.2f}\n"
                    f"  Score: {score:.2f}\n"
                    f"  Amount: ${qty * latest_price:.2f}\n"
                    f"  Order ID: {order.id}"
                )
                
                trades_executed.append(trade_summary)
                
                # Track new position
                track_new_position(ticker, latest_price, qty)
                
                # Log trade
                log_trade(ticker, "BUY", qty, latest_price, score)
                
            except tradeapi.rest.APIError as e:
                logger.error(f"❌ Alpaca API error for {ticker}: {e}")
                trades_failed.append(f"{ticker}: {str(e)}")
                
            except Exception as e:
                logger.error(f"❌ Failed to buy {ticker}: {e}")
                trades_failed.append(f"{ticker}: {str(e)}")
        
    except Exception as e:
        logger.error(f"❌ Critical error in buy executor: {e}")
        send_email(
            f"Buy Executor Error - {datetime.today().date()}",
            f"Critical error occurred:\n{e}",
            to_email=EMAIL_RECIPIENT
        )
        return []
    
    # Email report
    subject = f"Buy Orders Report - {datetime.today().date()}"
    
    body_parts = []
    body_parts.append("="*60)
    body_parts.append("BUY ORDER EXECUTION REPORT")
    body_parts.append("="*60)
    body_parts.append("")
    
    if trades_executed:
        body_parts.append(f"✅ EXECUTED ({len(trades_executed)} orders):")
        body_parts.append("-"*60)
        body_parts.append("\n\n".join(trades_executed))
        body_parts.append("")
    else:
        body_parts.append("No buy orders were executed.")
        body_parts.append("")
    
    if trades_failed:
        body_parts.append(f"❌ FAILED ({len(trades_failed)} orders):")
        body_parts.append("-"*60)
        body_parts.append("\n".join(trades_failed))
        body_parts.append("")
    
    body_parts.append("="*60)
    body = "\n".join(body_parts)
    
    send_email(subject, body, to_email=EMAIL_RECIPIENT)
    logger.info(f"📧 Email report sent to {EMAIL_RECIPIENT}: {len(trades_executed)} executed, {len(trades_failed)} failed")
    
    return trades_executed


if __name__ == "__main__":
    logger.info("▶️ Starting Buy Executor")
    execute_buys()
    logger.info("✅ Buy Executor finished")
