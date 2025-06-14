import subprocess
import datetime
import email_notifier

print(f"===== DAILY RUN STARTED: {datetime.datetime.now()} =====")

# Run stock predictor
print("Running stock predictor...")
subprocess.run(["python3", "stock_predictor.py"])

# Run backtest
print("Running backtest runner...")
subprocess.run(["python3", "backtest_runner.py"])

# Send email report
email_notifier.send_prediction_report()

print(f"===== DAILY RUN COMPLETED: {datetime.datetime.now()} =====")

