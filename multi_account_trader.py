import subprocess
import os

def trade_account(account_name, env_file, config_file):
    """Execute trades for a specific account"""
    print(f"\n{'='*60}")
    print(f"TRADING FOR: {account_name}")
    print(f"{'='*60}\n")
    
    # Set environment variables from specific .env file
    env = os.environ.copy()
    with open(env_file) as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                key, value = line.strip().split('=', 1)
                env[key] = value
    
    # Run buy executor with specific config
    print(f"[1/2] Executing buy orders for {account_name}...")
    result = subprocess.run(
        ["python", "buy_executor.py", "--config", config_file],
        env=env,
        capture_output=True,
        text=True
    )
    print(result.stdout)
    
    # Run fallback sells with specific config
    print(f"[2/2] Checking fallback sells for {account_name}...")
    result = subprocess.run(
        ["python", "fallbacksell.py", "--config", config_file],
        env=env,
        capture_output=True,
        text=True
    )
    print(result.stdout)

def main():
    print("="*60)
    print("MULTI-ACCOUNT TRADING SYSTEM")
    print("="*60)
    
    # Trade for Dave
    trade_account("Dave", ".env.dave", "config_dave.json")
    
    # Trade for Friend
    trade_account("Friend", ".env.friend", "config_friend.json")
    
    print("\n" + "="*60)
    print("ALL ACCOUNTS PROCESSED")
    print("="*60)

if __name__ == "__main__":
    main()
