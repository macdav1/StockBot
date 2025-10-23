import os
import json
import logging
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
import alpaca_trade_api as tradeapi

# Assuming you have these utility functions from your old code
try:
    from utils.google_sheets import log_metrics
except ImportError:
    print("Warning: google_sheets module not found. Install or provide the module.")
    log_metrics = None

load_dotenv()

# Logging
log_file = "logs/google_sheets_updater.log"
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

# Alpaca API
API_KEY = os.getenv("ALPACA_API_KEY")
API_SECRET = os.getenv("ALPACA_SECRET_KEY")
BASE_URL = os.getenv("ALPACA_PAPER_BASE_URL")
api = tradeapi.REST(API_KEY, API_SECRET, BASE_URL, api_version='v2')


def get_account_metrics():
    """Get current account metrics from Alpaca"""
    try:
        account = api.get_account()
        
        metrics = {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'equity': float(account.equity),
            'cash': float(account.cash),
            'portfolio_value': float(account.portfolio_value),
            'buying_power': float(account.buying_power),
            'long_market_value': float(account.long_market_value),
            'initial_equity': float(account.last_equity) if hasattr(account, 'last_equity') else float(account.equity),
        }
        
        # Calculate day's P/L
        if hasattr(account, 'last_equity') and float(account.last_equity) > 0:
            daily_pl = float(account.equity) - float(account.last_equity)
            daily_pl_pct = (daily_pl / float(account.last_equity)) * 100
        else:
            daily_pl = 0
            daily_pl_pct = 0
        
        metrics['daily_pl'] = round(daily_pl, 2)
        metrics['daily_pl_pct'] = round(daily_pl_pct, 2)
        
        return metrics
        
    except Exception as e:
        logger.error(f"Error getting account metrics: {e}")
        return {}


def get_position_metrics():
    """Get metrics about current positions"""
    try:
        positions = api.list_positions()
        
        if not positions:
            return {
                'num_positions': 0,
                'total_pl': 0,
                'total_pl_pct': 0,
                'avg_position_age': 0
            }
        
        total_pl = sum(float(p.unrealized_pl) for p in positions)
        avg_pl_pct = sum(float(p.unrealized_plpc) for p in positions) / len(positions) * 100
        
        # Get position ages from tracking file
        from position_tracker import get_position_age
        ages = []
        for p in positions:
            age = get_position_age(p.symbol)
            if age is not None:
                ages.append(age)
        
        avg_age = sum(ages) / len(ages) if ages else 0
        
        return {
            'num_positions': len(positions),
            'total_pl': round(total_pl, 2),
            'total_pl_pct': round(avg_pl_pct, 2),
            'avg_position_age': round(avg_age, 1)
        }
        
    except Exception as e:
        logger.error(f"Error getting position metrics: {e}")
        return {}


def get_prediction_metrics():
    """Get metrics from validation results"""
    try:
        validation_file = "prediction_validations.csv"
        
        if not os.path.exists(validation_file):
            return {
                'predictions_validated': 0,
                'prediction_accuracy': 0,
                'high_conf_accuracy': 0
            }
        
        df = pd.read_csv(validation_file)
        
        if df.empty:
            return {
                'predictions_validated': 0,
                'prediction_accuracy': 0,
                'high_conf_accuracy': 0
            }
        
        # Overall accuracy
        total = len(df)
        correct = df['Correct'].sum()
        accuracy = (correct / total * 100) if total > 0 else 0
        
        # High confidence accuracy (>=0.70)
        high_conf = df[df['Score'] >= 0.70]
        if not high_conf.empty:
            high_conf_correct = high_conf['Correct'].sum()
            high_conf_accuracy = (high_conf_correct / len(high_conf) * 100)
        else:
            high_conf_accuracy = 0
        
        return {
            'predictions_validated': total,
            'prediction_accuracy': round(accuracy, 2),
            'high_conf_accuracy': round(high_conf_accuracy, 2)
        }
        
    except Exception as e:
        logger.error(f"Error getting prediction metrics: {e}")
        return {}


def get_cashflow_metrics():
    """Calculate monthly and YTD profit based on cashflow.csv"""
    try:
        cashflow_file = "cashflow.csv"
        
        if not os.path.exists(cashflow_file):
            logger.warning(f"{cashflow_file} not found, creating new one")
            # Create initial file with current equity as baseline
            account = api.get_account()
            current_equity = float(account.equity)
            
            df = pd.DataFrame([{
                'Date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'Type': 'BASELINE',
                'Amount': current_equity,
                'Notes': 'Initial baseline - auto-created'
            }])
            df.to_csv(cashflow_file, index=False)
            
            return {
                'monthly_profit_pct': 0,
                'ytd_profit_pct': 0,
                'monthly_profit': 0,
                'ytd_profit': 0
            }
        
        # Read cashflow
        df = pd.read_csv(cashflow_file)
        df['Date'] = pd.to_datetime(df['Date'], format='mixed', errors='coerce')
        df = df.sort_values('Date')
        
        # Get current equity
        account = api.get_account()
        current_equity = float(account.equity)
        
        # Current date boundaries
        today = datetime.now()
        start_of_month = datetime(today.year, today.month, 1)
        start_of_year = datetime(today.year, 1, 1)
        
        # === MONTHLY PROFIT ===
        # Get month start baseline (most recent BASELINE before/on start of month)
        month_baselines = df[(df['Date'] <= start_of_month) & (df['Type'] == 'BASELINE')]
        if not month_baselines.empty:
            month_start_equity = float(month_baselines.iloc[-1]['Amount'])
        else:
            # No baseline, use earliest entry
            month_start_equity = float(df.iloc[0]['Amount'])
        
        # Get deposits/withdrawals THIS MONTH
        month_flows = df[(df['Date'] >= start_of_month) & (df['Type'].isin(['DEPOSIT', 'WITHDRAWAL']))]
        month_deposits = month_flows[month_flows['Type'] == 'DEPOSIT']['Amount'].sum()
        month_withdrawals = month_flows[month_flows['Type'] == 'WITHDRAWAL']['Amount'].sum()
        month_net_flow = month_deposits - month_withdrawals
        
        # Monthly profit = Current Equity - (Start Equity + Net Deposits)
        monthly_profit = current_equity - (month_start_equity + month_net_flow)
        monthly_profit_pct = (monthly_profit / month_start_equity * 100) if month_start_equity > 0 else 0
        
        # === YTD PROFIT ===
        # Get year start baseline
        year_baselines = df[(df['Date'] <= start_of_year) & (df['Type'] == 'BASELINE')]
        if not year_baselines.empty:
            year_start_equity = float(year_baselines.iloc[-1]['Amount'])
        else:
            year_start_equity = float(df.iloc[0]['Amount'])
        
        # Get deposits/withdrawals THIS YEAR
        year_flows = df[(df['Date'] >= start_of_year) & (df['Type'].isin(['DEPOSIT', 'WITHDRAWAL']))]
        year_deposits = year_flows[year_flows['Type'] == 'DEPOSIT']['Amount'].sum()
        year_withdrawals = year_flows[year_flows['Type'] == 'WITHDRAWAL']['Amount'].sum()
        year_net_flow = year_deposits - year_withdrawals
        
        # YTD profit = Current Equity - (Start Equity + Net Deposits)
        ytd_profit = current_equity - (year_start_equity + year_net_flow)
        ytd_profit_pct = (ytd_profit / year_start_equity * 100) if year_start_equity > 0 else 0
        
        logger.info(f"Month: Start=${month_start_equity:.2f}, Flow=${month_net_flow:.2f}, Current=${current_equity:.2f}, Profit=${monthly_profit:.2f}")
        logger.info(f"YTD: Start=${year_start_equity:.2f}, Flow=${year_net_flow:.2f}, Current=${current_equity:.2f}, Profit=${ytd_profit:.2f}")
        
        return {
            'monthly_profit_pct': round(monthly_profit_pct, 2),
            'ytd_profit_pct': round(ytd_profit_pct, 2),
            'monthly_profit': round(monthly_profit, 2),
            'ytd_profit': round(ytd_profit, 2)
        }
        
    except Exception as e:
        logger.error(f"Error calculating cashflow metrics: {e}", exc_info=True)
        return {
            'monthly_profit_pct': 0,
            'ytd_profit_pct': 0,
            'monthly_profit': 0,
            'ytd_profit': 0
        }


def auto_update_cashflow():
    """
    Auto-update cashflow.csv with monthly baseline if needed.
    Checks Alpaca for deposits/withdrawals and logs them.
    """
    try:
        cashflow_file = "cashflow.csv"
        
        # Get current equity
        account = api.get_account()
        current_equity = float(account.equity)
        
        # Load or create cashflow file
        if os.path.exists(cashflow_file):
            df = pd.read_csv(cashflow_file)
            df['Date'] = pd.to_datetime(df['Date'], format='mixed', errors='coerce')
        else:
            df = pd.DataFrame(columns=['Date', 'Type', 'Amount', 'Notes'])
        
        today = datetime.now()
        start_of_month = datetime(today.year, today.month, 1)
        
        # Check if we need a monthly baseline for this month
        month_baselines = df[(df['Date'] >= start_of_month) & (df['Type'] == 'BASELINE')]
        
        if month_baselines.empty:
            # Add monthly baseline
            new_entry = pd.DataFrame([{
                'Date': start_of_month.strftime('%Y-%m-%d %H:%M:%S'),
                'Type': 'BASELINE',
                'Amount': current_equity,
                'Notes': 'Auto-generated monthly baseline'
            }])
            df = pd.concat([df, new_entry], ignore_index=True)
            df.to_csv(cashflow_file, index=False)
            logger.info(f"✅ Added monthly baseline: ${current_equity:.2f}")
        
        # Optional: Detect deposits/withdrawals by comparing account activities
        # This would require checking Alpaca's account_activities endpoint
        # For now, user maintains manually which is fine
        
    except Exception as e:
        logger.error(f"Error auto-updating cashflow: {e}")


def get_trade_metrics():
    """Get metrics from trade history"""
    try:
        history_file = "predictions_history.csv"
        
        if not os.path.exists(history_file):
            return {
                'total_signals_7d': 0,
                'buy_signals_7d': 0,
                'sell_signals_7d': 0
            }
        
        df = pd.read_csv(history_file)
        
        if df.empty:
            return {
                'total_signals_7d': 0,
                'buy_signals_7d': 0,
                'sell_signals_7d': 0
            }
        
        # Count signals from last 7 days - handle mixed date formats
        df['Date'] = pd.to_datetime(df['Date'], format='mixed', errors='coerce')
        week_ago = pd.Timestamp.now() - pd.Timedelta(days=7)
        recent = df[df['Date'] >= week_ago]
        
        buy_count = len(recent[recent['Signal'] == 'BUY'])
        sell_count = len(recent[recent['Signal'] == 'SELL'])
        
        return {
            'total_signals_7d': len(recent),
            'buy_signals_7d': buy_count,
            'sell_signals_7d': sell_count
        }
        
    except Exception as e:
        logger.error(f"Error getting trade metrics: {e}")
        return {
            'total_signals_7d': 0,
            'buy_signals_7d': 0,
            'sell_signals_7d': 0
        }


def update_google_sheets():
    """Collect all metrics and update Google Sheets"""
    
    logger.info("="*60)
    logger.info("COLLECTING METRICS FOR GOOGLE SHEETS")
    logger.info("="*60)
    
    try:
        # Collect all metrics
        metrics = {}
        
        # Account metrics
        logger.info("Getting account metrics...")
        account_metrics = get_account_metrics()
        metrics.update(account_metrics)
        
        # Position metrics
        logger.info("Getting position metrics...")
        position_metrics = get_position_metrics()
        metrics.update(position_metrics)
        
        # Prediction metrics
        logger.info("Getting prediction metrics...")
        prediction_metrics = get_prediction_metrics()
        metrics.update(prediction_metrics)
        
        # Trade metrics
        logger.info("Getting trade metrics...")
        trade_metrics = get_trade_metrics()
        metrics.update(trade_metrics)
        
        # Cashflow metrics (Monthly/YTD profit)
        logger.info("Calculating cashflow metrics...")
        cashflow_metrics = get_cashflow_metrics()
        metrics.update(cashflow_metrics)
        
        # Auto-update cashflow if needed
        auto_update_cashflow()
        
        # Log metrics
        logger.info("\n📊 Metrics collected:")
        for key, value in metrics.items():
            logger.info(f"   {key}: {value}")
        
        # Update Google Sheets
        if log_metrics and metrics:
            logger.info("\nUpdating Google Sheets...")
            log_metrics(metrics)
            logger.info("✅ Google Sheets updated successfully")
        else:
            if not log_metrics:
                logger.warning("⚠️  log_metrics function not available, skipping Google Sheets update")
            if not metrics:
                logger.warning("⚠️  No metrics collected, skipping Google Sheets update")
        
        logger.info("="*60)
        return metrics
        
    except Exception as e:
        logger.error(f"❌ Error updating Google Sheets: {e}", exc_info=True)
        return {}


if __name__ == "__main__":
    logger.info("▶️ Starting Google Sheets Updater")
    update_google_sheets()
    logger.info("✅ Google Sheets Updater finished")
