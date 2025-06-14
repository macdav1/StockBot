import subprocess
import datetime
import email_notifier

print(f"===== DAILY RUN STARTED: {datetime.datetime.now()} =====")

# Run the stock predictor
print("Running stock predictor...")
subprocess.run(["python3", "Stock_app/stock_predictor.py"])

# Run the backtest
print("Running backtest runner...")
subprocess.run(["python3", "Stock_app/backtest_runner.py"])

# Send heartbeat email
today = datetime.date.today()
subject = f"✅ StockBot Heartbeat - {today}"
body = f"Stock predictor and backtest completed successfully on {today}."

email_notifier.send_email(subject, body)

print(f"===== DAILY RUN COMPLETED: {datetime.datetime.now()} =====")

