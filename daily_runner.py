import subprocess
import datetime
import email_notifier
import trade_executor
from logger import logger


logger.info(f"===== DAILY RUN STARTED: {datetime.datetime.now()} =====")
### I will maintain cashflow.csv manually for now
##logger.info("Running cashflow updater...")
# Run cashflow updater before anything else
#subprocess.run(["python3", "update_cashflow_from_alpaca.py"])
###logger.info("Cashflow updater completed!")

##logger.info("Running backtest runner over last nights predictions...")
##subprocess.run(["python3", "backtest_runner.py"])
##logger.info("Backtest completed!")

logger.info("Updating portfolio.csv with the latest...")
subprocess.run(["python3", "import_portfolio.py"])
logger.info("Portfolio update complete!")

logger.info("Running the scrape yahoo for top gainers and active stock...")
subprocess.run(["python3", "scrape_yahoo.py"])
logger.info("Scrape Yahoo is completed!")

logger.info("Running stock predictor...")
subprocess.run(["python3", "stock_predictor.py"])
logger.info("Predictions completed!")

logger.info("Validate 3-day-old predictions...")
subprocess.run(["python3", "validate_predictions.py"])
logger.info("Predictions completed!")

logger.info("Running update google sheets for metrics...")
subprocess.run(["python3", "update_google_sheets.py"], check=True)
logger.info("✅ Update google sheets finished")

logger.info("Running Sentiment checker ...")
subprocess.run(["python3", "sentiment_checker.py"])
logger.info("✅ Sentiment checker finished")

logger.info("Running trading module...")
trades = trade_executor.execute_trades()

# Build trade report for email
if trades:
    trade_message = "\nTrades Executed:\n" + "\n".join(trades)
else:
    trade_message = "\nNo trades executed today."

email_notifier.send_prediction_report(extra_message=trade_message)

logger.info(f"===== DAILY RUN COMPLETED: {datetime.datetime.now()} =====")

