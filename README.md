---

---

# AlgoBot Pro — Complete Project Explanation

---

## 1. Why Was This Project Made?

Imagine you want to invest in Bitcoin or Ethereum. Every day you open your phone and wonder:

> *"Should I buy now? Should I sell? Should I wait?"*

Most people guess. They get excited when prices go up and panic when prices go down. They make emotional decisions and often lose money.

**Professional traders don't guess.** They use technical analysis — they study price patterns, momentum, volume, and dozens of other signals to make calculated decisions. But this requires:
- Watching charts 24 hours a day
- Understanding 37+ technical indicators
- Years of experience reading market patterns

**AlgoBot Pro solves this problem.**

It acts like a professional trader that never sleeps — watching Bitcoin, Ethereum, BNB and Solana every single hour, analysing 37 technical signals automatically, and then sending you a simple message on Telegram saying **"BUY", "SELL" or "HOLD"** with the exact entry price, target price and stop-loss.

---

## 2. What Data Is Used and Where Does It Come From?

There are two types of data in this project:

---

### Part A — Historical Training Data (Used to teach the AI)

**Source:** HuggingFace (a free AI data platform) + Yahoo Finance

**What it is:** 2+ years of hourly price data for BTC, ETH, BNB and SOL. Every single hour for 2 years — that's around **17,000 data points per coin**.

Each data point contains:
```
Date/Time  |  Open Price  |  High Price  |  Low Price  |  Close Price  |  Volume
2024-01-01 |  ₹35,00,000  |  ₹35,20,000  |  ₹34,80,000 |  ₹35,10,000  |  500 BTC
2024-01-01 |  ₹35,10,000  |  ₹35,50,000  |  ₹35,00,000 |  ₹35,30,000  |  620 BTC
... (17,000 more rows)
```

**This data is NOT live** — it is historical, downloaded once and used to train the AI model. Think of it like giving a medical student 10 years of patient records to study from before letting them treat real patients.

---

### Part B — Live Data (Used every hour for real signals)

**Source:** Yahoo Finance API (free, real-time)

**What it is:** Every hour, the bot automatically fetches the **last 200 hourly candles** — essentially the last 8 days of price movement — fresh from Yahoo Finance.

**This IS live data** — it reflects actual current market prices.

```
Current time: 5:00 PM
Bot fetches: BTC price history from last 200 hours
Latest candle: BTC @ ₹66,500 at 5:00 PM today  ← LIVE
```

---

### What Happens to This Data?

Once we have the price data (historical or live), we calculate **37 technical indicators** from it:

| Indicator | What It Measures |
|---|---|
| RSI | Is the coin overbought or oversold? |
| MACD | Is momentum increasing or decreasing? |
| Bollinger Bands | Is price unusually high or low compared to recent history? |
| EMA 9/21/50 | Short, medium and long term price trends |
| ATR | How volatile is the market right now? |
| Stochastic | Is the coin near recent highs or lows? |
| OBV | Is volume confirming the price move? |
| + 30 more | Time of day, lag features, return features... |

---

## 3. How Was This Built — Step by Step

Think of the project like building a hospital:

---

### Step 1 — Collect Patient Records (Data Pipeline)

```
HuggingFace / Yahoo Finance
         ↓
    Raw price data
    (open, high, low, close, volume)
         ↓
    Clean the data
    (fill gaps, remove outliers, fix errors)
         ↓
    Saved as CSV files
```

Just like a hospital collects patient history before making a diagnosis.

---

### Step 2 — Run Medical Tests (Feature Engineering)

```
Clean price data
         ↓
    Calculate 37 indicators
    RSI, MACD, Bollinger Bands, EMA...
         ↓
    Each row now has 37 numbers
    describing what the market looks like at that moment
```

Just like a doctor runs blood tests, ECG, X-rays — we run 37 different "tests" on the price data to get a complete picture.

---

### Step 3 — Create Answer Key (Labeling)

This is the clever part. We look at historical data and ask:

> *"After this moment in time, did the price go UP more than 2% in the next 24 hours?"*

```
If price rose  > 2% in next 24 hours  →  Label = BUY  (0)
If price fell  > 2% in next 24 hours  →  Label = SELL (1)
Otherwise                              →  Label = HOLD (2)
```

We do this for all 17,000 historical data points. Now we have:
- **37 numbers** describing market conditions at each point
- **1 answer** (BUY/SELL/HOLD) telling us what actually happened

This is called **supervised learning** — we teach the AI by showing it the questions AND the answers.

---

### Step 4 — Teach the AI (Model Training)

We use an algorithm called **XGBoost** — the same algorithm used by winning teams in professional data science competitions worldwide.

```
Training data: First 80% of history (13,600 rows)
               AI studies this and learns patterns

Test data:     Last 20% of history (3,400 rows)
               AI is tested on data it has never seen
               Result: ~61% accuracy
               (vs 33% if it was just guessing randomly)
```

The AI essentially learns things like:
- *"When RSI is below 30 AND MACD is crossing upward AND volume is 2x normal → price usually goes up"*
- *"When price is 5% above EMA-50 AND RSI is above 70 → price usually corrects downward"*

---

### Step 5 — Verify It Works (Backtesting)

Before using real money, we simulate:

> *"If I had followed this AI's signals on the test data, how much money would I have made?"*

```
Starting capital: ₹1,00,000
Position size:    10% per trade (₹10,000)
Fee per trade:    0.1%

Result (approx):
  BTC: +14.2% return | 58% win rate
  ETH: +11.8% return | 55% win rate
  BNB: +12.4% return | 57% win rate
  SOL:  +9.6% return | 53% win rate
```

Only if these numbers pass the minimum thresholds does the model get deployed.

---

### Step 6 — Go Live (Real-time Signal Engine)

Every hour automatically:

```
Yahoo Finance (live prices)
         ↓
    Fetch last 200 candles
         ↓
    Calculate 37 indicators
         ↓
    Feed into trained XGBoost model
         ↓
    Model outputs: BUY (84% confident)
         ↓
    Filter: Is confidence >= 75%? YES
         ↓
    Format signal card:
        Entry: ₹66,000–₹66,500
        Target: ₹70,000 (+6%)
        Stop-loss: ₹64,200 (-3%)
        Position: 0.075 BTC (₹5,000)
         ↓
    Send to Telegram instantly
```

---

### Step 7 — Deliver and Display

**Telegram Bot** — You receive signals directly on your phone with tap buttons to check any coin anytime.

**Angular Dashboard** — A professional web app at `localhost:4200` showing:
- Live signal cards for all 4 coins
- Real candlestick charts with EMA, Bollinger Bands, RSI, MACD
- Full signal history table
- Backtest performance results
- Paper trading portfolio tracker

**FastAPI Backend** — A REST API connecting everything. The Angular app calls this API which calls the AI model.

---

## The Complete Picture in One Diagram

```
PAST (Train once)               PRESENT (Every hour)
─────────────────               ────────────────────

HuggingFace                     Yahoo Finance
2 years of data                 Last 200 candles
      ↓                               ↓
Calculate 37                    Calculate 37
indicators                      indicators
      ↓                               ↓
Label each row                  Feed into model
BUY/SELL/HOLD                         ↓
      ↓                         Model predicts
Train XGBoost                   BUY/SELL/HOLD
      ↓                         + confidence %
Save model.pkl ──────────────→       ↓
                                Filter by risk level
                                      ↓
                                Format signal card
                                      ↓
                           ┌──────────────────────┐
                           │  Telegram  │  Angular │
                           │    Bot     │  Dashboard│
                           └──────────────────────┘
```

---

## Simple One-Paragraph Explanation for Anyone

> AlgoBot Pro is an AI-powered trading assistant that watches Bitcoin, Ethereum, BNB and Solana prices 24/7. It was trained on 2 years of historical price data to recognise patterns that precede big price moves. Every hour it fetches the latest live prices, runs them through 37 technical calculations, and asks the AI model whether you should Buy, Sell or Hold. If the AI is confident enough, it sends you a full trading signal on Telegram — with exact entry price, target price, stop-loss, and the reason why. The whole system runs automatically on your laptop with a professional web dashboard to track everything visually.

---

## Why This Is Impressive Technically

| What | Why It Matters |
|---|---|
| **XGBoost ML model** | Industry standard algorithm used in professional quant trading |
| **37 features** | More signals than most retail traders even know about |
| **Hourly automation** | Never misses a signal while you sleep |
| **Walk-forward backtesting** | Tested on data the model never saw — honest results |
| **Angular frontend** | Production-grade web app, not just a script |
| **FastAPI backend** | RESTful API architecture like real fintech companies use |
| **Telegram delivery** | Signals reach you instantly anywhere in the world |
| **Risk management** | Entry zone, target, stop-loss and position size built in |

---

# AlgoBot Pro — Data Sources & Reference Links
> Complete reference document for all data sources, libraries, APIs and tools used in this project.

---

## 1. TRAINING DATA (Historical — Used to Train the AI)

### Primary Source — HuggingFace Dataset
| Detail | Info |
|--------|------|
| **Dataset Name** | sebdg/crypto_data |
| **Dataset Page** | https://huggingface.co/datasets/sebdg/crypto_data |
| **Direct Parquet URL** | https://huggingface.co/datasets/sebdg/crypto_data/resolve/refs%2Fconvert%2Fparquet/candles/train/0000.parquet |
| **What it contains** | Historical OHLCV (Open, High, Low, Close, Volume) candle data for 200+ crypto pairs |
| **Time range** | 2018 – 2024 (6+ years of hourly data) |
| **Format** | Parquet (columnar format, fast to load) |
| **Is it live?** | ❌ NO — Static historical dataset, downloaded once |
| **Cost** | FREE |

**How we use it in code:**
```python
# src/data_pipeline/fetch_huggingface.py
PARQUET_URL = "https://huggingface.co/datasets/sebdg/crypto_data/resolve/refs%2Fconvert%2Fparquet/candles/train/0000.parquet"
df = pd.read_parquet(PARQUET_URL)
```

**HuggingFace Platform Links:**
- HuggingFace Datasets Library Docs: https://huggingface.co/docs/datasets/quickstart
- HuggingFace Datasets GitHub: https://github.com/huggingface/datasets
- HuggingFace Datasets PyPI: https://pypi.org/project/datasets/
- All crypto datasets on HuggingFace: https://huggingface.co/datasets?other=cryptocurrency

---

## 2. LIVE DATA (Real-Time — Used Every Hour for Signals)

### Primary Live Source — Yahoo Finance via yfinance
| Detail | Info |
|--------|------|
| **Library Name** | yfinance |
| **PyPI Page** | https://pypi.org/project/yfinance/ |
| **Official Docs** | https://ranaroussi.github.io/yfinance/ |
| **API Reference** | https://ranaroussi.github.io/yfinance/reference/index.html |
| **GitHub Repo** | https://github.com/ranaroussi/yfinance |
| **Yahoo Finance Website** | https://finance.yahoo.com/ |
| **BTC live chart** | https://finance.yahoo.com/quote/BTC-USD/ |
| **ETH live chart** | https://finance.yahoo.com/quote/ETH-USD/ |
| **BNB live chart** | https://finance.yahoo.com/quote/BNB-USD/ |
| **SOL live chart** | https://finance.yahoo.com/quote/SOL-USD/ |
| **Is it live?** | ✅ YES — Fetches real-time prices every hour |
| **Cost** | FREE (for personal/research use) |
| **Rate limit** | No official limit, but use responsibly |

**How we use it in code:**
```python
# src/data_pipeline/fetch_live.py
import yfinance as yf

data = yf.download(
    "BTC-USD",
    period="200h",        # Last 200 hours
    interval="1h",        # Hourly candles
    progress=False,
    auto_adjust=True
)
# Returns: Open, High, Low, Close, Volume for each hour
```

**Ticker symbols used in our project:**
| Coin | Yahoo Finance Ticker | Live Price URL |
|------|---------------------|----------------|
| Bitcoin | `BTC-USD` | https://finance.yahoo.com/quote/BTC-USD/ |
| Ethereum | `ETH-USD` | https://finance.yahoo.com/quote/ETH-USD/ |
| BNB | `BNB-USD` | https://finance.yahoo.com/quote/BNB-USD/ |
| Solana | `SOL-USD` | https://finance.yahoo.com/quote/SOL-USD/ |

---

## 3. SUPPLEMENTARY DATA (Optional / Supporting)

### CoinGecko API — Market Cap, Fear & Greed
| Detail | Info |
|--------|------|
| **API Base URL** | https://api.coingecko.com/api/v3 |
| **Documentation** | https://www.coingecko.com/en/api/documentation |
| **BTC Price Endpoint** | https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd |
| **Is it live?** | ✅ YES — Real-time market data |
| **Cost** | FREE (up to 30 calls/minute on free tier) |

### Fear & Greed Index — Market Sentiment
| Detail | Info |
|--------|------|
| **API URL** | https://api.alternative.me/fng/ |
| **Website** | https://alternative.me/crypto/fear-and-greed-index/ |
| **What it gives** | A number from 0 (Extreme Fear) to 100 (Extreme Greed) |
| **Is it live?** | ✅ YES — Updated daily |
| **Cost** | FREE |

---

## 4. ML MODEL — XGBoost

| Detail | Info |
|--------|------|
| **Algorithm** | XGBoost (Extreme Gradient Boosting) |
| **Official Docs** | https://xgboost.readthedocs.io/ |
| **Getting Started** | https://xgboost.readthedocs.io/en/stable/get_started.html |
| **Python API** | https://xgboost.readthedocs.io/en/latest/python/python_api.html |
| **Parameters Guide** | https://xgboost.readthedocs.io/en/latest/parameter.html |
| **GitHub Repo** | https://github.com/dmlc/xgboost |
| **PyPI Page** | https://pypi.org/project/xgboost/ |
| **How it works** | https://xgboost.readthedocs.io/en/stable/tutorials/model.html |

**How we use it in code:**
```python
# src/models/train.py
from xgboost import XGBClassifier

model = XGBClassifier(
    n_estimators=300,
    max_depth=6,
    learning_rate=0.05,
    objective='multi:softprob',   # 3 classes: BUY / SELL / HOLD
    num_class=3,
    use_label_encoder=False
)
model.fit(X_train, y_train)
```

---

## 5. TECHNICAL ANALYSIS LIBRARY — ta

| Detail | Info |
|--------|------|
| **Library Name** | ta (Technical Analysis Library in Python) |
| **Official Docs** | https://technical-analysis-library-in-python.readthedocs.io/ |
| **GitHub Repo** | https://github.com/bukosabino/ta |
| **PyPI Page** | https://pypi.org/project/ta/ |
| **What it calculates** | RSI, MACD, Bollinger Bands, EMA, ATR, Stochastic, OBV and more |

**How we use it in code:**
```python
# src/features/indicators.py
import ta

df["rsi"]  = ta.momentum.RSIIndicator(df["close"], 14).rsi()
macd       = ta.trend.MACD(df["close"])
df["macd"] = macd.macd()
bb         = ta.volatility.BollingerBands(df["close"])
df["bb_upper"] = bb.bollinger_hband()
```

---

## 6. BACKEND FRAMEWORK — FastAPI

| Detail | Info |
|--------|------|
| **Framework** | FastAPI |
| **Official Docs** | https://fastapi.tiangolo.com/ |
| **GitHub Repo** | https://github.com/tiangolo/fastapi |
| **PyPI Page** | https://pypi.org/project/fastapi/ |
| **Tutorial** | https://fastapi.tiangolo.com/tutorial/ |
| **Our API runs at** | http://localhost:8000 |
| **Our API docs (auto-generated)** | http://localhost:8000/docs |

---

## 7. FRONTEND FRAMEWORK — Angular

| Detail | Info |
|--------|------|
| **Framework** | Angular 17 |
| **Official Docs** | https://angular.dev/ |
| **Angular CLI** | https://angular.dev/tools/cli |
| **Standalone Components Guide** | https://angular.dev/guide/components |
| **Angular Signals** | https://angular.dev/guide/signals |
| **Our dashboard runs at** | http://localhost:4200 |

---

## 8. CHARTS LIBRARY — Lightweight Charts

| Detail | Info |
|--------|------|
| **Library** | Lightweight Charts by TradingView |
| **Official Docs** | https://tradingview.github.io/lightweight-charts/ |
| **GitHub Repo** | https://github.com/tradingview/lightweight-charts |
| **npm Package** | https://www.npmjs.com/package/lightweight-charts |
| **Examples** | https://tradingview.github.io/lightweight-charts/docs/series-types |
| **What we use it for** | Candlestick, RSI, MACD and Volume charts |

---

## 9. CSS FRAMEWORK — Tailwind CSS

| Detail | Info |
|--------|------|
| **Framework** | Tailwind CSS v3 |
| **Official Docs** | https://tailwindcss.com/docs |
| **Installation** | https://tailwindcss.com/docs/installation |
| **Utility Classes** | https://tailwindcss.com/docs/utility-first |

---

## 10. TELEGRAM BOT API

| Detail | Info |
|--------|------|
| **Telegram Bot API Docs** | https://core.telegram.org/bots/api |
| **Create a bot (BotFather)** | https://t.me/BotFather |
| **Get your Chat ID** | https://t.me/userinfobot |
| **Telegram API Base URL** | https://api.telegram.org/bot{YOUR_TOKEN}/ |
| **sendMessage endpoint** | https://api.telegram.org/bot{TOKEN}/sendMessage |
| **getUpdates endpoint** | https://api.telegram.org/bot{TOKEN}/getUpdates |

---

## 11. OTHER PYTHON LIBRARIES USED

| Library | Purpose | Docs / PyPI |
|---------|---------|-------------|
| **pandas** | Data manipulation | https://pandas.pydata.org/docs/ |
| **numpy** | Numerical computation | https://numpy.org/doc/ |
| **scikit-learn** | Preprocessing, metrics | https://scikit-learn.org/ |
| **joblib** | Save/load ML models | https://joblib.readthedocs.io/ |
| **scipy** | Z-score outlier detection | https://scipy.org/ |
| **optuna** | Hyperparameter tuning | https://optuna.readthedocs.io/ |
| **APScheduler** | Hourly signal scheduling | https://apscheduler.readthedocs.io/ |
| **uvicorn** | ASGI server for FastAPI | https://www.uvicorn.org/ |
| **python-dotenv** | Load .env variables | https://pypi.org/project/python-dotenv/ |
| **requests** | HTTP calls to Telegram API | https://docs.python-requests.org/ |
| **sqlalchemy** | Database ORM | https://docs.sqlalchemy.org/ |

---

## 12. DATA FLOW SUMMARY

```
SOURCE              TYPE        LIVE?   USED FOR
────────────────────────────────────────────────────────────────
HuggingFace         Parquet     ❌ No   Training the AI model (once)
Yahoo Finance       OHLCV API   ✅ Yes  Every hour — live signals
CoinGecko           REST API    ✅ Yes  Supplementary market data
Fear & Greed Index  REST API    ✅ Yes  Market sentiment indicator
```

---

## 13. QUICK INSTALL REFERENCE

```bash
# All Python dependencies
pip install pandas numpy scikit-learn xgboost ta yfinance \
            fastapi uvicorn apscheduler python-dotenv \
            requests joblib scipy optuna sqlalchemy \
            python-telegram-bot pyarrow datasets

# All Angular dependencies
cd algobot-frontend
npm install
```

---

## 14. USEFUL LIVE DATA URLS YOU CAN OPEN IN BROWSER

```
BTC price (Yahoo Finance):
https://finance.yahoo.com/quote/BTC-USD/

ETH price (Yahoo Finance):
https://finance.yahoo.com/quote/ETH-USD/

BTC price (CoinGecko API):
https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd

ETH + BTC + BNB + SOL prices (CoinGecko API):
https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,binancecoin,solana&vs_currencies=usd

Fear & Greed Index (live):
https://api.alternative.me/fng/

HuggingFace training dataset:
https://huggingface.co/datasets/sebdg/crypto_data

Our FastAPI (when main.py is running):
http://localhost:8000/docs
http://localhost:8000/signals/all
http://localhost:8000/signal/BTC_USD
http://localhost:8000/status
```

---



