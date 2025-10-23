import json
import os
import hashlib
from datetime import datetime

def get_tracking_file():
    """Generate tracking filename based on API key"""
    api_key = os.getenv("ALPACA_API_KEY", "default")
    # Create short hash of API key for filename
    key_hash = hashlib.md5(api_key.encode()).hexdigest()[:8]
    return f"position_tracking_{key_hash}.json"

def load_position_tracking():
    """Load position tracking data from file"""
    tracking_file = get_tracking_file()
    if os.path.exists(tracking_file):
        try:
            with open(tracking_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading position tracking: {e}")
            return {}
    return {}

def save_position_tracking(tracking_data):
    """Save position tracking data to file"""
    tracking_file = get_tracking_file()
    try:
        with open(tracking_file, 'w') as f:
            json.dump(tracking_data, f, indent=2)
    except Exception as e:
        print(f"Error saving position tracking: {e}")

def track_new_position(ticker, entry_price, quantity):
    """
    Track a new position when opened.
    Call this from your buy script after order fills.
    """
    tracking = load_position_tracking()
    
    if ticker not in tracking:
        tracking[ticker] = {
            "purchase_date": datetime.now().strftime("%Y-%m-%d"),
            "entry_price": float(entry_price),
            "initial_quantity": float(quantity),
            "opened_at": datetime.now().isoformat()
        }
        save_position_tracking(tracking)
        print(f"✅ Tracking new position: {ticker} @ ${entry_price}")
    else:
        # Position already exists - could be adding to position
        print(f"ℹ️  Position {ticker} already tracked since {tracking[ticker]['purchase_date']}")

def remove_position_tracking(ticker):
    """
    Remove position tracking when fully closed.
    Call this from your sell script after position fully closed.
    """
    tracking = load_position_tracking()
    
    if ticker in tracking:
        del tracking[ticker]
        save_position_tracking(tracking)
        print(f"✅ Removed position tracking: {ticker}")
    else:
        print(f"ℹ️  Position {ticker} was not being tracked")

def get_position_age(ticker):
    """
    Get number of days a position has been held.
    Returns None if position not tracked.
    """
    tracking = load_position_tracking()
    
    if ticker not in tracking:
        return None
    
    purchase_date = datetime.strptime(tracking[ticker]["purchase_date"], "%Y-%m-%d")
    days_held = (datetime.now() - purchase_date).days
    return days_held

def get_position_info(ticker):
    """
    Get all tracking info for a position.
    Returns None if position not tracked.
    """
    tracking = load_position_tracking()
    return tracking.get(ticker)

def sync_with_broker_positions(api):
    """
    Sync tracking file with actual broker positions.
    Adds any missing positions, removes closed positions.
    Call this periodically (e.g., daily) to keep in sync.
    
    Args:
        api: Alpaca API connection object
    """
    tracking = load_position_tracking()
    
    try:
        # Get current positions from broker using provided API connection
        current_positions = {pos.symbol: pos for pos in api.list_positions()}
        
        # Add any positions not being tracked
        for ticker, position in current_positions.items():
            if ticker not in tracking:
                print(f"⚠️  Found untracked position: {ticker}, adding to tracking")
                # Estimate purchase date as today (best we can do)
                tracking[ticker] = {
                    "purchase_date": datetime.now().strftime("%Y-%m-%d"),
                    "entry_price": float(position.avg_entry_price),
                    "initial_quantity": float(position.qty),
                    "opened_at": datetime.now().isoformat(),
                    "note": "Added during sync - actual purchase date may be earlier"
                }
        
        # Remove tracking for positions that are closed
        tracked_tickers = list(tracking.keys())
        for ticker in tracked_tickers:
            if ticker not in current_positions:
                print(f"ℹ️  Position {ticker} is closed, removing from tracking")
                del tracking[ticker]
        
        save_position_tracking(tracking)
        print(f"✅ Sync complete: tracking {len(tracking)} positions")
        
    except Exception as e:
        print(f"Error syncing with broker: {e}")

def initialize_from_current_positions(api):
    """
    Initialize tracking file from current broker positions.
    Use this once to start tracking existing positions.
    
    Args:
        api: Alpaca API connection object
    """
    print("Initializing position tracking from current positions...")
    
    try:
        positions = api.list_positions()
        tracking = {}
        
        for position in positions:
            ticker = position.symbol
            tracking[ticker] = {
                "purchase_date": datetime.now().strftime("%Y-%m-%d"),
                "entry_price": float(position.avg_entry_price),
                "initial_quantity": float(position.qty),
                "opened_at": datetime.now().isoformat(),
                "note": "Initialized from existing position - actual purchase date unknown"
            }
            print(f"  Added {ticker} @ ${position.avg_entry_price}")
        
        save_position_tracking(tracking)
        print(f"✅ Initialized tracking for {len(tracking)} positions")
        
    except Exception as e:
        print(f"Error initializing tracking: {e}")

if __name__ == "__main__":
    # Example usage / testing
    print("Position tracker module loaded.")
    print("Use track_new_position(), get_position_age(), etc. from your scripts.")
