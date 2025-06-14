import subprocess
import datetime
import email_notifier

print(f"===== DAILY RUN STARTED: {datetime.datetime.now()} =====")

print("Running stock predictor...")
subprocess.run(['bash', 'run_predictor.sh'])

print("Running backtest runner...")
subprocess.run(['bash', 'run_backtester.sh'])

today = datetime.date.today()
subject = f"✅ StockBot Heartbeat - {today}"
body = f"Stock predictor and backtest completed successfully on {today}."
email_notifier.send_email(subject, body)

print(f"===== DAILY RUN COMPLETED: {datetime.datetime.now()} =====")

