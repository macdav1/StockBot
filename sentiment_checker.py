# sentiment_checker.py

import requests
from bs4 import BeautifulSoup
from nltk.sentiment.vader import SentimentIntensityAnalyzer
import nltk
from email_notifier import send_email

# Make sure VADER lexicon is available
nltk.download('vader_lexicon', quiet=True)

sia = SentimentIntensityAnalyzer()


# -----------------------------
# Yahoo Finance
# -----------------------------
def get_yahoo_finance_news(ticker, limit=15):
    url = f"https://finance.yahoo.com/quote/{ticker}?p={ticker}"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    headlines = []
    for h in soup.find_all("h3", limit=limit):
        text = h.get_text(strip=True)
        if text:
            headlines.append(text)
    return headlines


# -----------------------------
# Finviz
# -----------------------------
def get_finviz_news(ticker, limit=15):
    url = f"https://finviz.com/quote.ashx?t={ticker}"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    news_table = soup.find(id="news-table")
    if not news_table:
        return []

    rows = news_table.find_all("tr", limit=limit)
    headlines = [row.a.get_text(strip=True) for row in rows if row.a]
    return headlines


# -----------------------------
# Reddit
# -----------------------------
def get_reddit_posts(ticker, limit=20):
    url = f"https://www.reddit.com/search/?q={ticker}&sort=new"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    posts = []
    for post in soup.find_all("h3", limit=limit):
        text = post.get_text(strip=True)
        if text:
            posts.append(text)
    return posts

def describe_sentiment(score):
    if score >= 0.3:
        return "🟢 Strongly Bullish"
    elif score >= 0.1:
        return "🟩 Moderately Bullish"
    elif score <= -0.3:
        return "🔴 Strongly Bearish"
    elif score <= -0.1:
        return "🟠 Moderately Bearish"
    else:
        return "⚪ Neutral / Unclear"

# -----------------------------
# Sentiment Scoring
# -----------------------------
def get_sentiment_from_texts(texts):
    if not texts:
        return 0.0
    scores = [sia.polarity_scores(t)["compound"] for t in texts]
    return round(sum(scores) / len(scores), 3) if scores else 0.0


def sentiment_score(ticker):
    yahoo = get_yahoo_finance_news(ticker)
    finviz = get_finviz_news(ticker)
    reddit = get_reddit_posts(ticker)

    yahoo_score = get_sentiment_from_texts(yahoo)
    finviz_score = get_sentiment_from_texts(finviz)
    reddit_score = get_sentiment_from_texts(reddit)

    final_score = round(
        (yahoo_score * 0.4 + finviz_score * 0.4 + reddit_score * 0.2), 3
    )

    return {
        "ticker": ticker,
        "final": final_score,
        "yahoo": yahoo_score,
        "finviz": finviz_score,
        "reddit": reddit_score,
    }


# -----------------------------
# Batch Scan + Email
# -----------------------------
def scan_top_stocks_and_email():
    import pandas as pd
    import os

    predictions_path = "predictions.csv"

    if not os.path.exists(predictions_path):
        send_email("Sentiment Check Failed", "⚠️ No predictions.csv file found.")
        return

    df = pd.read_csv(predictions_path)
    if "Ticker" not in df.columns or df.empty:
        send_email("Sentiment Check Failed", "⚠️ No tickers found in predictions.csv.")
        return

    tickers = df["Ticker"].dropna().astype(str).unique().tolist()
    if not tickers:
        send_email("Sentiment Check Failed", "⚠️ predictions.csv contained no valid tickers.")
        return

    results = []
    for ticker in tickers:
        try:
            scores = sentiment_score(ticker)
            results.append(scores)
        except Exception as e:
            print(f"⚠️ Error checking {ticker}: {e}")

    if not results:
        send_email("Sentiment Check", "⚠️ No sentiment results could be generated.")
        return

    # Rank by final sentiment score
    results.sort(key=lambda x: x["final"], reverse=True)
    top10 = results[:10]

    # Build email
    email_text = "📊 Top 10 Sentiment Rankings (Predicted Stocks)\n\n"
    for r in top10:
        label = describe_sentiment(r['final'])
        email_text += (
            f"{r['ticker']}: {r['final']} {label}\n"
            f"   Yahoo={r['yahoo']}, Finviz={r['finviz']}, Reddit={r['reddit']}\n\n"
        )

    send_email("Top 10 Bullish Predictions by Sentiment", email_text)


if __name__ == "__main__":
    scan_top_stocks_and_email()
    print("✅ Sentiment scan complete, email sent")

