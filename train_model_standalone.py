import os
import pandas as pd
import yfinance as yf
import numpy as np
from datetime import datetime
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.utils import resample
import joblib
import xgboost as xgb
import json
import warnings
warnings.filterwarnings("ignore")

# Custom JSON encoder for numpy types
class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return super(NumpyEncoder, self).default(obj)

MODEL_PATH = "trained_model.xgb"
SCALER_PATH = "scaler.pkl"
METADATA_PATH = "trained_model_metadata.json"

# ✅ Enhanced feature set with technical indicators
FEATURE_COLS = [
    # Original features
    'Return', 'MA5', 'MA10', 'market_trend',
    # Momentum indicators
    'RSI', 'MACD', 'MACD_Signal', 'MACD_Hist',
    # Volatility
    'ATR', 'Volatility_20',
    # Volume
    'Volume_Ratio', 'Volume_MA5',
    # Price patterns
    'High_Low_Ratio', 'Close_to_MA20',
    # Additional moving averages
    'MA20', 'MA_Ratio_5_20'
]

# Read tickers - now using yahoo_top.txt for momentum stocks
#ticker_file = "yhoo_top.txt" if os.path.exists("yahoo_top.txt") else "top_100_stocks.txt"
ticker_file = "top_100_stocks.txt"
with open(ticker_file) as f:
    tickers = [line.strip() for line in f if line.strip()]

print(f"Loaded {len(tickers)} tickers from {ticker_file}")

# --- TECHNICAL INDICATOR CALCULATIONS ---
def calculate_rsi(series, period=14):
    """Calculate Relative Strength Index"""
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_macd(series, fast=12, slow=26, signal=9):
    """Calculate MACD, Signal, and Histogram"""
    ema_fast = series.ewm(span=fast).mean()
    ema_slow = series.ewm(span=slow).mean()
    macd = ema_fast - ema_slow
    macd_signal = macd.ewm(span=signal).mean()
    macd_hist = macd - macd_signal
    return macd, macd_signal, macd_hist

def calculate_atr(df, period=14):
    """Calculate Average True Range"""
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    
    # Stack vertically and take max to ensure we get a Series
    true_range = pd.DataFrame({
        'hl': high_low,
        'hc': high_close,
        'lc': low_close
    }).max(axis=1)
    
    atr = true_range.rolling(period).mean()
    return atr

# --- ENHANCED FEATURE GENERATION ---
def generate_features(df, spy_df=None):
    try:
        df = df.copy()
        
        # Ensure we're working with proper column structure
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        
        # Original features
        df['Return'] = df['Close'].pct_change()
        df['MA5'] = df['Close'].rolling(5).mean()
        df['MA10'] = df['Close'].rolling(10).mean()
        df['MA20'] = df['Close'].rolling(20).mean()
        
        # Moving average ratios - ensure Series output
        ma5_values = df['MA5'].values
        ma20_values = df['MA20'].values
        close_values = df['Close'].values
        
        df['MA_Ratio_5_20'] = pd.Series(ma5_values / ma20_values, index=df.index)
        df['Close_to_MA20'] = pd.Series((close_values - ma20_values) / ma20_values, index=df.index)
        
        # RSI
        df['RSI'] = calculate_rsi(df['Close'])
        
        # MACD - unpack carefully
        macd_result = calculate_macd(df['Close'])
        df['MACD'] = macd_result[0]
        df['MACD_Signal'] = macd_result[1]
        df['MACD_Hist'] = macd_result[2]
        
        # ATR (volatility)
        df['ATR'] = calculate_atr(df)
        
        # Volatility (20-day rolling standard deviation of returns)
        df['Volatility_20'] = df['Return'].rolling(20).std()
        
        # Volume indicators - ensure Series output
        volume_values = df['Volume'].values
        volume_ma20 = df['Volume'].rolling(20).mean().values
        
        df['Volume_MA5'] = df['Volume'].rolling(5).mean()
        df['Volume_Ratio'] = pd.Series(volume_values / volume_ma20, index=df.index)
        
        # Price patterns - ensure Series output
        high_values = df['High'].values
        low_values = df['Low'].values
        
        df['High_Low_Ratio'] = pd.Series((high_values - low_values) / close_values, index=df.index)
        
        # Market trend (SPY)
        if spy_df is not None:
            if isinstance(spy_df.columns, pd.MultiIndex):
                spy_df.columns = spy_df.columns.droplevel(1)
            spy_df['market_trend'] = spy_df['Close'].pct_change().fillna(0)
            df['market_trend'] = spy_df['market_trend'].reindex(df.index).fillna(0)
        else:
            df['market_trend'] = 0.0
        
        # Label for 3-day forward prediction (changed from next-day)
        df['Label'] = (df['Close'].shift(-3) > df['Close']).astype(int)
        
        # Drop NaN values
        df.dropna(inplace=True)
        
        # Replace infinite values with NaN and then drop
        df.replace([np.inf, -np.inf], np.nan, inplace=True)
        df.dropna(inplace=True)
        
        return df
        
    except Exception as e:
        print(f"Error in generate_features: {e}")
        raise

# --- GET TRAINING DATA ---
def get_training_data(tickers):
    all_data = []
    
    # Download SPY with longer history for better market trend
    spy_df = yf.download("SPY", period="2y", auto_adjust=False)
    
    successful = 0
    failed = 0
    
    for ticker in tickers:
        try:
            print(f"Fetching data for {ticker}...")
            # Use 2 years for more training data
            df = yf.download(ticker, period="2y", auto_adjust=False, progress=False)
            
            if df.empty or len(df) < 50:  # Increased minimum to 50 days
                print(f"⚠️  Not enough data for {ticker}, skipping.")
                failed += 1
                continue
            
            df = generate_features(df, spy_df)
            
            if len(df) < 30:  # After feature generation, need at least 30 rows
                print(f"⚠️  Insufficient data after feature generation for {ticker}")
                failed += 1
                continue
            
            df['Ticker'] = ticker
            all_data.append(df)
            successful += 1
            
        except Exception as e:
            print(f"⚠️  Failed to get data for {ticker}: {e}")
            failed += 1
    
    print(f"\n✅ Successfully loaded: {successful} tickers")
    print(f"❌ Failed/skipped: {failed} tickers")
    
    if not all_data:
        raise RuntimeError("No training data available for any tickers.")
    
    combined_df = pd.concat(all_data)
    print(f"📊 Total training samples: {len(combined_df)}")
    
    return combined_df

# --- TRAIN MODEL ---
def train_model():
    print("\n" + "="*60)
    print("STARTING MODEL TRAINING - 3-DAY FORWARD PREDICTION")
    print(f"Training Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60 + "\n")
    
    df = get_training_data(tickers)
    
    # Check label distribution BEFORE balancing
    label_counts = df['Label'].value_counts()
    print(f"\n📊 Label Distribution (BEFORE balancing):")
    print(f"   Up days (1): {label_counts.get(1, 0)} ({label_counts.get(1, 0)/len(df)*100:.1f}%)")
    print(f"   Down days (0): {label_counts.get(0, 0)} ({label_counts.get(0, 0)/len(df)*100:.1f}%)")
    
    # ✅ BALANCE THE CLASSES to fix bias
    df_up = df[df['Label'] == 1]
    df_down = df[df['Label'] == 0]
    
    # Upsample minority class to match majority
    if len(df_down) > len(df_up):
        print(f"\n⚖️  Upsampling UP class from {len(df_up)} to {len(df_down)} samples...")
        df_up_resampled = resample(df_up, n_samples=len(df_down), random_state=42, replace=True)
        df = pd.concat([df_up_resampled, df_down])
    else:
        print(f"\n⚖️  Upsampling DOWN class from {len(df_down)} to {len(df_up)} samples...")
        df_down_resampled = resample(df_down, n_samples=len(df_up), random_state=42, replace=True)
        df = pd.concat([df_up, df_down_resampled])
    
    # Shuffle the balanced dataset
    df = df.sample(frac=1, random_state=42).reset_index(drop=True)
    
    # Check label distribution AFTER balancing
    label_counts = df['Label'].value_counts()
    print(f"\n📊 Label Distribution (AFTER balancing):")
    print(f"   Up days (1): {label_counts.get(1, 0)} ({label_counts.get(1, 0)/len(df)*100:.1f}%)")
    print(f"   Down days (0): {label_counts.get(0, 0)} ({label_counts.get(0, 0)/len(df)*100:.1f}%)")
    print(f"   Total samples: {len(df)}")
    
    X = df[FEATURE_COLS]
    y = df['Label']
    
    # Check for any remaining NaN or inf values
    if X.isnull().any().any():
        print("\n⚠️  Warning: NaN values found in features, dropping...")
        mask = ~X.isnull().any(axis=1)
        X = X[mask]
        y = y[mask]
    
    print(f"\n📊 Feature matrix shape: {X.shape}")
    print(f"📊 Features: {len(FEATURE_COLS)}")
    
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # Enhanced XGBoost parameters for better performance
    model = xgb.XGBClassifier(
        use_label_encoder=False,
        eval_metric="logloss",
        n_estimators=300,        # Increased from 200
        learning_rate=0.03,      # Slightly lower for better generalization
        max_depth=5,             # Increased from 4 for more complex patterns
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=3,      # Prevent overfitting
        gamma=0.1,               # Minimum loss reduction
        reg_alpha=0.1,           # L1 regularization
        reg_lambda=1.0,          # L2 regularization
        random_state=42
    )
    
    print("\n🔄 Training model...")
    model.fit(X_train_scaled, y_train)
    
    # Predictions and evaluation
    y_pred = model.predict(X_test_scaled)
    y_pred_proba = model.predict_proba(X_test_scaled)
    
    accuracy = accuracy_score(y_test, y_pred)
    
    print("\n" + "="*60)
    print(f"✅ TRAINING COMPLETE - Accuracy: {accuracy:.4f} ({accuracy*100:.2f}%)")
    print("="*60)
    
    # Detailed classification report
    print("\n📊 Classification Report:")
    print(classification_report(y_test, y_pred, target_names=['Down', 'Up']))
    
    # Confusion matrix
    cm = confusion_matrix(y_test, y_pred)
    print("\n📊 Confusion Matrix:")
    print(f"                Predicted Down  Predicted Up")
    print(f"Actual Down     {cm[0][0]:>14}  {cm[0][1]:>12}")
    print(f"Actual Up       {cm[1][0]:>14}  {cm[1][1]:>12}")
    
    # Calculate high-confidence accuracy
    high_conf_threshold = 0.65
    high_conf_mask = (y_pred_proba.max(axis=1) >= high_conf_threshold)
    if high_conf_mask.sum() > 0:
        high_conf_acc = accuracy_score(y_test[high_conf_mask], y_pred[high_conf_mask])
        print(f"\n📊 High Confidence Accuracy (≥{high_conf_threshold}):")
        print(f"   Accuracy: {high_conf_acc:.4f} ({high_conf_acc*100:.2f}%)")
        print(f"   Samples: {high_conf_mask.sum()} ({high_conf_mask.sum()/len(y_test)*100:.1f}%)")
    
    # Save model + scaler
    model.save_model(MODEL_PATH)
    joblib.dump(scaler, SCALER_PATH)
    print(f"\n💾 Model saved to {MODEL_PATH}")
    print(f"💾 Scaler saved to {SCALER_PATH}")
    
    # Feature importance
    importances = model.feature_importances_
    print("\n📊 Feature Importance (Top 10):")
    feature_importance = sorted(zip(FEATURE_COLS, importances), key=lambda x: -x[1])
    for i, (name, imp) in enumerate(feature_importance[:10], 1):
        print(f"   {i:2d}. {name:<20}: {imp:.4f}")
    
    # Save metadata with enhanced info
    metadata = {
        'accuracy': float(accuracy),
        'trained_date': str(datetime.now()),
        'prediction_horizon': '3-day',  # Added to track prediction timeframe
        'score_threshold_recommended': float(0.60 if accuracy >= 0.60 else 0.55),
        'feature_count': int(len(FEATURE_COLS)),
        'features': list(FEATURE_COLS),
        'training_samples': int(len(X_train)),
        'test_samples': int(len(X_test)),
        'ticker_source': str(ticker_file),
        'data_period': '2y',
        'label_distribution': {
            'up': int(label_counts.get(1, 0)),
            'down': int(label_counts.get(0, 0))
        },
        'model_params': {
            'n_estimators': 300,
            'learning_rate': 0.03,
            'max_depth': 5,
            'subsample': 0.8,
            'colsample_bytree': 0.8
        },
        'feature_importance': {str(name): float(imp) for name, imp in feature_importance[:10]}
    }
    
    with open(METADATA_PATH, 'w') as f:
        json.dump(metadata, f, indent=2, cls=NumpyEncoder)
    
    print(f"💾 Metadata saved to {METADATA_PATH}")
    
    # Recommendations
    print("\n" + "="*60)
    print("📋 RECOMMENDATIONS:")
    print("="*60)
    if accuracy >= 0.65:
        print("✅ Excellent accuracy! Model is ready for live trading.")
        print(f"   Recommended score_threshold: 0.60-0.65")
    elif accuracy >= 0.58:
        print("✅ Good accuracy. Model should perform well.")
        print(f"   Recommended score_threshold: 0.58-0.62")
    elif accuracy >= 0.52:
        print("⚠️  Moderate accuracy. Use with caution.")
        print(f"   Recommended score_threshold: 0.60+ (be selective)")
        print("   Consider paper trading first.")
    else:
        print("❌ Low accuracy. Model needs improvement.")
        print("   Do NOT use for live trading.")
        print("   Suggestions:")
        print("   - Collect more diverse training data")
        print("   - Try different prediction targets (3-5 day returns)")
        print("   - Consider ensemble methods")
    
    print("\n" + "="*60 + "\n")
    
    return model, scaler, accuracy

if __name__ == "__main__":
    train_model()
