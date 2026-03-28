"""
config/settings.py
===================
Central configuration for AlgoBot Pro.

Every hardcoded value in the project lives here.
All other files import from this file instead of
defining their own constants.

HOW TO USE:
    from config.settings import COINS, FORWARD_HOURS, RISK_THRESHOLDS
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ══════════════════════════════════════════════════════════════
# COINS & MARKETS
# ══════════════════════════════════════════════════════════════

# Coins the system tracks (HuggingFace market string → internal name)
COINS = {
    "BTC-USD": "BTC_USD",
    "ETH-USD": "ETH_USD",
    "BNB-USD": "BNB_USD",
    "SOL-USD": "SOL_USD",
}

# Human-readable display names for the dashboard
COIN_DISPLAY = {
    "BTC_USD": "BTC/USD",
    "ETH_USD": "ETH/USD",
    "BNB_USD": "BNB/USD",
    "SOL_USD": "SOL/USD",
}

# Yahoo Finance ticker map (for live data fetching)
YAHOO_TICKERS = {
    "BTC_USD": "BTC-USD",
    "ETH_USD": "ETH-USD",
    "BNB_USD": "BNB-USD",
    "SOL_USD": "SOL-USD",
}

# CoinGecko API coin IDs (for supplementary price data)
COINGECKO_IDS = {
    "BTC_USD": "bitcoin",
    "ETH_USD": "ethereum",
    "BNB_USD": "binancecoin",
    "SOL_USD": "solana",
}

# ══════════════════════════════════════════════════════════════
# DIRECTORY PATHS
# ══════════════════════════════════════════════════════════════

BASE_DIR      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR      = os.path.join(BASE_DIR, "data")
RAW_DIR       = os.path.join(DATA_DIR, "raw")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")
LIVE_DIR      = os.path.join(DATA_DIR, "live")
LABELS_DIR    = os.path.join(DATA_DIR, "labels")
MODELS_DIR    = os.path.join(BASE_DIR, "models")
LOGS_DIR      = os.path.join(BASE_DIR, "logs")
SIGNAL_LOG    = os.path.join(DATA_DIR, "signal_log.json")

# ══════════════════════════════════════════════════════════════
# DATA PIPELINE
# ══════════════════════════════════════════════════════════════

# HuggingFace dataset
HUGGINGFACE_DATASET_ID = "sebdg/crypto_data"
HUGGINGFACE_PARQUET_URL = (
    "https://huggingface.co/datasets/sebdg/crypto_data"
    "/resolve/refs%2Fconvert%2Fparquet/candles/train/0000.parquet"
)

# Preprocessing
MAX_GAP_FILL_HOURS     = 3      # Forward-fill gaps up to this many hours
OUTLIER_ZSCORE         = 4.0    # Drop rows where log-return z-score > this
MIN_ROWS_PER_COIN      = 1000   # Minimum rows expected after cleaning

# Live data fetching
LOOKBACK_CANDLES       = 200    # How many historical candles to fetch for indicators
LIVE_FETCH_INTERVAL_H  = 1      # Fetch new data every N hours

# ══════════════════════════════════════════════════════════════
# FEATURE ENGINEERING
# ══════════════════════════════════════════════════════════════

# RSI
RSI_WINDOW = 14

# MACD
MACD_FAST   = 12
MACD_SLOW   = 26
MACD_SIGNAL = 9

# Bollinger Bands
BB_WINDOW = 20
BB_STD    = 2.0

# EMA windows
EMA_SHORT  = 9
EMA_MID    = 21
EMA_LONG   = 50

# ATR
ATR_WINDOW = 14

# Stochastic
STOCH_WINDOW = 14
STOCH_SMOOTH = 3

# Volume
VOLUME_WINDOW = 20

# Lag periods for lag features
LAG_PERIODS = [1, 2, 3]

# Return periods (in candles)
RETURN_PERIODS = [1, 4, 24]

# Complete ordered list of feature columns used by the model
# ORDER MATTERS — model was trained with these exact columns in this order
FEATURE_COLUMNS = [
    "rsi",
    "macd_line",
    "macd_signal",
    "macd_histogram",
    "bb_upper",
    "bb_lower",
    "bb_width",
    "bb_pct",
    "ema_9",
    "ema_21",
    "ema_50",
    "ema_cross",
    "atr",
    "stoch_k",
    "stoch_d",
    "obv_norm",
    "volume_ratio",
    "rsi_lag1",
    "rsi_lag2",
    "rsi_lag3",
    "macd_line_lag1",
    "macd_line_lag2",
    "macd_histogram_lag1",
    "macd_histogram_lag2",
    "return_1h",
    "return_4h",
    "return_24h",
    "hour_of_day",
    "day_of_week",
    "is_weekend",
    "session_asia",
    "session_london",
    "session_us",
    "close_vs_ema50",
    "candle_body",
    "high_low_range",
    "candle_direction",
]

# ══════════════════════════════════════════════════════════════
# LABELING
# ══════════════════════════════════════════════════════════════

FORWARD_HOURS  = 24    # Look this many candles ahead to assign label
THRESHOLD_PCT  = 2.0   # Min % change to call BUY or SELL (else HOLD)

# Label integer encoding (do not change — model trained with these)
LABEL_BUY  = 0
LABEL_SELL = 1
LABEL_HOLD = 2

LABEL_NAMES = {
    LABEL_BUY:  "BUY",
    LABEL_SELL: "SELL",
    LABEL_HOLD: "HOLD",
}

LABEL_EMOJIS = {
    "BUY":  "🟢",
    "SELL": "🔴",
    "HOLD": "🟡",
}

# ══════════════════════════════════════════════════════════════
# MODEL TRAINING
# ══════════════════════════════════════════════════════════════

TRAIN_RATIO    = 0.80   # 80% train, 20% test (time-based split)
RANDOM_SEED    = 42
MODEL_VERSION  = os.getenv("MODEL_VERSION", "v1")

# Default XGBoost hyperparameters
XGBOOST_PARAMS = {
    "n_estimators":     300,
    "max_depth":        6,
    "learning_rate":    0.05,
    "subsample":        0.8,
    "colsample_bytree": 0.8,
    "min_child_weight": 5,
    "gamma":            0.1,
    "reg_alpha":        0.1,
    "reg_lambda":       1.0,
    "objective":        "multi:softprob",
    "num_class":        3,
    "eval_metric":      "mlogloss",
    "random_state":     RANDOM_SEED,
    "n_jobs":           -1,
    "verbosity":        0,
}

# Optuna hyperparameter search
OPTUNA_TRIALS  = 50
OPTUNA_CV_FOLDS = 3

# ══════════════════════════════════════════════════════════════
# SIGNAL GENERATION & FILTERING
# ══════════════════════════════════════════════════════════════

# Minimum confidence per risk level to send a signal
RISK_THRESHOLDS = {
    "low":    0.85,
    "medium": 0.75,
    "high":   0.65,
}

DEFAULT_RISK_LEVEL = os.getenv("DEFAULT_RISK_LEVEL", "medium")

# Minimum volume ratio to allow a signal (avoids illiquid markets)
MIN_VOLUME_RATIO = 0.80

# ══════════════════════════════════════════════════════════════
# SIGNAL FORMATTING & POSITION SIZING
# ══════════════════════════════════════════════════════════════

DEFAULT_CAPITAL     = float(os.getenv("DEFAULT_CAPITAL", "50000"))
POSITION_SIZE_PCT   = 0.10    # Use 10% of capital per trade
BUY_TARGET_PCT      = 0.06    # Target = entry + 6%
SELL_TARGET_PCT     = 0.06    # Target = entry - 6%
STOP_LOSS_PCT       = 0.03    # Stop-loss = entry ± 3%
ENTRY_ZONE_PCT      = 0.005   # Entry zone = ±0.5% around current price
TRADE_FEE_PCT       = 0.001   # 0.1% fee per trade

# ══════════════════════════════════════════════════════════════
# BACKTESTING
# ══════════════════════════════════════════════════════════════

BACKTEST_CAPITAL    = 100_000.0
BACKTEST_CONF_MIN   = 0.65
BACKTEST_MAX_HOLD_H = 48       # Max hours to hold a position

# Minimum performance gates for deployment
MIN_WIN_RATE        = 52.0     # %
MIN_TOTAL_RETURN    = 10.0     # %
MAX_DRAWDOWN        = -25.0    # %
MIN_SHARPE          = 0.8

# ══════════════════════════════════════════════════════════════
# SCHEDULER
# ══════════════════════════════════════════════════════════════

SCHEDULER_TIMEZONE      = "UTC"
SIGNAL_RUN_MINUTE       = 0     # Run at :00 of every hour
MAX_SIGNAL_LOG_ENTRIES  = 1000  # Keep last N signals in log

# ══════════════════════════════════════════════════════════════
# DELIVERY
# ══════════════════════════════════════════════════════════════

# Telegram
TELEGRAM_BOT_TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID     = os.getenv("TELEGRAM_TEST_CHAT_ID", "")

# Email
EMAIL_SENDER    = os.getenv("EMAIL_SENDER", "")
EMAIL_PASSWORD  = os.getenv("EMAIL_PASSWORD", "")
EMAIL_SMTP_HOST = os.getenv("EMAIL_SMTP_HOST", "smtp.gmail.com")
EMAIL_SMTP_PORT = int(os.getenv("EMAIL_SMTP_PORT", "587"))

# API
API_HOST = "0.0.0.0"
API_PORT = 8000

# Dashboard
DASHBOARD_PORT = 8501

# ══════════════════════════════════════════════════════════════
# SUBSCRIBERS (in production, load from database)
# ══════════════════════════════════════════════════════════════

# Default subscriber — loaded from .env
DEFAULT_SUBSCRIBER = {
    "chat_id":    TELEGRAM_CHAT_ID,
    "coins":      list(COINS.values()),
    "risk_level": DEFAULT_RISK_LEVEL,
    "capital":    DEFAULT_CAPITAL,
}

# ══════════════════════════════════════════════════════════════
# HEALTH CHECK
# ══════════════════════════════════════════════════════════════

HEALTH_CHECK_INTERVAL_MIN = 30   # Run health check every N minutes
MAX_DATA_STALENESS_H      = 3    # Alert if data is older than N hours
MAX_SIGNAL_STALENESS_H    = 3    # Alert if no signal in N hours

# ══════════════════════════════════════════════════════════════
# APP ENVIRONMENT
# ══════════════════════════════════════════════════════════════

APP_ENV   = os.getenv("APP_ENV", "development")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
IS_PROD   = APP_ENV == "production"

# ══════════════════════════════════════════════════════════════
# HELPER: ensure all directories exist
# ══════════════════════════════════════════════════════════════

def ensure_dirs() -> None:
    """Create all required directories if they don't exist."""
    for directory in [RAW_DIR, PROCESSED_DIR, LIVE_DIR,
                      LABELS_DIR, MODELS_DIR, LOGS_DIR]:
        os.makedirs(directory, exist_ok=True)


if __name__ == "__main__":
    # Print all settings when run directly — useful for debugging
    print("AlgoBot Pro — Configuration Summary")
    print("=" * 45)
    print(f"  Coins tracked  : {list(COINS.values())}")
    print(f"  Model version  : {MODEL_VERSION}")
    print(f"  Risk level     : {DEFAULT_RISK_LEVEL}")
    print(f"  Capital        : Rs {DEFAULT_CAPITAL:,.0f}")
    print(f"  Forward hours  : {FORWARD_HOURS}h")
    print(f"  Threshold      : ±{THRESHOLD_PCT}%")
    print(f"  Feature count  : {len(FEATURE_COLUMNS)}")
    print(f"  Telegram       : {'configured' if TELEGRAM_BOT_TOKEN else 'NOT configured'}")
    print(f"  Email          : {'configured' if EMAIL_SENDER else 'NOT configured'}")
    print(f"  Environment    : {APP_ENV}")
    print(f"  Base dir       : {BASE_DIR}")
    ensure_dirs()
    print("  Directories    : all created")