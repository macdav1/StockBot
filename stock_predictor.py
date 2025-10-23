import yfinance as yf
import pandas as pd
import numpy as np
from email_notifier import send_prediction_report, send_email
from datetime import datetime
from sklearn.preprocessing import StandardScaler
import xgboost as xgb
import joblib
import os
import json
import logging
from logger import logger
from logging.handlers import TimedRotatingFileHandler
import re
import warnings

warnings.simplefilter(action='ignore', category=FutureWarning)

# --- Logging setup ---
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "stock_predictor.log")
handler = TimedRotatingFileHandler(log_file, when="midnight", interval=1, backupCount=7, encoding="utf-8")
handler.suffix = "%Y-%m-%d"
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.setLevel(logging.INFO)
logger.addHandler(handler)
console = logging.StreamHandler()
console.setFormatter(formatter)
logger.addHandler(console)

# --- Features used in training (MUST match training script) ---
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

# --- Config ---
with open("config.json") as f:
    config = json.load(f)
score_threshold = config.get("score_threshold", 0.6)  # Default to 0.6 if not set
accuracy_threshold = config.get("accuracy_threshold", 0.55)  # Default to 0.55 if not set
model_path = config["model_path"]
scaler_path = config["scaler_path"]
data_period = config.get("data_period", "6mo")

logger.info(f"Config loaded: score_threshold={score_threshold}, accuracy_threshold={accuracy_threshold}")

# --- Load tickers and portfolio ---
with open("yahoo_top.txt") as f:
    tickers = [line.strip().upper() for line in f if line.strip()]
portfolio_df = pd.read_csv("portfolio.csv")
portfolio_tickers = set(portfolio_df["Ticker"].astype(str).str.strip())

# --- Exclusion patterns ---
EXCLUDE_TICKERS = {"SQQQ", "TQQQ", "UVXY", "SOXS", "SOXL", "SPXL", "SPXS",
                   "LABU", "LABD", "TECL", "TECS", "FNGU", "FNGD", "UDOW", "SDOW"}
_LEVERAGED_PATTERNS = re.compile(
    r'(2x|3x|Ultra|UltraShort|Ultra Pro|Ultra-Pro|Direxion|ProShares|Inverse|Daily|Leveraged|Short)',
    re.IGNORECASE
)

# --- Feature generation ---
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

        df.dropna(inplace=True)
        
        # Replace infinite values
        df.replace([np.inf, -np.inf], np.nan, inplace=True)
        df.dropna(inplace=True)
        
        return df
        
    except Exception as e:
        logger.warning(f"Error in generate_features: {e}")
        raise

# --- Prepare latest row ---
def prepare_latest_data(df, scaler):
    for col in FEATURE_COLS:
        if col not in df.columns:
            df[col] = 0.0
    latest = df.tail(1)[FEATURE_COLS].fillna(0)
    # Keep as DataFrame to preserve feature names
    scaled = scaler.transform(latest)
    return scaled, df

# --- Download data ---
def download_data(ticker):
    logger.info(f"Downloading data for {ticker}")
    df = yf.download(ticker, period=data_period, auto_adjust=False)
    df.dropna(inplace=True)
    return df

# --- Leveraged/inverse detection ---
def looks_like_leveraged(ticker):
    if ticker in EXCLUDE_TICKERS:
        return True
    try:
        info = yf.Ticker(ticker).info or {}
        name = info.get('longName') or info.get('shortName') or ""
        if _LEVERAGED_PATTERNS.search(name):
            return True
    except Exception:
        pass
    return False

# --- Load model with accuracy from metadata ---
def load_model():
    if os.path.exists(model_path) and os.path.exists(scaler_path):
        model = xgb.XGBClassifier()
        model.load_model(model_path)
        scaler = joblib.load(scaler_path)
        
        # Sanity check
        if model.n_features_in_ != len(FEATURE_COLS):
            raise ValueError(f"Model expects {model.n_features_in_} features, but FEATURE_COLS has {len(FEATURE_COLS)}")
        
        # Try to load accuracy from metadata file
        # Handle both .json and .xgb extensions
        if model_path.endswith('.json'):
            metadata_path = model_path.replace('.json', '_metadata.json')
        elif model_path.endswith('.xgb'):
            metadata_path = model_path.replace('.xgb', '_metadata.json')
        else:
            metadata_path = model_path + '_metadata.json'
        
        accuracy = 0.6  # Default fallback
        
        if os.path.exists(metadata_path):
            try:
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                    accuracy = metadata.get('accuracy', 0.6)
                    logger.info(f"Loaded model accuracy from metadata: {accuracy:.4f}")
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                logger.warning(f"Could not read metadata file (corrupted or invalid JSON): {e}")
                logger.warning(f"Using default accuracy: {accuracy}")
        else:
            logger.warning(f"No metadata file found at {metadata_path}, using default accuracy: {accuracy}")
        
        return model, scaler, accuracy
    else:
        raise RuntimeError("Model or scaler not found — run train_model_standalone.py first.")

# --- MAIN ---
def main():
    model, scaler, accuracy = load_model()
    predictions = []
    
    # Diagnostic counters
    stats = {
        'total': 0,
        'leveraged': 0,
        'no_data': 0,
        'predictions_up': 0,
        'predictions_down': 0,
        'passed_score': 0,
        'passed_accuracy': 0,
        'buy_signals': 0,
        'sell_signals': 0
    }

    # Download SPY for market trend
    spy_df = yf.download("SPY", period="60d", interval="1d", auto_adjust=False)
    spy_df['market_trend'] = spy_df['Close'].pct_change().fillna(0)

    for ticker in tickers:
        stats['total'] += 1
        try:
            if looks_like_leveraged(ticker):
                logger.info(f"Skipping leveraged/inverse ETF: {ticker}")
                stats['leveraged'] += 1
                continue

            df = download_data(ticker)
            if df.empty:
                logger.warning(f"Insufficient data for {ticker}")
                stats['no_data'] += 1
                continue

            df = generate_features(df, spy_df)
            missing_cols = [f for f in FEATURE_COLS if f not in df.columns]
            if missing_cols:
                logger.warning(f"{ticker} missing columns: {missing_cols}")
                continue

            latest_scaled, df = prepare_latest_data(df, scaler)

            prob = model.predict_proba(latest_scaled)
            prediction = "Up" if prob[0][1] > prob[0][0] else "Down"
            score = round(float(prob[0][1] if prediction == "Up" else prob[0][0]), 2)
            
            if prediction == "Up":
                stats['predictions_up'] += 1
            else:
                stats['predictions_down'] += 1
            
            logger.info(f"{ticker} → prediction={prediction}, score={score:.2f}, accuracy={accuracy:.4f}")

            # Determine signal with detailed logging
            signal = "-"
            if score >= score_threshold:
                stats['passed_score'] += 1
                if accuracy >= accuracy_threshold:
                    stats['passed_accuracy'] += 1
                    signal = "BUY" if prediction == "Up" else "SELL"
                    if signal == "BUY":
                        stats['buy_signals'] += 1
                    else:
                        stats['sell_signals'] += 1
                    logger.info(f"✅ {ticker} SIGNAL: {signal} (score={score:.2f}, accuracy={accuracy:.4f})")
                else:
                    logger.info(f"❌ {ticker} failed accuracy check: {accuracy:.4f} < {accuracy_threshold}")
            else:
                logger.info(f"❌ {ticker} failed score check: {score:.2f} < {score_threshold}")

            close_price = float(df['Close'].iloc[-1])

            predictions.append({
                "Date": datetime.now().strftime("%Y-%m-%d"),
                "Ticker": ticker,
                "Prediction": prediction,
                "Score": score,
                "Accuracy": round(accuracy, 4),
                "Signal": signal,
                "Close": close_price
            })

        except Exception as e:
            logger.warning(f"Unhandled exception for {ticker}: {e}")
            continue

    # --- Print diagnostic statistics ---
    logger.info("\n" + "="*60)
    logger.info("PREDICTION RUN STATISTICS")
    logger.info("="*60)
    logger.info(f"Total tickers processed: {stats['total']}")
    logger.info(f"Leveraged/excluded: {stats['leveraged']}")
    logger.info(f"No data available: {stats['no_data']}")
    logger.info(f"Successfully analyzed: {stats['predictions_up'] + stats['predictions_down']}")
    logger.info(f"  - Predicted UP: {stats['predictions_up']}")
    logger.info(f"  - Predicted DOWN: {stats['predictions_down']}")
    logger.info(f"Passed score threshold (≥{score_threshold}): {stats['passed_score']}")
    logger.info(f"Passed accuracy threshold (≥{accuracy_threshold}): {stats['passed_accuracy']}")
    logger.info(f"Final BUY signals: {stats['buy_signals']}")
    logger.info(f"Final SELL signals: {stats['sell_signals']}")
    logger.info("="*60 + "\n")

    # --- Save predictions ---
    df_all = pd.DataFrame(predictions)
    df_signals = df_all[df_all["Signal"].isin(["BUY", "SELL"])].sort_values(by='Score', ascending=False).head(6)

    df_all.to_csv("all_predictions.csv", index=False)
    df_signals.to_csv("predictions.csv", index=False)

    # --- Update history ---
    history_file = "predictions_history.csv"
    today = datetime.now().strftime("%Y-%m-%d")  # Format as string for consistency
    
    if os.path.exists(history_file):
        try:
            hist_df = pd.read_csv(history_file)
            
            # Convert Date column to string for comparison (handle mixed formats)
            if 'Date' in hist_df.columns:
                hist_df['Date'] = pd.to_datetime(hist_df['Date'], format='mixed', errors='coerce').dt.strftime('%Y-%m-%d')
            
            # Remove today's entries if they exist (avoid duplicates on re-runs)
            hist_df = hist_df[hist_df['Date'] != today]
            
            # Ensure df_signals has Date column as string
            df_signals_copy = df_signals.copy()
            df_signals_copy['Date'] = today
            
            # Append today's signals
            updated_hist = pd.concat([hist_df, df_signals_copy], ignore_index=True)
            updated_hist.to_csv(history_file, index=False)
            logger.info(f"📝 Updated {history_file} - added {len(df_signals_copy)} predictions for {today}")
        except Exception as e:
            logger.error(f"Error updating predictions history: {e}")
            # If history file is corrupted, start fresh
            logger.warning("Creating new predictions_history.csv")
            df_signals_copy = df_signals.copy()
            df_signals_copy['Date'] = today
            df_signals_copy.to_csv(history_file, index=False)
    else:
        logger.info(f"📝 Creating new {history_file}")
        df_signals_copy = df_signals.copy()
        df_signals_copy['Date'] = today
        df_signals_copy.to_csv(history_file, index=False)

    logger.info("✅ Predictions completed")
    
    if not df_signals.empty:
        logger.info("Top actionable signals:\n%s", df_signals.head(10).to_string())
        send_prediction_report(df_signals)
    else:
        logger.warning("⚠️ No actionable signals generated")
        logger.info("\nTROUBLESHOOTING SUGGESTIONS:")
        logger.info(f"1. Lower score_threshold in config.json (currently {score_threshold})")
        logger.info(f"2. Lower accuracy_threshold in config.json (currently {accuracy_threshold})")
        logger.info(f"3. Check model accuracy: {accuracy:.4f}")
        logger.info("4. Review all_predictions.csv to see score distribution")
        send_email("Daily Predictions", "⚠️ No actionable signals for today. Check logs for details.")

if __name__ == "__main__":
    main()
