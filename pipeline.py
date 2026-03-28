"""
pipeline.py
============
Master pipeline script — runs every step in the correct order.

Place this file in the ROOT of your project:
    C:\\Users\\GHANSHYAM\\Desktop\\algobot-pro\\pipeline.py

HOW TO RUN:
    python pipeline.py               # Full pipeline (all steps)
    python pipeline.py --from label  # Start from labeling onwards
    python pipeline.py --from train  # Start from training onwards
    python pipeline.py --only train  # Run only training

STEPS:
    1. preprocess  — clean raw CSVs
    2. engineer    — calculate indicators + build feature matrix
    3. label       — create BUY/SELL/HOLD labels
    4. train       — train XGBoost model
    5. backtest    — verify model performance
"""

import os
import sys
import logging
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ── coin list ─────────────────────────────────────────────────────────────────
COINS = ["BTC_USD", "ETH_USD", "BNB_USD", "SOL_USD"]

# ── directories ───────────────────────────────────────────────────────────────
RAW_DIR       = os.path.join("data", "raw")
PROCESSED_DIR = os.path.join("data", "processed")
LABELS_DIR    = os.path.join("data", "labels")
MODELS_DIR    = "models"

for d in [RAW_DIR, PROCESSED_DIR, LABELS_DIR, MODELS_DIR]:
    os.makedirs(d, exist_ok=True)


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — PREPROCESS
# ══════════════════════════════════════════════════════════════════════════════

def step_preprocess():
    log.info("\n" + "="*55)
    log.info("STEP 1 — Preprocessing raw data")
    log.info("="*55)

    import numpy as np
    from scipy import stats

    MAX_GAP  = 3       # forward-fill gaps up to 3 candles
    Z_THRESH = 4.0     # drop rows where log-return z-score > 4

    def process_one(coin_name: str):
        path = os.path.join(RAW_DIR, f"{coin_name}_raw.csv")
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"Raw file missing: {path}\n"
                f"Run fetch first:\n"
                f"  python src/data_pipeline/fetch_huggingface.py"
            )

        df = pd.read_csv(path, parse_dates=["datetime"])
        log.info(f"  {coin_name}: loaded {len(df):,} raw rows")

        # ── gap fill ─────────────────────────────────────────────────────
        df = df.set_index("datetime")
        df.index = pd.DatetimeIndex(df.index)
        df = df.resample("1h").first()
        df = df.ffill(limit=MAX_GAP)
        df = df.dropna(subset=["close"])
        df = df.reset_index()

        # ── outlier removal ───────────────────────────────────────────────
        df["_lr"] = np.log(df["close"] / df["close"].shift(1))
        df = df.dropna(subset=["_lr"])
        z = np.abs(stats.zscore(df["_lr"]))
        before = len(df)
        df = df[z <= Z_THRESH].drop(columns=["_lr"]).reset_index(drop=True)
        removed = before - len(df)
        if removed:
            log.info(f"  {coin_name}: removed {removed} outlier rows")

        # ── fix OHLC violations ───────────────────────────────────────────
        df["high"] = df[["high", "open", "close"]].max(axis=1)
        df["low"]  = df[["low",  "open", "close"]].min(axis=1)

        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].astype("float64")

        out = os.path.join(PROCESSED_DIR, f"{coin_name}_processed.csv")
        df.to_csv(out, index=False)
        log.info(f"  {coin_name}: saved {len(df):,} rows → {out}")
        return df

    results = {}
    for coin in COINS:
        try:
            results[coin] = process_one(coin)
        except Exception as e:
            log.error(f"  FAILED {coin}: {e}")
    return results


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — ENGINEER FEATURES
# ══════════════════════════════════════════════════════════════════════════════

def step_engineer():
    log.info("\n" + "="*55)
    log.info("STEP 2 — Engineering features")
    log.info("="*55)

    import ta
    import numpy as np

    FEATURE_COLS = [
        "rsi", "macd_line", "macd_signal", "macd_histogram",
        "bb_upper", "bb_lower", "bb_width", "bb_pct",
        "ema_9", "ema_21", "ema_50", "ema_cross",
        "atr", "stoch_k", "stoch_d", "obv_norm", "volume_ratio",
        "rsi_lag1", "rsi_lag2", "rsi_lag3",
        "macd_line_lag1", "macd_line_lag2",
        "macd_histogram_lag1", "macd_histogram_lag2",
        "return_1h", "return_4h", "return_24h",
        "hour_of_day", "day_of_week", "is_weekend",
        "session_asia", "session_london", "session_us",
        "close_vs_ema50", "candle_body", "high_low_range", "candle_direction",
    ]

    def engineer_one(coin_name: str):
        path = os.path.join(PROCESSED_DIR, f"{coin_name}_processed.csv")
        if not os.path.exists(path):
            raise FileNotFoundError(f"Processed file missing: {path}")

        df = pd.read_csv(path, parse_dates=["datetime"])

        # ── indicators ────────────────────────────────────────────────────
        df["rsi"]            = ta.momentum.RSIIndicator(df["close"], 14).rsi()
        macd                 = ta.trend.MACD(df["close"])
        df["macd_line"]      = macd.macd()
        df["macd_signal"]    = macd.macd_signal()
        df["macd_histogram"] = macd.macd_diff()
        bb                   = ta.volatility.BollingerBands(df["close"])
        df["bb_upper"]       = bb.bollinger_hband()
        df["bb_lower"]       = bb.bollinger_lband()
        df["bb_width"]       = bb.bollinger_wband()
        df["bb_pct"]         = bb.bollinger_pband()
        df["ema_9"]          = ta.trend.EMAIndicator(df["close"], 9).ema_indicator()
        df["ema_21"]         = ta.trend.EMAIndicator(df["close"], 21).ema_indicator()
        df["ema_50"]         = ta.trend.EMAIndicator(df["close"], 50).ema_indicator()
        df["ema_cross"]      = np.where(df["ema_9"] > df["ema_21"], 1, -1)
        df["atr"]            = ta.volatility.AverageTrueRange(
                                   df["high"], df["low"], df["close"]).average_true_range()
        stoch                = ta.momentum.StochasticOscillator(
                                   df["high"], df["low"], df["close"])
        df["stoch_k"]        = stoch.stoch()
        df["stoch_d"]        = stoch.stoch_signal()
        obv                  = ta.volume.OnBalanceVolumeIndicator(
                                   df["close"], df["volume"]).on_balance_volume()
        df["obv_norm"]       = obv / obv.rolling(20).mean()
        df["volume_ratio"]   = df["volume"] / df["volume"].rolling(20).mean()

        # ── lag features ──────────────────────────────────────────────────
        for lag in [1, 2, 3]:
            df[f"rsi_lag{lag}"] = df["rsi"].shift(lag)
        for lag in [1, 2]:
            df[f"macd_line_lag{lag}"]      = df["macd_line"].shift(lag)
            df[f"macd_histogram_lag{lag}"] = df["macd_histogram"].shift(lag)

        # ── return features ───────────────────────────────────────────────
        df["return_1h"]  = df["close"].pct_change(1)  * 100
        df["return_4h"]  = df["close"].pct_change(4)  * 100
        df["return_24h"] = df["close"].pct_change(24) * 100

        # ── time features ─────────────────────────────────────────────────
        dt = pd.to_datetime(df["datetime"], utc=True)
        df["hour_of_day"]    = dt.dt.hour
        df["day_of_week"]    = dt.dt.dayofweek
        df["is_weekend"]     = (df["day_of_week"] >= 5).astype(int)
        df["session_asia"]   = ((df["hour_of_day"] >= 0)  & (df["hour_of_day"] < 8)).astype(int)
        df["session_london"] = ((df["hour_of_day"] >= 8)  & (df["hour_of_day"] < 13)).astype(int)
        df["session_us"]     = ((df["hour_of_day"] >= 13) & (df["hour_of_day"] < 22)).astype(int)

        # ── price context ─────────────────────────────────────────────────
        df["close_vs_ema50"]   = (df["close"] - df["ema_50"]) / df["ema_50"] * 100
        df["candle_body"]      = abs(df["close"] - df["open"]) / df["close"] * 100
        df["high_low_range"]   = (df["high"] - df["low"]) / df["close"] * 100
        df["candle_direction"] = np.sign(df["close"] - df["open"])

        # ── drop warmup NaNs ──────────────────────────────────────────────
        before = len(df)
        df = df.dropna(subset=FEATURE_COLS).reset_index(drop=True)
        log.info(f"  {coin_name}: dropped {before-len(df)} warmup rows → {len(df):,} rows")

        out = os.path.join(PROCESSED_DIR, f"{coin_name}_features.csv")
        df.to_csv(out, index=False)
        log.info(f"  {coin_name}: saved features → {out}")
        return df, FEATURE_COLS

    results = {}
    feature_cols = None
    for coin in COINS:
        try:
            df, feature_cols = engineer_one(coin)
            results[coin] = df
        except Exception as e:
            log.error(f"  FAILED {coin}: {e}")

    return results, feature_cols


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — CREATE LABELS
# ══════════════════════════════════════════════════════════════════════════════

def step_label():
    log.info("\n" + "="*55)
    log.info("STEP 3 — Creating BUY / SELL / HOLD labels")
    log.info("="*55)

    import numpy as np

    FORWARD_HOURS = 24
    THRESHOLD_PCT = 2.0

    def label_one(coin_name: str):
        path = os.path.join(PROCESSED_DIR, f"{coin_name}_features.csv")
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"Features file missing: {path}\n"
                f"Run step_engineer() first."
            )
        df = pd.read_csv(path, parse_dates=["datetime"])

        future_close        = df["close"].shift(-FORWARD_HOURS)
        df["future_return"] = (future_close - df["close"]) / df["close"] * 100

        conditions = [
            df["future_return"] >  THRESHOLD_PCT,
            df["future_return"] < -THRESHOLD_PCT,
        ]
        df["label"] = np.select(conditions, [0, 1], default=2).astype(int)
        df = df.dropna(subset=["future_return"]).reset_index(drop=True)

        # Log distribution
        total  = len(df)
        counts = df["label"].value_counts().sort_index()
        names  = {0: "BUY", 1: "SELL", 2: "HOLD"}
        log.info(f"  {coin_name}: {total:,} labeled rows")
        for lbl, cnt in counts.items():
            log.info(f"    {names.get(lbl,'?'):4s}: {cnt:6,}  ({cnt/total*100:.1f}%)")

        out = os.path.join(LABELS_DIR, f"{coin_name}_labeled.csv")
        df.to_csv(out, index=False)
        log.info(f"  Saved → {out}")
        return df

    results = {}
    for coin in COINS:
        try:
            results[coin] = label_one(coin)
        except Exception as e:
            log.error(f"  FAILED {coin}: {e}")
    return results


# ══════════════════════════════════════════════════════════════════════════════
# STEP 4 — TRAIN
# ══════════════════════════════════════════════════════════════════════════════

def step_train():
    log.info("\n" + "="*55)
    log.info("STEP 4 — Training XGBoost models")
    log.info("="*55)

    import json
    import joblib
    import numpy as np
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import accuracy_score, roc_auc_score, classification_report
    from sklearn.utils.class_weight import compute_sample_weight
    from xgboost import XGBClassifier

    # These must match exactly what engineer_one() saves
    FEATURE_COLS = [
        "rsi", "macd_line", "macd_signal", "macd_histogram",
        "bb_upper", "bb_lower", "bb_width", "bb_pct",
        "ema_9", "ema_21", "ema_50", "ema_cross",
        "atr", "stoch_k", "stoch_d", "obv_norm", "volume_ratio",
        "rsi_lag1", "rsi_lag2", "rsi_lag3",
        "macd_line_lag1", "macd_line_lag2",
        "macd_histogram_lag1", "macd_histogram_lag2",
        "return_1h", "return_4h", "return_24h",
        "hour_of_day", "day_of_week", "is_weekend",
        "session_asia", "session_london", "session_us",
        "close_vs_ema50", "candle_body", "high_low_range", "candle_direction",
    ]

    PARAMS = {
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
        "random_state":     42,
        "n_jobs":           -1,
        "verbosity":        0,
    }

    LABEL_NAMES = {0: "BUY", 1: "SELL", 2: "HOLD"}

    def train_one(coin_name: str):
        path = os.path.join(LABELS_DIR, f"{coin_name}_labeled.csv")
        if not os.path.exists(path):
            raise FileNotFoundError(f"Labeled file missing: {path}")

        df = pd.read_csv(path, parse_dates=["datetime"])

        # Verify all feature columns exist
        missing = [c for c in FEATURE_COLS if c not in df.columns]
        if missing:
            raise KeyError(f"Missing feature columns: {missing}")

        # Time-based split (80/20) — no random shuffle
        split = int(len(df) * 0.80)
        train_df = df.iloc[:split]
        test_df  = df.iloc[split:]

        log.info(f"  {coin_name}: train={len(train_df):,}  test={len(test_df):,}")

        X_train = train_df[FEATURE_COLS].values
        y_train = train_df["label"].values.astype(int)
        X_test  = test_df[FEATURE_COLS].values
        y_test  = test_df["label"].values.astype(int)

        # Scale features
        scaler  = StandardScaler()
        X_train = scaler.fit_transform(X_train)
        X_test  = scaler.transform(X_test)

        # Class-balanced sample weights
        weights = compute_sample_weight("balanced", y_train)

        # Train
        model = XGBClassifier(**PARAMS)
        model.fit(X_train, y_train, sample_weight=weights, verbose=False)

        # Evaluate
        y_pred  = model.predict(X_test)
        y_proba = model.predict_proba(X_test)
        acc     = accuracy_score(y_test, y_pred)
        try:
            auc = roc_auc_score(y_test, y_proba, multi_class="ovr", average="macro")
        except Exception:
            auc = 0.0

        log.info(f"  {coin_name}: accuracy={acc:.4f}  auc={auc:.4f}")

        report = classification_report(
            y_test, y_pred,
            target_names=["BUY", "SELL", "HOLD"],
            zero_division=0,
        )
        log.info(f"\n{report}")

        # Save model + scaler + feature list
        model_path  = os.path.join(MODELS_DIR, f"xgb_{coin_name}_v1.pkl")
        scaler_path = os.path.join(MODELS_DIR, f"scaler_{coin_name}.pkl")
        feat_path   = os.path.join(MODELS_DIR, "feature_names.json")

        joblib.dump(model,  model_path)
        joblib.dump(scaler, scaler_path)
        with open(feat_path, "w") as f:
            json.dump(FEATURE_COLS, f, indent=2)

        log.info(f"  Saved model  → {model_path}")
        log.info(f"  Saved scaler → {scaler_path}")

        return {"accuracy": acc, "auc": auc}

    results = {}
    for coin in COINS:
        try:
            results[coin] = train_one(coin)
        except Exception as e:
            log.error(f"  FAILED {coin}: {e}")

    log.info("\n── Training Summary ──────────────────────────────")
    for coin, res in results.items():
        log.info(f"  {coin}: accuracy={res['accuracy']:.2%}  auc={res['auc']:.4f}")

    return results


# ══════════════════════════════════════════════════════════════════════════════
# STEP 5 — BACKTEST
# ══════════════════════════════════════════════════════════════════════════════

def step_backtest():
    log.info("\n" + "="*55)
    log.info("STEP 5 — Backtesting models")
    log.info("="*55)

    import json
    import joblib
    import numpy as np

    CONF_MIN      = 0.65
    CAPITAL       = 100_000.0
    POS_SIZE      = 0.10
    FEE           = 0.001
    MAX_HOLD_H    = 48

    FEATURE_COLS = json.load(open(os.path.join(MODELS_DIR, "feature_names.json")))

    def backtest_one(coin_name: str):
        labeled_path = os.path.join(LABELS_DIR, f"{coin_name}_labeled.csv")
        model_path   = os.path.join(MODELS_DIR, f"xgb_{coin_name}_v1.pkl")
        scaler_path  = os.path.join(MODELS_DIR, f"scaler_{coin_name}.pkl")

        df     = pd.read_csv(labeled_path, parse_dates=["datetime"])
        model  = joblib.load(model_path)
        scaler = joblib.load(scaler_path)

        # Use only the test portion (last 20%)
        split  = int(len(df) * 0.80)
        test   = df.iloc[split:].reset_index(drop=True)

        X      = scaler.transform(test[FEATURE_COLS].values)
        proba  = model.predict_proba(X)
        labels = proba.argmax(axis=1)
        confs  = proba.max(axis=1)

        test["pred"]       = labels
        test["confidence"] = confs

        # Simulate trades
        capital  = CAPITAL
        trades   = []
        pos      = None
        entry_p  = 0.0
        entry_i  = 0
        pos_size = 0.0

        for i, row in test.iterrows():
            price = row["close"]
            sig   = int(row["pred"])
            conf  = float(row["confidence"])

            if pos is None and conf >= CONF_MIN:
                if sig == 0:   # BUY
                    val      = capital * POS_SIZE
                    pos_size = (val - val * FEE) / price
                    entry_p  = price
                    entry_i  = i
                    pos      = "LONG"
                elif sig == 1: # SELL
                    val      = capital * POS_SIZE
                    pos_size = (val - val * FEE) / price
                    entry_p  = price
                    entry_i  = i
                    pos      = "SHORT"

            elif pos == "LONG":
                held = i - entry_i
                if (sig == 1 and conf >= CONF_MIN) or held >= MAX_HOLD_H:
                    pnl      = (price - entry_p) * pos_size - price * pos_size * FEE
                    capital += pnl
                    trades.append({"dir": "LONG", "pnl": pnl, "dur": held})
                    pos = None

            elif pos == "SHORT":
                held = i - entry_i
                if (sig == 0 and conf >= CONF_MIN) or held >= MAX_HOLD_H:
                    pnl      = (entry_p - price) * pos_size - price * pos_size * FEE
                    capital += pnl
                    trades.append({"dir": "SHORT", "pnl": pnl, "dur": held})
                    pos = None

        if not trades:
            log.warning(f"  {coin_name}: No trades executed (try lowering CONF_MIN)")
            return {}

        t         = pd.DataFrame(trades)
        wins      = (t["pnl"] > 0).sum()
        total_ret = (capital - CAPITAL) / CAPITAL * 100
        win_rate  = wins / len(t) * 100
        g_profit  = t.loc[t["pnl"] > 0, "pnl"].sum()
        g_loss    = abs(t.loc[t["pnl"] <= 0, "pnl"].sum())
        pf        = g_profit / g_loss if g_loss > 0 else float("inf")

        log.info(f"  {coin_name}:")
        log.info(f"    Trades     : {len(t)}")
        log.info(f"    Win rate   : {win_rate:.1f}%")
        log.info(f"    Total ret  : {total_ret:+.2f}%")
        log.info(f"    Profit fact: {pf:.2f}")
        log.info(f"    Final cap  : Rs {capital:,.0f}")

        return {
            "trades": len(t), "win_rate": win_rate,
            "total_return": total_ret, "profit_factor": pf,
        }

    results = {}
    for coin in COINS:
        try:
            results[coin] = backtest_one(coin)
        except Exception as e:
            log.error(f"  FAILED {coin}: {e}")

    return results


# ══════════════════════════════════════════════════════════════════════════════
# MASTER RUNNER
# ══════════════════════════════════════════════════════════════════════════════

STEPS = {
    "preprocess": step_preprocess,
    "engineer":   step_engineer,
    "label":      step_label,
    "train":      step_train,
    "backtest":   step_backtest,
}

STEP_ORDER = ["preprocess", "engineer", "label", "train", "backtest"]


def run_pipeline(from_step: str = "preprocess", only_step: str = None):
    """
    Run the full pipeline from a given step, or run a single step.

    Args:
        from_step:  Start from this step (inclusive)
        only_step:  If set, run only this step
    """
    log.info("\n" + "█"*55)
    log.info("  AlgoBot Pro — Master Pipeline")
    log.info("█"*55)

    if only_step:
        if only_step not in STEPS:
            log.error(f"Unknown step: {only_step}. Choose from: {STEP_ORDER}")
            return
        log.info(f"Running single step: {only_step}")
        STEPS[only_step]()
        return

    if from_step not in STEP_ORDER:
        log.error(f"Unknown step: {from_step}. Choose from: {STEP_ORDER}")
        return

    start_idx = STEP_ORDER.index(from_step)
    steps_to_run = STEP_ORDER[start_idx:]

    log.info(f"Running steps: {' → '.join(steps_to_run)}\n")

    for step_name in steps_to_run:
        try:
            STEPS[step_name]()
        except Exception as e:
            log.error(f"\nPipeline failed at step '{step_name}': {e}")
            log.error("Fix the error above and re-run from this step:")
            log.error(f"  python pipeline.py --from {step_name}")
            sys.exit(1)

    log.info("\n" + "█"*55)
    log.info("  Pipeline complete! All steps finished successfully.")
    log.info("  Models saved to: models/")
    log.info("  Next: python main.py  (start live signal engine)")
    log.info("█"*55)


if __name__ == "__main__":
    # Parse command line arguments
    from_step  = "preprocess"
    only_step  = None

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--from" and i+1 < len(args):
            from_step = args[i+1]
            i += 2
        elif args[i] == "--only" and i+1 < len(args):
            only_step = args[i+1]
            i += 2
        else:
            i += 1

    run_pipeline(from_step=from_step, only_step=only_step)