# ... (same imports & setup as before)

def execute_sells():
    trades_executed = []
    try:
        df = pd.read_csv("predictions.csv")
        df = df[df['Signal'].str.strip().str.lower() == 'sell']
        logger.info(f"Loaded {len(df)} sell signals.")

        for _, row in df.iterrows():
            ticker = row['Ticker'].strip().upper()
            score = float(row.get("Score", 0))
            
            # --- same filter logic (moving avg, volume, etc.) ---
            # --- same sell logic (trailing stop, profit exit, etc.) ---

            # Submit sell
            api.submit_order(
                symbol=ticker,
                qty=sell_qty,
                side='sell',
                type='market',
                time_in_force='day'
            )
            logger.info(f"SELL {sell_qty} shares of {ticker} at ${latest_price:.2f}")
            trades_executed.append(f"SELL {sell_qty} {ticker}")
            remove_peak(ticker)
            log_trade(ticker, "SELL", sell_qty, latest_price, score)

    except Exception as e:
        logger.error(f"Unexpected error in sell_executor: {e}")

    # ✅ portfolio update still here
    try:
        positions = api.list_positions()
        portfolio_data = []
        for p in positions:
            current_price = float(p.current_price)
            avg_price = float(p.avg_entry_price)
            shares = float(p.qty)
            pl = (current_price - avg_price) * shares
            portfolio_data.append({
                "Ticker": p.symbol,
                "Shares": shares,
                "Average Cost": avg_price,
                "Current Price": current_price,
                "P/L($)": round(pl, 2)
            })

        df_portfolio = pd.DataFrame(portfolio_data)
        df_portfolio.to_csv("portfolio.csv", index=False)
        print("💾 portfolio.csv updated with current positions.")

    except Exception as e:
        logger.error(f"❌ Failed to update portfolio.csv: {e}")
        print(f"⚠️ Error while updating portfolio.csv: {e}")

    # ✅ email report
    if trades_executed:
        subject = f"Sell Trades Executed - {datetime.today().date()}"
        body = "\n".join(trades_executed)
    else:
        subject = f"No Sell Trades Executed - {datetime.today().date()}"
        body = "No sell trades were made today."

    send_email(subject, body)

