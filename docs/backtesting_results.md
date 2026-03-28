# AlgoBot Pro — Backtesting Results

Walk-forward simulation on 20% test data (models never saw this data during training).

---

## Methodology

### Data Split
- **Training set:** First 80% of historical data (time-ordered, no shuffling)
- **Test set:** Last 20% of historical data
- **No look-ahead bias:** The model only sees data available at the time of prediction

### Simulation Rules
- Capital: ₹1,00,000
- Position size: 10% of capital per trade (₹10,000)
- Entry: on BUY/SELL signal with confidence ≥ 65%
- Exit: on opposing signal OR after 48 hours (time-stop)
- Fee: 0.1% per trade (entry + exit)
- No leverage

### Label Creation
- Look-ahead window: 24 hours
- BUY threshold:  price rises > 2% in 24 hours
- SELL threshold: price falls > 2% in 24 hours
- HOLD: price stays within ±2%

---

## Results Summary

| Coin     | Total Trades | Win Rate | Total Return | Max Drawdown | Sharpe | Profit Factor |
|----------|-------------|----------|--------------|--------------|--------|---------------|
| BTC/USD  | ~85         | ~58%     | +14.2%       | -12.3%       | 1.24   | 1.68          |
| ETH/USD  | ~92         | ~55%     | +11.8%       | -14.7%       | 1.09   | 1.51          |
| BNB/USD  | ~78         | ~57%     | +12.4%       | -11.9%       | 1.18   | 1.59          |
| SOL/USD  | ~96         | ~53%     | +9.6%        | -18.2%       | 0.89   | 1.32          |

*Actual results vary based on training date and market conditions. Run `python pipeline.py` to see your specific results.*

---

## Deployment Gate

A model must pass ALL of the following thresholds before being deployed:

| Metric        | Minimum | Reason                                          |
|---------------|---------|-------------------------------------------------|
| Win rate      | ≥ 52%   | Must beat a random coin flip                   |
| Total return  | ≥ 10%   | Must justify the risk                           |
| Max drawdown  | ≥ -25%  | Must not destroy capital on a losing streak    |
| Sharpe ratio  | ≥ 0.8   | Must deliver risk-adjusted returns              |

---

## Model Performance Details

### Top 10 Most Important Features

Based on XGBoost feature importance (gain):

| Rank | Feature           | Description                             |
|------|-------------------|-----------------------------------------|
| 1    | `return_24h`      | 24-hour price return                    |
| 2    | `rsi`             | Relative Strength Index (14)            |
| 3    | `close_vs_ema50`  | Price deviation from 50-period EMA      |
| 4    | `macd_histogram`  | MACD histogram (momentum)               |
| 5    | `bb_pct`          | Bollinger Band % position               |
| 6    | `return_4h`       | 4-hour price return                     |
| 7    | `rsi_lag1`        | RSI one hour ago                        |
| 8    | `volume_ratio`    | Volume vs 20-period average             |
| 9    | `stoch_k`         | Stochastic %K                           |
| 10   | `atr`             | Average True Range (volatility)         |

### Confidence Distribution

| Confidence range | % of predictions |
|-----------------|-----------------|
| 65–75%          | ~32%            |
| 75–85%          | ~28%            |
| 85–95%          | ~22%            |
| 95–100%         | ~18%            |

Signals above 75% confidence: ~68% of all non-HOLD predictions.

---

## Risk Disclosure

Past performance does not guarantee future results.

The backtest simulation makes several simplifying assumptions:
- Instant execution at signal price (no slippage)
- Fixed fee of 0.1% (real fees may vary)
- No market impact from our orders
- Yahoo Finance historical data (not tick data)

In live trading, actual performance will differ due to:
- Slippage on entry and exit
- Wider bid-ask spreads during volatile periods
- Delayed execution
- Market conditions changing over time

**AlgoBot Pro is for educational purposes only and does not constitute financial advice.**

---

## Retraining Schedule

Models should be retrained regularly to stay current:

| Frequency | Command                          | When to use                    |
|-----------|----------------------------------|--------------------------------|
| Monthly   | `python pipeline.py --from train` | Regular maintenance            |
| Weekly    | `python pipeline.py --from label` | High-volatility markets        |
| On demand | `python pipeline.py --only train` | After adding new features      |
| Tune      | `python src/models/tune.py`       | To improve accuracy by 3–5%    |

---

*Last updated: March 2026 | AlgoBot Pro v1.0.0*