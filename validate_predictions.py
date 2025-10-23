import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import os
import json
from email_notifier import send_email

PREDICTIONS_FILE = "predictions.csv"
VALIDATION_FILE = "prediction_validations.csv"
REPORT_FILE = "prediction_performance_report.txt"

def validate_predictions():
    """
    Check predictions made 3 days ago to see if they were correct.
    Predictions are for 3-day forward moves, so we check after 3 days.
    """
    
    print("\n" + "="*60)
    print("PREDICTION VALIDATION - 3-DAY RESULTS")
    print("="*60 + "\n")
    
    # Check if predictions history exists
    if not os.path.exists("predictions_history.csv"):
        print("❌ No predictions_history.csv found. Need historical predictions to validate.")
        return
    
    # Load all historical predictions
    history_df = pd.read_csv("predictions_history.csv")
    history_df['Date'] = pd.to_datetime(history_df['Date'], format='mixed', errors='coerce')
    
    # Clean up: Remove rows with invalid dates
    before_cleanup = len(history_df)
    history_df = history_df.dropna(subset=['Date'])
    after_cleanup = len(history_df)
    
    if before_cleanup > after_cleanup:
        print(f"⚠️  Removed {before_cleanup - after_cleanup} entries with invalid dates")
    
    # Clean up: Remove duplicate entries (same ticker + date)
    before_dedup = len(history_df)
    history_df = history_df.drop_duplicates(subset=['Date', 'Ticker'], keep='first')
    after_dedup = len(history_df)
    
    if before_dedup > after_dedup:
        print(f"⚠️  Removed {before_dedup - after_dedup} duplicate entries")
        # Save cleaned version
        history_df.to_csv("predictions_history.csv", index=False)
        print("✅ Cleaned predictions_history.csv saved")
    
    # Find predictions from 3 trading days ago (approximately 3-4 calendar days)
    # We'll check predictions from 3-5 days ago to account for weekends
    today = datetime.now().date()
    check_dates = [today - timedelta(days=i) for i in range(3, 6)]
    
    predictions_to_validate = history_df[
        history_df['Date'].dt.date.isin(check_dates)
    ].copy()
    
    if predictions_to_validate.empty:
        print("ℹ️  No predictions from 3-5 days ago to validate yet.")
        print("   Predictions need 3 trading days to mature.")
        
        # Send email even when nothing to validate
        send_email(
            f"No Predictions to Validate - {today}",
            "No predictions from 3-5 days ago found to validate yet.\nPredictions need 3 trading days to mature."
        )
        return
    
    print(f"📊 Validating {len(predictions_to_validate)} predictions from 3-5 days ago\n")
    
    # Validate each prediction
    validations = []
    correct = 0
    incorrect = 0
    skipped = 0
    
    for _, pred in predictions_to_validate.iterrows():
        ticker = pred['Ticker']
        prediction_date = pred['Date'].date()
        predicted_direction = pred['Prediction']
        predicted_score = pred['Score']
        entry_price = pred['Close']
        signal = pred.get('Signal', '-')
        
        try:
            # Get price data from prediction date to today
            start_date = prediction_date
            end_date = today
            
            df = yf.download(ticker, start=start_date, end=end_date, progress=False, auto_adjust=False)
            
            # Check if dataframe is empty or has insufficient data
            if df.empty or len(df) < 2:
                print(f"⚠️  {ticker}: Insufficient data, skipping")
                skipped += 1
                continue
            
            # Get entry and exit prices - handle DataFrame with proper extraction
            close_series = df['Close']
            
            # Extract scalar values properly
            if hasattr(close_series.iloc[0], 'item'):
                actual_entry = close_series.iloc[0].item()
                actual_exit = close_series.iloc[-1].item()
            else:
                actual_entry = float(close_series.iloc[0])
                actual_exit = float(close_series.iloc[-1])
            
            # Calculate actual return
            actual_return = (actual_exit - actual_entry) / actual_entry
            actual_direction = "Up" if actual_exit > actual_entry else "Down"
            
            # Check if prediction was correct
            is_correct = (predicted_direction == actual_direction)
            
            if is_correct:
                correct += 1
                result_symbol = "✅"
            else:
                incorrect += 1
                result_symbol = "❌"
            
            # Calculate days held
            days_held = (df.index[-1] - df.index[0]).days
            
            validation = {
                'Prediction_Date': prediction_date,
                'Validation_Date': today,
                'Ticker': ticker,
                'Predicted': predicted_direction,
                'Actual': actual_direction,
                'Correct': is_correct,
                'Score': predicted_score,
                'Signal': signal,
                'Entry_Price': round(actual_entry, 2),
                'Exit_Price': round(actual_exit, 2),
                'Actual_Return_Pct': round(actual_return * 100, 2),
                'Days_Held': days_held
            }
            
            validations.append(validation)
            
            print(f"{result_symbol} {ticker:6s} | Predicted: {predicted_direction:4s} | "
                  f"Actual: {actual_direction:4s} | Return: {actual_return*100:+6.2f}% | "
                  f"Score: {predicted_score:.2f} | Days: {days_held}")
            
        except Exception as e:
            print(f"⚠️  {ticker}: Error validating - {e}")
            skipped += 1
            continue
    
    if not validations:
        print("\n⚠️  No predictions could be validated.")
        send_email(
            f"Validation Error - {today}",
            "Predictions were found but could not be validated.\nCheck logs for details."
        )
        return
    
    # Save validations
    validation_df = pd.DataFrame(validations)
    
    if os.path.exists(VALIDATION_FILE):
        existing = pd.read_csv(VALIDATION_FILE)
        # Avoid duplicates - only add new validations
        existing_key = existing['Prediction_Date'] + existing['Ticker']
        validation_key = validation_df['Prediction_Date'].astype(str) + validation_df['Ticker']
        validation_df = validation_df[~validation_key.isin(existing_key)]
        
        if not validation_df.empty:
            combined = pd.concat([existing, validation_df], ignore_index=True)
            combined.to_csv(VALIDATION_FILE, index=False)
    else:
        validation_df.to_csv(VALIDATION_FILE, index=False)
    
    # Calculate statistics
    total = correct + incorrect
    accuracy = (correct / total * 100) if total > 0 else 0
    
    print("\n" + "="*60)
    print("VALIDATION SUMMARY")
    print("="*60)
    print(f"Total Validated:     {total}")
    print(f"✅ Correct:          {correct} ({correct/total*100:.1f}%)")
    print(f"❌ Incorrect:        {incorrect} ({incorrect/total*100:.1f}%)")
    print(f"⏭️  Skipped:          {skipped}")
    print(f"\n🎯 ACTUAL ACCURACY:  {accuracy:.2f}%")
    
    # Performance by signal type
    if not validation_df.empty:
        buy_signals = validation_df[validation_df['Signal'] == 'BUY']
        sell_signals = validation_df[validation_df['Signal'] == 'SELL']
        
        if not buy_signals.empty:
            buy_correct = buy_signals['Correct'].sum()
            buy_total = len(buy_signals)
            print(f"\n📈 BUY Signals:      {buy_correct}/{buy_total} correct ({buy_correct/buy_total*100:.1f}%)")
            avg_buy_return = buy_signals['Actual_Return_Pct'].mean()
            print(f"   Avg Return:       {avg_buy_return:+.2f}%")
        
        if not sell_signals.empty:
            sell_correct = sell_signals['Correct'].sum()
            sell_total = len(sell_signals)
            print(f"\n📉 SELL Signals:     {sell_correct}/{sell_total} correct ({sell_correct/sell_total*100:.1f}%)")
            avg_sell_return = sell_signals['Actual_Return_Pct'].mean()
            print(f"   Avg Return:       {avg_sell_return:+.2f}%")
        
        # Performance by confidence score
        high_conf = validation_df[validation_df['Score'] >= 0.70]
        if not high_conf.empty:
            high_conf_correct = high_conf['Correct'].sum()
            high_conf_total = len(high_conf)
            print(f"\n🎯 High Confidence (≥0.70): {high_conf_correct}/{high_conf_total} correct ({high_conf_correct/high_conf_total*100:.1f}%)")
    
    print("="*60 + "\n")
    
    # Generate detailed report
    generate_performance_report()
    
    # ---------------- email report ----------------
    if validations:
        subject = f"Prediction Validation Results - {today}"
        
        body_parts = []
        body_parts.append("="*60)
        body_parts.append("PREDICTION VALIDATION - 3-DAY RESULTS")
        body_parts.append("="*60)
        body_parts.append("")
        body_parts.append(f"📊 Validated {total} predictions from 3-5 days ago")
        body_parts.append("")
        body_parts.append("SUMMARY:")
        body_parts.append(f"  ✅ Correct:   {correct} ({accuracy:.1f}%)")
        body_parts.append(f"  ❌ Incorrect: {incorrect} ({(incorrect/total*100):.1f}%)")
        body_parts.append(f"  🎯 Accuracy:  {accuracy:.2f}%")
        body_parts.append("")
        body_parts.append("DETAILED RESULTS:")
        body_parts.append("-"*60)
        
        for val in validations:
            symbol = "✅" if val['Correct'] else "❌"
            body_parts.append(
                f"{symbol} {val['Ticker']:6s} | Predicted: {val['Predicted']:4s} | "
                f"Actual: {val['Actual']:4s} | Return: {val['Actual_Return_Pct']:+6.2f}% | "
                f"Score: {val['Score']:.2f}"
            )
        
        body_parts.append("")
        
        # Add performance by signal type
        validation_df_temp = pd.DataFrame(validations)
        buy_signals = validation_df_temp[validation_df_temp['Signal'] == 'BUY']
        sell_signals = validation_df_temp[validation_df_temp['Signal'] == 'SELL']
        
        if not buy_signals.empty:
            buy_correct = buy_signals['Correct'].sum()
            buy_total = len(buy_signals)
            avg_buy_return = buy_signals['Actual_Return_Pct'].mean()
            body_parts.append(f"📈 BUY Signals:  {buy_correct}/{buy_total} correct ({buy_correct/buy_total*100:.1f}%), Avg Return: {avg_buy_return:+.2f}%")
        
        if not sell_signals.empty:
            sell_correct = sell_signals['Correct'].sum()
            sell_total = len(sell_signals)
            avg_sell_return = sell_signals['Actual_Return_Pct'].mean()
            body_parts.append(f"📉 SELL Signals: {sell_correct}/{sell_total} correct ({sell_correct/sell_total*100:.1f}%), Avg Return: {avg_sell_return:+.2f}%")
        
        # Add high confidence stats
        high_conf = validation_df_temp[validation_df_temp['Score'] >= 0.70]
        if not high_conf.empty:
            high_conf_correct = high_conf['Correct'].sum()
            high_conf_total = len(high_conf)
            body_parts.append("")
            body_parts.append(f"🎯 High Confidence (≥0.70): {high_conf_correct}/{high_conf_total} correct ({high_conf_correct/high_conf_total*100:.1f}%)")
        
        body_parts.append("")
        body_parts.append("="*60)
        
        body = "\n".join(body_parts)
    else:
        subject = f"No Predictions to Validate - {today}"
        body = "No predictions from 3-5 days ago found to validate yet.\nPredictions need 3 trading days to mature."
    
    send_email(subject, body)

def generate_performance_report():
    """Generate a comprehensive performance report from all validations"""
    
    if not os.path.exists(VALIDATION_FILE):
        return
    
    df = pd.read_csv(VALIDATION_FILE)
    
    if df.empty:
        return
    
    report = []
    report.append("="*60)
    report.append("PREDICTION PERFORMANCE REPORT")
    report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("="*60)
    report.append("")
    
    # Overall statistics
    total = len(df)
    correct = df['Correct'].sum()
    accuracy = correct / total * 100
    
    report.append("OVERALL PERFORMANCE")
    report.append("-"*60)
    report.append(f"Total Predictions Validated:  {total}")
    report.append(f"Correct Predictions:          {correct} ({accuracy:.2f}%)")
    report.append(f"Incorrect Predictions:        {total - correct} ({100-accuracy:.2f}%)")
    report.append("")
    
    # Average returns
    avg_return = df['Actual_Return_Pct'].mean()
    median_return = df['Actual_Return_Pct'].median()
    report.append(f"Average Actual Return:        {avg_return:+.2f}%")
    report.append(f"Median Actual Return:         {median_return:+.2f}%")
    report.append("")
    
    # Performance by signal type
    report.append("PERFORMANCE BY SIGNAL TYPE")
    report.append("-"*60)
    
    for signal_type in ['BUY', 'SELL']:
        signal_df = df[df['Signal'] == signal_type]
        if not signal_df.empty:
            sig_total = len(signal_df)
            sig_correct = signal_df['Correct'].sum()
            sig_accuracy = sig_correct / sig_total * 100
            sig_avg_return = signal_df['Actual_Return_Pct'].mean()
            
            report.append(f"{signal_type} Signals:")
            report.append(f"  Total:      {sig_total}")
            report.append(f"  Accuracy:   {sig_accuracy:.2f}%")
            report.append(f"  Avg Return: {sig_avg_return:+.2f}%")
            report.append("")
    
    # Performance by confidence level
    report.append("PERFORMANCE BY CONFIDENCE LEVEL")
    report.append("-"*60)
    
    confidence_buckets = [
        (0.65, 0.70, "Medium (0.65-0.70)"),
        (0.70, 0.80, "High (0.70-0.80)"),
        (0.80, 1.00, "Very High (0.80+)")
    ]
    
    for min_score, max_score, label in confidence_buckets:
        bucket_df = df[(df['Score'] >= min_score) & (df['Score'] < max_score)]
        if not bucket_df.empty:
            bucket_total = len(bucket_df)
            bucket_correct = bucket_df['Correct'].sum()
            bucket_accuracy = bucket_correct / bucket_total * 100
            
            report.append(f"{label}:")
            report.append(f"  Count:      {bucket_total}")
            report.append(f"  Accuracy:   {bucket_accuracy:.2f}%")
            report.append("")
    
    # Best and worst predictions
    report.append("TOP 5 BEST PREDICTIONS (Highest Returns)")
    report.append("-"*60)
    best = df.nlargest(5, 'Actual_Return_Pct')
    for _, row in best.iterrows():
        status = "✅" if row['Correct'] else "❌"
        report.append(f"{status} {row['Ticker']:6s} | {row['Predicted']:4s} | Return: {row['Actual_Return_Pct']:+6.2f}% | Score: {row['Score']:.2f}")
    report.append("")
    
    report.append("TOP 5 WORST PREDICTIONS (Lowest Returns)")
    report.append("-"*60)
    worst = df.nsmallest(5, 'Actual_Return_Pct')
    for _, row in worst.iterrows():
        status = "✅" if row['Correct'] else "❌"
        report.append(f"{status} {row['Ticker']:6s} | {row['Predicted']:4s} | Return: {row['Actual_Return_Pct']:+6.2f}% | Score: {row['Score']:.2f}")
    report.append("")
    
    report.append("="*60)
    
    # Write report
    with open(REPORT_FILE, 'w') as f:
        f.write('\n'.join(report))
    
    print(f"📄 Detailed report saved to {REPORT_FILE}")

if __name__ == "__main__":
    validate_predictions()
