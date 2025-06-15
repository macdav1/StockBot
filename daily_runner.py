# daily_runner.py

import subprocess
import email_notifier
import signal_generator

from datetime import datetime

print(f"===== DAILY RUN STARTED: {datetime.now()} =====")

print("Running stock predictor...")
subprocess.run(["python3", "stock_predictor.py"])

print("Running backtest runner...")
subprocess.run(["python3", "backtest_runner.py"])

# Generate signals
print("Generating trading signals...")
signal_generator.generate_trade_signals()

# Send email report
email_notifier.send_prediction_report()

print(f"===== DAILY RUN COMPLETED: {datetime.now()} =====")

