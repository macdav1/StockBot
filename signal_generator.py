# signal_generator.py

import pandas as pd

# Thresholds can be adjusted as you learn more
BUY_THRESHOLD = 0.6
SELL_THRESHOLD = 0.4

def generate_trade_signals(predictions_file='predictions.csv', signals_file='signals.csv'):
    df = pd.read_csv(predictions_file)

    actions = []
    for _, row in df.iterrows():
        score = row['Score']
        if score >= BUY_THRESHOLD:
            action = 'BUY'
        elif score <= SELL_THRESHOLD:
            action = 'SELL'
        else:
            action = 'HOLD'
        actions.append(action)

    df['Action'] = actions
    df.to_csv(signals_file, index=False)
    print(f"✅ Signals generated and saved to {signals_file}")

