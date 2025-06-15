import subprocess
import email_notifier
import trader

print("===== DAILY RUN STARTED =====")
print("Running stock predictor...")
subprocess.run(["python3", "stock_predictor.py"])

print("Running backtest runner...")
subprocess.run(["python3", "backtest_runner.py"])

print("Running trading module...")
trades = trader.run_trader()

# Email report as usual
email_notifier.send_prediction_report(extra_message="\nTrades Executed:\n" + "\n".join(trades) if trades else "\nNo trades executed today.")

print("===== DAILY RUN COMPLETED =====")

