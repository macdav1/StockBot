import os
import json
import logging
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
import alpaca_trade_api as tradeapi
from utils.trade_logger import log_trade
from email_notifier import send_email
from position_tracker import get_position_age, remove_position_tracking, sync_with_broker_positions
import argparse

# Add argument parsing for multi-account support
parser = argparse.ArgumentParser(description='Execute fallback sells for underperforming positions')
parser.add_argument('--env', default='.env', help='Environment file to use (e.g., .env.dave)')
parser.add_argument('--config', default='config.json', help='Config file to use (e.g., config_dave.json)')
args = parser.parse_args()

# Load specific environment file FIRST
load_dotenv(args.env, override=True)



# Get email recipient from environment
EMAIL_RECIPIENT = os.getenv("EMAIL_TO", os.getenv("EMAIL_USER"))

# Logging setup
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "fallback_sell_executor.log")

logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger()

# DEBUG: Check which API key is loaded
logger.info(f"DEBUG: Using API key ending in: ...{os.getenv('ALPACA_API_KEY')[-4:]}")

# Add console handler
console = logging.StreamHandler()
console.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(console)

# Alpaca API - uses environment variables loaded above
API_KEY = os.getenv("ALPACA_API_KEY")
API_SECRET = os.getenv("ALPACA_SECRET_KEY")
BASE_URL = os.getenv("ALPACA_PAPER_BASE_URL")
api = tradeapi.REST(API_KEY, API_SECRET, BASE_URL, api_version="v2")

# Load config from specified file
with open(args.config) as f:
    config = json.load(f)

HOLD_DAYS = int(config.get("hold_days", 3))
FALLBACK_GAIN_THRESHOLD = float(config.get("fallback_gain_threshold", 0.02))
MAX_HOLD_DAYS = int(config.get("max_hold_days", 7))
STOP_LOSS_PCT = float(config.get("stop_loss_pct", -0.08))
TRAILING_STOP_PCT = float(config.get("trailing_stop_pct", -0.05))

# Log which account we're using
account_name = args.env.replace('.env.', '').replace('.env', 'default')
logger.info(f"="*60)
logger.info(f"Fallback Sell Executor starting for account: {account_name}")
logger.info(f"Using config: {args.config}")
logger.info(f"Email recipient: {EMAIL_RECIPIENT}")
logger.info(f"Hold days: {HOLD_DAYS}, Max hold: {MAX_HOLD_DAYS}")
logger.info(f"Stop loss: {STOP_LOSS_PCT:.0%}, Trailing stop: {TRAILING_STOP_PCT:.0%}")
logger.info(f"="*60)


def execute_fallback_sells():
    trades_executed = []
    skipped_positions = []
    errors = []
    
    # Statistics for email summary
    stats = {
        'total_positions': 0,
        'not_held_long_enough': 0,
        'below_cost': 0,
        'low_gain': 0,
        'meeting_targets': 0,
        'sells_executed': 0,
        'sell_failures': 0
    }
    
    try:
        # Sync position tracking with broker first
        sync_with_broker_positions(api)
        
        # Get all positions from Alpaca
        positions = api.list_positions()
        stats['total_positions'] = len(positions)
        
        if not positions:
            logger.info("No open positions to analyze")
            send_email(
                f"No Positions to Analyze - {datetime.today().date()}",
                "No open positions found in account.",
                to_email=EMAIL_RECIPIENT
            )
            return
        
        logger.info(f"📊 Analyzing {len(positions)} positions for fallback sells")
        
        for position in positions:
            ticker = position.symbol
            shares = float(position.qty)
            avg_cost = float(position.avg_entry_price)
            current_price = float(position.current_price)
            market_value = float(position.market_value)
            unrealized_pl = float(position.unrealized_pl)
            unrealized_plpc = float(position.unrealized_plpc)
            
            # Get days held from tracking file
            days_held = get_position_age(ticker)
            
            if days_held is None:
                logger.warning(f"⚠️  {ticker}: No tracking data found, assuming 0 days")
                days_held = 0
            
            # Check minimum hold period
            if days_held < HOLD_DAYS:
                stats['not_held_long_enough'] += 1
                logger.info(f"Fallback skipped for {ticker}: held only {days_held} days (min: {HOLD_DAYS})")
                skipped_positions.append(f"{ticker}: Held {days_held}/{HOLD_DAYS} days")
                continue
            
            gain = (current_price - avg_cost) / avg_cost
            peak_gain = unrealized_plpc
            
            # Determine sell reason with multiple exit strategies
            sell_reason = None
            
            # 1. STOP LOSS - Hard stop at -8%
            if gain <= STOP_LOSS_PCT:
                sell_reason = f"STOP LOSS: {gain:.2%} loss (threshold: {STOP_LOSS_PCT:.0%})"
                stats['below_cost'] += 1
                
            # 2. TRAILING STOP - If was profitable but dropped significantly
            elif peak_gain > 0.05 and gain < (peak_gain - abs(TRAILING_STOP_PCT)):
                sell_reason = f"TRAILING STOP: At {gain:.2%}, dropped from peak {peak_gain:.2%}"
                stats['below_cost'] += 1
            
            # 3. TIME STOP - Held max days without hitting target
            elif days_held >= MAX_HOLD_DAYS and gain < FALLBACK_GAIN_THRESHOLD:
                sell_reason = f"TIME STOP: Held {days_held} days (max: {MAX_HOLD_DAYS}), gain only {gain:.2%}"
                stats['low_gain'] += 1
                
            # 4. BELOW COST - Losing position (after minimum hold)
            elif current_price < avg_cost:
                sell_reason = f"LOSING TRADE: ${current_price:.2f} < ${avg_cost:.2f} (cost), {gain:.2%}"
                stats['below_cost'] += 1
            
            # 5. LOW GAIN - After minimum hold period
            elif gain < FALLBACK_GAIN_THRESHOLD:
                sell_reason = f"LOW GAIN: {gain:.2%} < {FALLBACK_GAIN_THRESHOLD:.0%} after {days_held} days"
                stats['low_gain'] += 1
                
            else:
                stats['meeting_targets'] += 1
                logger.info(
                    f"✅ {ticker}: gain {gain:.2%}, P/L ${unrealized_pl:.2f} ({unrealized_plpc:.2%}), held {days_held} days - " 
                    f"Meeting targets, no fallback needed"
                )
                skipped_positions.append(f"{ticker}: Meeting targets ({gain:.2%} gain, {days_held}d)")
                continue
            
            # Execute sell
            logger.warning(
                f"⚠️ FALLBACK SELL TRIGGERED: {ticker}\n"
                f"   Reason: {sell_reason}\n"
                f"   Shares: {shares}, Current: ${current_price:.2f}, Cost: ${avg_cost:.2f}\n"
                f"   Days held: {days_held}\n"
                f"   Unrealized P/L: ${unrealized_pl:.2f} ({unrealized_plpc:.2%})"
            )
            
            # Determine sell quantity - handle fractional shares properly
            if shares < 1.0:
                sell_qty = shares
                logger.info(f"   Fractional position: selling all {sell_qty} shares")
            else:
                sell_qty = round(shares - 1e-6, 4)
                logger.info(f"   Whole share position: selling {sell_qty} shares")
            
            try:
                order = api.submit_order(
                    symbol=ticker,
                    qty=sell_qty,
                    side="sell",
                    type="market",
                    time_in_force="day"
                )
                
                stats['sells_executed'] += 1
                
                trade_summary = (
                    f"FALLBACK SELL: {sell_qty} shares of {ticker} @ ${current_price:.2f}\n"
                    f"  Reason: {sell_reason}\n"
                    f"  P/L: ${unrealized_pl:.2f} ({unrealized_plpc:.2%})\n"
                    f"  Held: {days_held} days\n"
                    f"  Order ID: {order.id}"
                )
                
                trades_executed.append(trade_summary)
                logger.info(f"✅ {trade_summary}")
                
                # Remove from position tracking
                remove_position_tracking(ticker)
                
                # Log to trade history
                try:
                    log_trade(ticker, "FALLBACK_SELL", sell_qty, current_price, score=None)
                except Exception as log_error:
                    logger.warning(f"Could not log trade to history: {log_error}")
                
            except Exception as e:
                stats['sell_failures'] += 1
                error_msg = f"❌ FALLBACK SELL FAILED for {ticker}: {e}"
                logger.error(error_msg)
                errors.append(error_msg)
                continue
                
    except Exception as e:
        error_msg = f"❌ Critical error during fallback sell logic: {e}"
        logger.error(error_msg)
        errors.append(error_msg)
    
    # Generate comprehensive email report
    subject = f"Fallback Sell Report - {datetime.today().date()}"
    
    body_parts = [
        "="*60,
        "FALLBACK SELL EXECUTION SUMMARY",
        "="*60,
        "",
        "📊 STATISTICS:",
        f"  Total positions analyzed: {stats['total_positions']}",
        f"  Not held long enough: {stats['not_held_long_enough']}",
        f"  Meeting targets (no action): {stats['meeting_targets']}",
        f"  Triggered due to loss: {stats['below_cost']}",
        f"  Triggered due to low gain: {stats['low_gain']}",
        f"  ✅ Sells executed: {stats['sells_executed']}",
        f"  ❌ Sell failures: {stats['sell_failures']}",
        ""
    ]
    
    if trades_executed:
        body_parts.extend([
            "="*60,
            f"🔻 TRADES EXECUTED ({len(trades_executed)}):",
            "="*60,
            "",
            "\n\n".join(trades_executed),
            ""
        ])
        subject = f"⚠️ {len(trades_executed)} Fallback Sell(s) - {datetime.today().date()}"
    
    if skipped_positions:
        body_parts.extend([
            "="*60,
            f"⏭️  SKIPPED POSITIONS ({len(skipped_positions)}):",
            "="*60,
            "",
            "\n".join(skipped_positions),
            ""
        ])
    
    if errors:
        body_parts.extend([
            "="*60,
            f"❌ ERRORS ({len(errors)}):",
            "="*60,
            "",
            "\n".join(errors),
            ""
        ])
        subject = f"⚠️ Fallback Sell Errors - {datetime.today().date()}"
    
    body_parts.append("="*60)
    body = "\n".join(body_parts)
    
    send_email(subject, body, to_email=EMAIL_RECIPIENT)
    logger.info(f"📧 Email report sent to {EMAIL_RECIPIENT}: {subject}")


if __name__ == "__main__":
    logger.info("▶️ Starting Fallback Sell Executor")
    execute_fallback_sells()
    logger.info("✅ Fallback Sell Executor finished")
