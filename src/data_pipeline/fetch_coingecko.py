"""
src/data_pipeline/fetch_coingecko.py
======================================
PURPOSE:
    Fetch supplementary market data from CoinGecko API.
    Used for price validation, market cap data, and 24h stats.

    CoinGecko provides data that Yahoo Finance doesn't:
    - Market capitalisation
    - 24h trading volume (exchange-wide, not just one pair)
    - Price change percentages
    - Market dominance

WHY COINGECKO IN ADDITION TO YAHOO FINANCE?
    Yahoo Finance gives us OHLCV candles (for indicators).
    CoinGecko gives us market-wide stats (for context and validation).
    Together they give the signal a richer picture.

FREE TIER:
    CoinGecko's public API is completely free with no API key needed.
    Rate limit: ~10-30 requests/minute (we stay well below this).

DEPENDENCIES:
    pip install requests pandas
"""

import time
import logging
import requests
import pandas as pd
from datetime import datetime, timezone

from config.settings import COINS, COINGECKO_IDS

log = logging.getLogger(__name__)

COINGECKO_BASE = "https://api.coingecko.com/api/v3"
REQUEST_TIMEOUT = 15
RATE_LIMIT_SLEEP = 1.5   # seconds between requests to avoid rate limit


def _get(endpoint: str, params: dict = None) -> dict:
    """
    Make a GET request to CoinGecko API.

    Args:
        endpoint: API endpoint e.g. '/simple/price'
        params:   Query parameters dict

    Returns:
        dict: JSON response, or empty dict on failure
    """
    url = f"{COINGECKO_BASE}{endpoint}"
    try:
        resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RateLimitError:
        log.warning("CoinGecko rate limit hit — waiting 60 seconds ...")
        time.sleep(60)
        return {}
    except requests.exceptions.RequestException as e:
        log.error(f"CoinGecko request failed: {e}")
        return {}


def get_current_prices(coin_names: list = None) -> dict:
    """
    Get current prices for multiple coins in one API call.

    Args:
        coin_names: List of coin names e.g. ['BTC_USD', 'ETH_USD']
                    Defaults to all coins in settings.

    Returns:
        dict: {
            'BTC_USD': {
                'price_usd':    66500.0,
                'change_24h':   2.3,      # % change in last 24h
                'volume_24h':   28_000_000_000.0,
                'market_cap':   1_300_000_000_000.0,
                'fetched_at':   '2024-03-28T10:00:00+00:00'
            },
            ...
        }

    Example:
        >>> from src.data_pipeline.fetch_coingecko import get_current_prices
        >>> prices = get_current_prices(['BTC_USD', 'ETH_USD'])
        >>> print(prices['BTC_USD']['price_usd'])
    """
    if coin_names is None:
        coin_names = list(COINS.values())

    # Build CoinGecko IDs list
    cg_ids = []
    id_to_coin = {}
    for coin in coin_names:
        cg_id = COINGECKO_IDS.get(coin)
        if cg_id:
            cg_ids.append(cg_id)
            id_to_coin[cg_id] = coin

    if not cg_ids:
        log.warning("No valid CoinGecko IDs found")
        return {}

    data = _get("/simple/price", params={
        "ids":                  ",".join(cg_ids),
        "vs_currencies":        "usd",
        "include_24hr_change":  "true",
        "include_24hr_vol":     "true",
        "include_market_cap":   "true",
        "include_last_updated_at": "true",
    })

    if not data:
        return {}

    now     = datetime.now(timezone.utc).isoformat()
    results = {}

    for cg_id, values in data.items():
        coin_name = id_to_coin.get(cg_id)
        if not coin_name:
            continue

        results[coin_name] = {
            "price_usd":  values.get("usd", 0.0),
            "change_24h": values.get("usd_24h_change", 0.0),
            "volume_24h": values.get("usd_24h_vol", 0.0),
            "market_cap": values.get("usd_market_cap", 0.0),
            "fetched_at": now,
        }

        log.info(
            f"  {coin_name}: ${results[coin_name]['price_usd']:,.2f} "
            f"({results[coin_name]['change_24h']:+.2f}% 24h)"
        )

    return results


def get_market_summary() -> dict:
    """
    Get overall crypto market statistics.
    Used to add market context to signals (bull/bear market conditions).

    Returns:
        dict: {
            'total_market_cap_usd':    2_500_000_000_000,
            'btc_dominance_pct':       52.3,
            'eth_dominance_pct':       17.1,
            'market_cap_change_24h':   1.8,    # % change
            'active_cryptocurrencies': 15000,
            'fetched_at':              '...'
        }

    Example:
        >>> from src.data_pipeline.fetch_coingecko import get_market_summary
        >>> summary = get_market_summary()
        >>> print(f"BTC dominance: {summary['btc_dominance_pct']:.1f}%")
    """
    data = _get("/global")

    if not data or "data" not in data:
        log.warning("Failed to fetch global market data from CoinGecko")
        return {}

    d   = data["data"]
    now = datetime.now(timezone.utc).isoformat()

    summary = {
        "total_market_cap_usd":    d.get("total_market_cap", {}).get("usd", 0),
        "total_volume_24h_usd":    d.get("total_volume", {}).get("usd", 0),
        "btc_dominance_pct":       d.get("market_cap_percentage", {}).get("btc", 0),
        "eth_dominance_pct":       d.get("market_cap_percentage", {}).get("eth", 0),
        "market_cap_change_24h":   d.get("market_cap_change_percentage_24h_usd", 0),
        "active_cryptocurrencies": d.get("active_cryptocurrencies", 0),
        "fetched_at":              now,
    }

    log.info(
        f"  Market cap: ${summary['total_market_cap_usd']/1e12:.2f}T | "
        f"BTC dominance: {summary['btc_dominance_pct']:.1f}%"
    )

    return summary


def validate_price_against_yahoo(
    coin_name: str,
    yahoo_price: float,
    tolerance_pct: float = 1.0,
) -> bool:
    """
    Cross-check a Yahoo Finance price against CoinGecko.
    Alerts if prices diverge by more than tolerance_pct.

    Used as a data quality check before generating signals.

    Args:
        coin_name:     e.g. 'BTC_USD'
        yahoo_price:   Price from Yahoo Finance
        tolerance_pct: Max allowed % difference (default 1.0%)

    Returns:
        bool: True if prices match within tolerance, False if suspicious

    Example:
        >>> from src.data_pipeline.fetch_coingecko import validate_price_against_yahoo
        >>> ok = validate_price_against_yahoo('BTC_USD', 66500.0)
        >>> print("Price OK" if ok else "Price mismatch — check data!")
    """
    time.sleep(RATE_LIMIT_SLEEP)   # Be polite to the API
    prices = get_current_prices([coin_name])

    if not prices or coin_name not in prices:
        log.warning(f"  Could not validate {coin_name} price — CoinGecko unavailable")
        return True   # Don't block signal on API failure

    cg_price = prices[coin_name]["price_usd"]

    if cg_price <= 0:
        return True

    diff_pct = abs(yahoo_price - cg_price) / cg_price * 100

    if diff_pct > tolerance_pct:
        log.warning(
            f"  PRICE MISMATCH for {coin_name}: "
            f"Yahoo={yahoo_price:,.2f}  CoinGecko={cg_price:,.2f}  "
            f"Diff={diff_pct:.2f}% (>{tolerance_pct}%)"
        )
        return False

    log.info(
        f"  Price validation OK: {coin_name} "
        f"Yahoo={yahoo_price:,.2f} vs CG={cg_price:,.2f} "
        f"(diff={diff_pct:.3f}%)"
    )
    return True


def get_fear_greed_index() -> dict:
    """
    Fetch the Crypto Fear & Greed Index from alternative.me API.

    The Fear & Greed Index (0-100) measures overall market sentiment:
        0-24  = Extreme Fear  (historically good buying opportunity)
        25-44 = Fear
        45-55 = Neutral
        56-74 = Greed
        75-100 = Extreme Greed (historically good selling opportunity)

    Returns:
        dict: {
            'value':       72,
            'label':       'Greed',
            'fetched_at':  '...'
        }

    Example:
        >>> from src.data_pipeline.fetch_coingecko import get_fear_greed_index
        >>> fgi = get_fear_greed_index()
        >>> print(f"Fear & Greed: {fgi['value']} ({fgi['label']})")
    """
    try:
        resp = requests.get(
            "https://api.alternative.me/fng/",
            params={"limit": 1},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()

        if "data" in data and data["data"]:
            entry = data["data"][0]
            return {
                "value":      int(entry.get("value", 50)),
                "label":      entry.get("value_classification", "Neutral"),
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
    except Exception as e:
        log.warning(f"Fear & Greed Index fetch failed: {e}")

    # Return neutral default on failure
    return {
        "value":      50,
        "label":      "Neutral",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)s  %(message)s"
    )

    print("── Current Prices ──────────────────────────────────")
    prices = get_current_prices()
    for coin, data in prices.items():
        print(f"  {coin}: ${data['price_usd']:,.2f}  ({data['change_24h']:+.2f}% 24h)")

    print("\n── Market Summary ──────────────────────────────────")
    summary = get_market_summary()
    print(f"  Market cap:    ${summary.get('total_market_cap_usd',0)/1e12:.2f}T")
    print(f"  BTC dominance: {summary.get('btc_dominance_pct',0):.1f}%")

    print("\n── Fear & Greed Index ──────────────────────────────")
    fgi = get_fear_greed_index()
    print(f"  Score: {fgi['value']} — {fgi['label']}")