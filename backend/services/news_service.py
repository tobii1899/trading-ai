"""
News & Sentiment Service
- Fetches recent financial news via NewsAPI (free tier) or RSS fallback
- Detects high-impact events: FOMC, NFP, CPI, political speeches, etc.
- Returns sentiment score and impact warnings for the UI
"""

import os
import re
import logging
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional
import httpx
import feedparser

logger = logging.getLogger(__name__)

NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")  # Optional: get free key at newsapi.org

# Keywords that indicate HIGH-IMPACT market events
HIGH_IMPACT_KEYWORDS = [
    # Central banks
    "fomc", "federal reserve", "fed rate", "powell", "rate decision",
    "ecb", "bank of england", "boe", "boj", "bank of japan",
    # Economic data
    "nfp", "non-farm payroll", "payroll", "cpi", "inflation",
    "gdp", "unemployment", "jobs report", "retail sales",
    # Political / macro
    "war", "sanctions", "tariff", "trade war", "geopolit",
    "election", "referendum", "default", "debt ceiling",
    # Market stress
    "crash", "circuit breaker", "black swan", "emergency",
    "bank failure", "bank run", "bankruptcy",
]

# Keywords for sentiment scoring
BULLISH_KEYWORDS = [
    "surges", "rally", "bull", "breakout", "record high", "gains", "rises",
    "strong growth", "better than expected", "beats estimates", "optimism",
    "recovery", "upbeat", "hawkish", "rate hike pause",
]

BEARISH_KEYWORDS = [
    "plunges", "crash", "bear", "breakdown", "record low", "losses", "falls",
    "weak", "worse than expected", "misses", "recession", "fear", "panic",
    "downturn", "rate hike", "tightening", "stagflation",
]

# Free RSS feeds for financial news
RSS_FEEDS = [
    "https://feeds.content.dowjones.io/public/rss/mw_topstories",  # MarketWatch
    "https://finance.yahoo.com/news/rssindex",                      # Yahoo Finance
    "https://www.investing.com/rss/news.rss",                       # Investing.com
]


def _score_sentiment(text: str) -> float:
    """
    Simple keyword-based sentiment score.
    Returns: float in [-1.0, +1.0], positive = bullish.
    """
    text_lower = text.lower()
    bull_count = sum(1 for kw in BULLISH_KEYWORDS if kw in text_lower)
    bear_count = sum(1 for kw in BEARISH_KEYWORDS if kw in text_lower)

    total = bull_count + bear_count
    if total == 0:
        return 0.0

    return round((bull_count - bear_count) / total, 3)


def _is_high_impact(text: str) -> bool:
    """Check if text contains high-impact event keywords."""
    text_lower = text.lower()
    return any(kw in text_lower for kw in HIGH_IMPACT_KEYWORDS)


def _is_asset_relevant(text: str, asset: str) -> bool:
    """Check if news article is relevant to the given asset."""
    relevance_map = {
        "XAU/USD": ["gold", "xau", "precious metal", "safe haven", "inflation", "fed", "dollar"],
        "GBP/JPY": ["gbp", "sterling", "pound", "jpy", "yen", "japan", "uk", "brexit", "boe", "boj"],
        "NASDAQ100": ["nasdaq", "tech", "s&p", "equity", "stocks", "fed", "rate", "qqq", "tech stocks"],
    }
    keywords = relevance_map.get(asset, [])
    text_lower = text.lower()
    return any(kw in text_lower for kw in keywords) or True  # fallback: always include general market news


async def fetch_news_rss(max_articles: int = 20) -> list[dict]:
    """Fetch news from RSS feeds (no API key required)."""
    articles = []
    seen_hashes = set()

    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:max_articles]:
                title = getattr(entry, "title", "")
                summary = getattr(entry, "summary", "")
                published = getattr(entry, "published", "")
                link = getattr(entry, "link", "")

                full_text = f"{title} {summary}"
                # Deduplicate by content hash
                content_hash = hashlib.md5(title.encode()).hexdigest()
                if content_hash in seen_hashes:
                    continue
                seen_hashes.add(content_hash)

                articles.append({
                    "title": title,
                    "summary": summary[:300],
                    "url": link,
                    "published": published,
                    "source": feed.feed.get("title", feed_url),
                    "sentiment": _score_sentiment(full_text),
                    "high_impact": _is_high_impact(full_text),
                })
        except Exception as e:
            logger.warning(f"RSS feed error ({feed_url}): {e}")

    return articles


async def fetch_news_newsapi(asset: str, max_articles: int = 10) -> list[dict]:
    """
    Fetch news from NewsAPI.org (requires free API key).
    Searches for asset-specific terms.
    """
    if not NEWS_API_KEY:
        return []

    query_map = {
        "XAU/USD": "gold OR XAU OR precious metals",
        "GBP/JPY": "pound OR sterling OR yen OR GBPJPY",
        "NASDAQ100": "NASDAQ OR tech stocks OR QQQ",
    }
    query = query_map.get(asset, "forex OR stocks OR market")

    url = "https://newsapi.org/v2/everything"
    params = {
        "q": query,
        "sortBy": "publishedAt",
        "pageSize": max_articles,
        "language": "en",
        "from": (datetime.utcnow() - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%S"),
        "apiKey": NEWS_API_KEY,
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.warning(f"NewsAPI error: {e}")
        return []

    articles = []
    for item in data.get("articles", []):
        title = item.get("title", "")
        description = item.get("description", "")
        full_text = f"{title} {description}"

        articles.append({
            "title": title,
            "summary": description[:300] if description else "",
            "url": item.get("url", ""),
            "published": item.get("publishedAt", ""),
            "source": item.get("source", {}).get("name", ""),
            "sentiment": _score_sentiment(full_text),
            "high_impact": _is_high_impact(full_text),
        })

    return articles


async def get_market_sentiment(asset: str) -> dict:
    """
    Get aggregated news sentiment and risk warnings for an asset.
    
    Returns:
        dict with: overall_sentiment, high_impact_detected, warning_message,
                   article_count, recent_articles
    """
    # Try NewsAPI first (richer), fall back to RSS
    articles = await fetch_news_newsapi(asset, max_articles=10)
    if not articles:
        articles = await fetch_news_rss(max_articles=30)
        # Filter to relevant articles
        articles = [a for a in articles if _is_asset_relevant(
            f"{a['title']} {a['summary']}", asset
        )][:10]

    if not articles:
        return {
            "overall_sentiment": 0.0,
            "high_impact_detected": False,
            "warning_message": None,
            "article_count": 0,
            "recent_articles": [],
        }

    sentiments = [a["sentiment"] for a in articles]
    overall_sentiment = round(sum(sentiments) / len(sentiments), 3) if sentiments else 0.0
    high_impact = any(a["high_impact"] for a in articles)

    # Build specific warning message based on detected events
    warning_parts = []
    all_text = " ".join(f"{a['title']} {a['summary']}" for a in articles).lower()

    if "fomc" in all_text or "federal reserve" in all_text or "powell" in all_text:
        warning_parts.append("FOMC/Fed event detected")
    if "nfp" in all_text or "non-farm payroll" in all_text or "payroll" in all_text:
        warning_parts.append("NFP release")
    if "cpi" in all_text or "inflation" in all_text:
        warning_parts.append("CPI/Inflation data")
    if "war" in all_text or "conflict" in all_text or "sanctions" in all_text:
        warning_parts.append("Geopolitical tension")
    if "rate decision" in all_text or "interest rate" in all_text:
        warning_parts.append("Rate decision")

    warning_message = None
    if high_impact:
        if warning_parts:
            warning_message = f"⚠️ High-impact event: {', '.join(warning_parts)} – trade risk significantly elevated"
        else:
            warning_message = "⚠️ High-impact market news detected – trade risk elevated"

    return {
        "overall_sentiment": overall_sentiment,
        "high_impact_detected": high_impact,
        "warning_message": warning_message,
        "article_count": len(articles),
        "recent_articles": articles[:5],  # Return top 5 for UI
    }
