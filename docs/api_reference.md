# AlgoBot Pro — API Reference

FastAPI backend running on `http://localhost:8000`

Interactive docs available at: `http://localhost:8000/docs`

---

## Base URL

```
http://localhost:8000
```

---

## Endpoints

### `GET /`

Health check. Confirms the API is running.

**Response**
```json
{
  "status":    "running",
  "service":   "AlgoBot Pro",
  "version":   "1.0.0",
  "timestamp": "2024-03-28T14:00:00+00:00",
  "coins":     ["BTC_USD", "ETH_USD", "BNB_USD", "SOL_USD"]
}
```

---

### `GET /signal/{coin}`

Get the latest signal for one coin. Returns cached signal if available,
otherwise generates a fresh one on demand.

**Path parameters**

| Parameter | Type   | Example     | Description         |
|-----------|--------|-------------|---------------------|
| `coin`    | string | `BTC_USD`   | Coin identifier     |

**Valid coins:** `BTC_USD` `ETH_USD` `BNB_USD` `SOL_USD`

**Response (200)**
```json
{
  "coin":             "BTC_USD",
  "signal":           "BUY",
  "confidence":       0.84,
  "price":            66500.0,
  "entry_low":        66168.0,
  "entry_high":       66832.0,
  "target_price":     70490.0,
  "stop_loss_price":  64505.0,
  "risk_reward":      2.0,
  "quantity":         0.075374,
  "position_value":   5000.0,
  "rsi":              32.5,
  "macd_histogram":   0.024,
  "volume_ratio":     1.8,
  "atr":              1200.0,
  "reasons": [
    "RSI at 32.5 — oversold territory, historically a buying opportunity",
    "MACD bullish crossover — momentum turning positive",
    "Price 2.3% below EMA-50 — mean reversion likely"
  ],
  "telegram_message": "...",
  "timestamp":        "2024-03-28T14:00:00+00:00",
  "cached_at":        "2024-03-28T14:00:01+00:00"
}
```

**Response (404)** — Coin not found
```json
{ "detail": "Coin 'INVALID' not found. Available: ['BTC_USD', ...]" }
```

**Response (503)** — Signal generation failed
```json
{ "detail": "Signal generation failed: <error details>" }
```

---

### `GET /signals/all`

Get the latest cached signal for every coin.

**Response (200)**
```json
{
  "signals": {
    "BTC_USD": { ...signal object... },
    "ETH_USD": { ...signal object... },
    "BNB_USD": { ...signal object... },
    "SOL_USD": { ...signal object... }
  },
  "count":     4,
  "timestamp": "2024-03-28T14:00:00+00:00"
}
```

Note: Only coins with cached signals appear in `signals`. If the scheduler
hasn't run yet, `count` will be 0.

---

### `GET /history/{coin}?limit=50`

Get past signals for one coin from the persistent log file.

**Path parameters**

| Parameter | Type   | Example   |
|-----------|--------|-----------|
| `coin`    | string | `ETH_USD` |

**Query parameters**

| Parameter | Type    | Default | Description                      |
|-----------|---------|---------|----------------------------------|
| `limit`   | integer | `50`    | Max signals to return (max 1000) |

**Response (200)**
```json
{
  "coin":    "ETH_USD",
  "count":   48,
  "signals": [ ...array of signal objects, oldest first... ]
}
```

---

### `GET /backtest/{coin}`

Return saved backtest metrics for a coin.
Only available after running `python pipeline.py`.

**Response (200)**
```json
{
  "coin":               "BTC_USD",
  "total_trades":       87,
  "win_rate_pct":       58.6,
  "total_return_pct":   14.2,
  "max_drawdown_pct":   -12.3,
  "sharpe_ratio":       1.24,
  "profit_factor":      1.68,
  "initial_capital":    100000.0,
  "final_capital":      114200.0
}
```

**Response (404)** — No backtest data found
```json
{ "detail": "No backtest found for BTC_USD. Run backtest first." }
```

---

### `GET /status`

System status — shows which models are trained, data freshness,
and last signal for each coin.

**Response (200)**
```json
{
  "system": "AlgoBot Pro",
  "coins": {
    "BTC_USD": {
      "model_trained":   true,
      "data_labeled":    true,
      "last_signal":     "HOLD",
      "last_confidence": 0.519,
      "last_price":      66438.12,
      "cached_at":       "2024-03-28T12:05:16+00:00"
    },
    ...
  }
}
```

---

## Signal Object Reference

Every signal endpoint returns signal objects with this structure:

| Field              | Type    | Description                                     |
|--------------------|---------|-------------------------------------------------|
| `coin`             | string  | e.g. `BTC_USD`                                  |
| `signal`           | string  | `BUY` \| `SELL` \| `HOLD`                       |
| `confidence`       | float   | Model confidence 0.0–1.0                        |
| `price`            | float   | Price at signal generation time                  |
| `entry_low`        | float   | Lower bound of recommended entry zone            |
| `entry_high`       | float   | Upper bound of recommended entry zone            |
| `target_price`     | float   | Price target (+6% for BUY, -6% for SELL)         |
| `stop_loss_price`  | float   | Stop-loss price (-3% for BUY, +3% for SELL)      |
| `risk_reward`      | float   | Risk/reward ratio (e.g. 2.0 means 1:2)          |
| `quantity`         | float   | Units to buy/sell                                |
| `position_value`   | float   | Rs value of position                             |
| `rsi`              | float   | RSI value at signal time                         |
| `macd_histogram`   | float   | MACD histogram value                             |
| `volume_ratio`     | float   | Volume / 20-period average volume               |
| `atr`              | float   | Average True Range                               |
| `reasons`          | array   | Plain-English reasons for the signal             |
| `telegram_message` | string  | Pre-formatted Telegram message                   |
| `timestamp`        | string  | ISO 8601 datetime of signal generation           |
| `cached_at`        | string  | ISO 8601 datetime of cache update                |

---

## Label Encoding

The model predicts three classes:

| Integer | Label | Meaning                               |
|---------|-------|---------------------------------------|
| `0`     | BUY   | Price expected to rise > 2% in 24h   |
| `1`     | SELL  | Price expected to fall > 2% in 24h   |
| `2`     | HOLD  | Price expected to stay within ±2%     |

---

## Error Responses

All errors follow FastAPI's standard format:

```json
{
  "detail": "Human-readable error message"
}
```

| HTTP Code | Meaning                                      |
|-----------|----------------------------------------------|
| `200`     | Success                                      |
| `404`     | Coin not found or no backtest data           |
| `503`     | Signal generation failed (model or data error)|
| `422`     | Validation error (invalid query parameters)  |

---

## Rate Limiting

No rate limiting in development mode.
In production, add rate limiting via Redis (see `database/redis_config.py`).

---

## Authentication

No authentication in development mode.
Add API key authentication before exposing to the internet.

---

*Last updated: March 2026 | AlgoBot Pro v1.0.0*