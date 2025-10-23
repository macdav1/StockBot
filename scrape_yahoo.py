import requests
from bs4 import BeautifulSoup
import time

def scrape_yahoo_tickers(url, max_tickers=50):
    """
    Scrape ticker symbols from Yahoo Finance page
    
    Args:
        url: Yahoo Finance URL to scrape
        max_tickers: Maximum number of tickers to retrieve
    
    Returns:
        List of ticker symbols
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        tickers = []
        
        # Find all table rows with ticker data
        # Yahoo Finance uses data-symbol attribute for tickers
        for row in soup.find_all('a', {'data-symbol': True}):
            ticker = row['data-symbol']
            if ticker and ticker not in tickers:
                tickers.append(ticker)
                if len(tickers) >= max_tickers:
                    break
        
        # Fallback: look for ticker symbols in table cells
        if not tickers:
            for row in soup.find_all('tr'):
                cells = row.find_all('td')
                if cells:
                    # First cell usually contains ticker
                    ticker_cell = cells[0].find('a')
                    if ticker_cell:
                        ticker = ticker_cell.get_text(strip=True)
                        if ticker and ticker not in tickers:
                            tickers.append(ticker)
                            if len(tickers) >= max_tickers:
                                break
        
        return tickers
    
    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return []

def main():
    """Main function to scrape gainers and actives, save to file"""
    
    # URLs for Yahoo Finance screeners
    gainers_url = "https://finance.yahoo.com/markets/stocks/gainers/"
    actives_url = "https://finance.yahoo.com/markets/stocks/most-active/"
    
    print("Scraping Yahoo Finance gainers...")
    gainers = scrape_yahoo_tickers(gainers_url, max_tickers=50)
    print(f"Found {len(gainers)} gainers")
    
    # Small delay to be respectful to the server
    time.sleep(2)
    
    print("Scraping Yahoo Finance most actives...")
    actives = scrape_yahoo_tickers(actives_url, max_tickers=50)
    print(f"Found {len(actives)} actives")
    
    # Combine and deduplicate
    all_tickers = []
    seen = set()
    
    # Add gainers first
    for ticker in gainers:
        if ticker not in seen:
            all_tickers.append(ticker)
            seen.add(ticker)
    
    # Add actives
    for ticker in actives:
        if ticker not in seen:
            all_tickers.append(ticker)
            seen.add(ticker)
    
    print(f"\nTotal unique tickers: {len(all_tickers)}")
    
    # Write to file
    output_file = "yahoo_top.txt"
    with open(output_file, 'w') as f:
        for ticker in all_tickers:
            f.write(f"{ticker}\n")
    
    print(f"Tickers saved to {output_file}")
    
    # Display first 10 tickers as preview
    print(f"\nFirst 10 tickers: {', '.join(all_tickers[:10])}")

if __name__ == "__main__":
    main()
