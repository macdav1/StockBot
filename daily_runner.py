import subprocess
import datetime
import email_notifier
import trade_executor
from logger import logger


logger.info(f"===== DAILY RUN STARTED: {datetime.datetime.now()} =====")

logger.info("Running stock predictor...")
subprocess.run(["python3", "stock_predictor.py"])
logger.info("Predictions completed!")

logger.info("Running backtest runner...")
subprocess.run(["python3", "backtest_runner.py"])
logger.info("Backtest completed!")

logger.info("Running trading module...")
trades = trade_executor.execute_trades()

# Build trade report for email
if trades:
    trade_message = "\nTrades Executed:\n" + "\n".join(trades)
else:
    trade_message = "\nNo trades executed today."

email_notifier.send_prediction_report(extra_message=trade_message)

logger.info(f"===== DAILY RUN COMPLETED: {datetime.datetime.now()} =====")

