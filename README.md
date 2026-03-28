# AlgoBot Pro 🤖📈

**Algorithmic Trading Signal Bot — ML-powered BUY/SELL/HOLD signals for BTC, ETH, BNB, SOL**

Built with XGBoost · Yahoo Finance · Telegram · Streamlit · FastAPI

---

## What it does

- Fetches live crypto price data every hour
- Calculates 37 technical indicators (RSI, MACD, Bollinger Bands, EMA, ATR...)
- Runs an XGBoost model trained on 2+ years of historical data
- Sends BUY/SELL signals with entry price, target, stop-loss, and plain-English reasons
- Delivers via Telegram bot and a Streamlit web dashboard

---

## Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the full pipeline (first time only — trains the models)
```bash
python pipeline.py
```
This takes about 5-10 minutes. Runs: preprocess → engineer → label → train → backtest

### 3. Start the live system
```bash
python main.py
```
This starts the FastAPI server (port 8000) + hourly signal scheduler.

### 4. Open the dashboard (in a separate terminal)
```bash
streamlit run app/main.py
```
Open http://localhost:8501 in your browser.

---

## Telegram Setup (to receive signals on your phone)

1. Open Telegram → message **@BotFather** → send `/newbot`
2. Give your bot a name (e.g. "AlgoBot Pro Signals")
3. Copy the token BotFather gives you
4. Open `.env` and set:
   ```
   TELEGRAM_BOT_TOKEN=your_token_here
   TELEGRAM_TEST_CHAT_ID=your_chat_id_here
   ```
5. Get your chat ID by messaging **@userinfobot** on Telegram
6. Restart `python main.py`

---

## Project Structure

```
algobot-pro/
├── pipeline.py              ← Run this first (trains models)
├── main.py                  ← Run this to start live system
├── .env                     ← Your API keys (never commit this)
├── requirements.txt
│
├── data/
│   ├── raw/                 ← Downloaded OHLCV CSVs
│   ├── processed/           ← Cleaned + feature-engineered data
│   ├── labels/              ← BUY/SELL/HOLD labeled CSVs
│   └── signal_log.json      ← All generated signals (auto-created)
│
├── models/                  ← Trained XGBoost models (.pkl files)
│
├── src/
│   ├── data_pipeline/       ← fetch_huggingface.py, preprocess.py
│   ├── features/            ← indicators.py, engineer.py, labeler.py
│   ├── models/              ← train.py, tune.py, backtest.py
│   ├── signals/             ← generator.py, filter.py, formatter.py
│   ├── delivery/            ← telegram_bot.py, api.py
│   └── scheduler/           ← runner.py (hourly job)
│
└── app/
    └── main.py              ← Streamlit dashboard
```

---

## Run Commands Reference

```bash
# First time setup — full pipeline
python pipeline.py

# Start from a specific step
python pipeline.py --from label      # skip to labeling
python pipeline.py --from train      # skip to training
python pipeline.py --only backtest   # run only backtesting

# Live system
python main.py                        # API + scheduler
streamlit run app/main.py             # Dashboard only

# Manual signal generation (one-off)
python -c "
from src.signals.generator import generate_signal
from src.signals.formatter import format_signal
sig = generate_signal('BTC_USD')
card = format_signal(sig)
print(card['telegram_message'])
"

# Hyperparameter tuning (improves accuracy by ~3-5%)
python src/models/tune.py
```

---

## Revenue Model

| Tier       | Price           | Features                                    |
|------------|-----------------|---------------------------------------------|
| Free       | ₹0/month        | 3 signals/day, dashboard view               |
| Premium    | ₹999/month      | Unlimited signals, all coins, Telegram      |
| Pro        | ₹4,999/month    | All Premium + auto-trade via Zerodha        |
| Enterprise | Custom          | White-label, API access, custom assets      |

---

## Disclaimer

AlgoBot Pro is for **educational purposes only**. It does not constitute financial advice.
Trading in financial markets involves substantial risk of loss.
Past performance does not guarantee future results.

---

*Built with ❤️ using Python, XGBoost, and Streamlit*