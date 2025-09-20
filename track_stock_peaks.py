# track_stock_peaks.py

import pandas as pd

# Dictionary to store current peaks for each ticker
# Example: {'BABA': 105.3, 'WDAY': 250.0}
ticker_peaks = {}

def update_peak(df, ticker, new_close):
    """
    Update the peak closing price for a ticker.
    
    Parameters:
        df (DataFrame): Optional, can be used to store historical peaks
        ticker (str): Stock symbol
        new_close (float): Latest closing price
    """
    global ticker_peaks
    if ticker not in ticker_peaks or new_close > ticker_peaks[ticker]:
        ticker_peaks[ticker] = new_close
        # Optionally log or save to df if you want historical peaks
        if df is not None:
            df.loc[len(df)] = {"Ticker": ticker, "PeakClose": new_close, "Datetime": pd.Timestamp.now()}
    return ticker_peaks[ticker]

def remove_peak(df, ticker):
    """
    Remove a peak record for a ticker.
    
    Parameters:
        df (DataFrame): Optional DataFrame storing historical peaks
        ticker (str): Stock symbol
    """
    global ticker_peaks
    if ticker in ticker_peaks:
        del ticker_peaks[ticker]
    if df is not None:
        df.drop(df[df["Ticker"] == ticker].index, inplace=True)

