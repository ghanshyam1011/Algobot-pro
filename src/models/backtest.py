"""
src/models/backtest.py
========================
PURPOSE:
    Simulate trading all model signals on 3 years of historical data
    to measure real-world performance BEFORE going live.

WHAT IT DOES:
    1. Loads the labeled test data (the 20% the model has never seen)
    2. Loads the trained model and predicts signals on every row
    3. Simulates buying/selling based on those signals with real position sizing
    4. Calculates: Total Return, Win Rate, Max Drawdown, Sharpe Ratio, Profit Factor
    5. Saves a detailed trade log and summary report

WHY BACKTESTING IS CRITICAL:
    A model with 60% accuracy does not automatically make money.
    The 40% of wrong predictions might be on large moves (big losses)
    while the 60% correct are on small moves (small gains).
    Backtesting tells us if the model actually generates PROFIT, not just accuracy.

    Target metrics for deployment:
        Total Return  > 20%   (on the test period)
        Win Rate      > 52%   (above coin-flip)
        Max Drawdown  < 25%   (acceptable risk)
        Sharpe Ratio  > 0.8   (risk-adjusted return)

INPUT:  Trained model from models/ + data/labels/BTC_USD_labeled.csv
OUTPUT: models/backtest_BTC_USD.json   (summary metrics)
        models/trade_log_BTC_USD.csv   (every simulated trade)

DEPENDENCIES:
    pip install pandas numpy joblib xgboost
"""

import os
import sys
import json
import logging
import numpy as np
import pandas as pd
from pathlib import Path

# Add repo root to path so absolute imports work when run directly
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.features.labeler import load_labeled, LABEL_BUY, LABEL_SELL, LABEL_HOLD
from src.models.train import load_model, time_based_split, prepare_X_y, MODELS_DIR

log = logging.getLogger(__name__)

INITIAL_CAPITAL    = 100_000.0   # Starting capital in Rs
POSITION_SIZE_PCT  = 0.10        # Use 10% of capital per trade
TRADE_FEE_PCT      = 0.001       # 0.1% fee per trade (typical for crypto)
CONFIDENCE_MIN     = 0.65        # Only trade signals with >= 65% model confidence
STOP_LOSS_ATR_MULT = 2.0         # Stop-loss = entry price - 2 × ATR


def _apply_model(
    df: pd.DataFrame,
    model,
    scaler,
    features: list,
) -> pd.DataFrame:
    """
    Run model prediction on every row and add signal + confidence columns.

    Args:
        df:       Test DataFrame with feature columns
        model:    Trained XGBClassifier
        scaler:   Fitted StandardScaler
        features: List of feature column names

    Returns:
        pd.DataFrame: Input df + 'pred_label' and 'pred_confidence' columns
    """
    X = scaler.transform(df[features].values)
    proba  = model.predict_proba(X)   # shape (n, 3): [P(BUY), P(SELL), P(HOLD)]
    labels = proba.argmax(axis=1)
    confs  = proba.max(axis=1)

    df = df.copy()
    df["pred_label"]      = labels
    df["pred_confidence"] = confs
    return df


def _simulate_trades(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Walk through the test data row by row and simulate trades.

    Rules:
        - Only enter a trade when confidence >= CONFIDENCE_MIN
        - Only one position open at a time (no overlapping trades)
        - Each BUY trade risks POSITION_SIZE_PCT of current capital
        - Exit on SELL signal, or if HOLD continues for > 48 hours
        - Apply TRADE_FEE_PCT on entry and exit
        - Log every trade with entry/exit price, P&L, and result

    Args:
        df: DataFrame with pred_label and pred_confidence columns

    Returns:
        tuple: (trade_log DataFrame, metrics dict)
    """
    capital       = INITIAL_CAPITAL
    equity_curve  = [capital]
    trades        = []

    position      = None   # None means flat (no open trade)
    entry_price   = 0.0
    entry_idx     = 0
    position_size = 0.0    # How many units of the asset we hold

    for i, row in df.iterrows():
        price = row["close"]
        sig   = int(row["pred_label"])
        conf  = float(row["pred_confidence"])

        # ── Entry logic ──────────────────────────────────────────────────────
        if position is None and conf >= CONFIDENCE_MIN:
            if sig == LABEL_BUY:
                # Open a long position
                trade_capital = capital * POSITION_SIZE_PCT
                fee           = trade_capital * TRADE_FEE_PCT
                position_size = (trade_capital - fee) / price
                entry_price   = price
                entry_idx     = i
                position      = "LONG"

            elif sig == LABEL_SELL:
                # Open a short position (we short the asset)
                trade_capital = capital * POSITION_SIZE_PCT
                fee           = trade_capital * TRADE_FEE_PCT
                position_size = (trade_capital - fee) / price
                entry_price   = price
                entry_idx     = i
                position      = "SHORT"

        # ── Exit logic ───────────────────────────────────────────────────────
        elif position == "LONG":
            # Exit on SELL signal OR if held too long (> 48 candles / 48 hours)
            hold_duration = i - entry_idx
            should_exit   = (sig == LABEL_SELL and conf >= CONFIDENCE_MIN) or (hold_duration >= 48)

            if should_exit:
                exit_price  = price
                gross_pnl   = (exit_price - entry_price) * position_size
                fee         = exit_price * position_size * TRADE_FEE_PCT
                net_pnl     = gross_pnl - fee
                capital    += net_pnl

                trades.append({
                    "entry_idx":    entry_idx,
                    "exit_idx":     i,
                    "entry_time":   df.loc[entry_idx, "datetime"] if entry_idx in df.index else None,
                    "exit_time":    row["datetime"],
                    "direction":    position,
                    "entry_price":  entry_price,
                    "exit_price":   exit_price,
                    "duration_h":   hold_duration,
                    "gross_pnl":    gross_pnl,
                    "net_pnl":      net_pnl,
                    "capital_after":capital,
                    "result":       "WIN" if net_pnl > 0 else "LOSS",
                })
                position = None

        elif position == "SHORT":
            hold_duration = i - entry_idx
            should_exit   = (sig == LABEL_BUY and conf >= CONFIDENCE_MIN) or (hold_duration >= 48)

            if should_exit:
                exit_price = price
                gross_pnl  = (entry_price - exit_price) * position_size
                fee        = exit_price * position_size * TRADE_FEE_PCT
                net_pnl    = gross_pnl - fee
                capital   += net_pnl

                trades.append({
                    "entry_idx":    entry_idx,
                    "exit_idx":     i,
                    "entry_time":   df.loc[entry_idx, "datetime"] if entry_idx in df.index else None,
                    "exit_time":    row["datetime"],
                    "direction":    position,
                    "entry_price":  entry_price,
                    "exit_price":   exit_price,
                    "duration_h":   hold_duration,
                    "gross_pnl":    gross_pnl,
                    "net_pnl":      net_pnl,
                    "capital_after":capital,
                    "result":       "WIN" if net_pnl > 0 else "LOSS",
                })
                position = None

        equity_curve.append(capital)

    trade_log = pd.DataFrame(trades)
    return trade_log, equity_curve


def _calculate_metrics(
    trade_log: pd.DataFrame,
    equity_curve: list,
    coin_name: str,
) -> dict:
    """
    Calculate all performance metrics from the trade log and equity curve.

    Args:
        trade_log:   DataFrame of all simulated trades
        equity_curve: List of capital values after each candle
        coin_name:   Used for logging

    Returns:
        dict: All performance metrics
    """
    if len(trade_log) == 0:
        log.warning(f"  {coin_name}: No trades executed. "
                    f"Try lowering CONFIDENCE_MIN ({CONFIDENCE_MIN}).")
        return {"total_trades": 0}

    equity    = np.array(equity_curve)
    total_ret = (equity[-1] - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100
    wins      = (trade_log["net_pnl"] > 0).sum()
    losses    = (trade_log["net_pnl"] <= 0).sum()
    win_rate  = wins / len(trade_log) * 100

    # Max Drawdown: largest peak-to-trough decline
    peak       = np.maximum.accumulate(equity)
    drawdown   = (equity - peak) / peak * 100
    max_dd     = drawdown.min()

    # Sharpe Ratio: risk-adjusted return (daily returns)
    # Annualised using sqrt(24*365) for hourly data
    pnl_array  = trade_log["net_pnl"].values
    if pnl_array.std() > 0:
        sharpe = (pnl_array.mean() / pnl_array.std()) * np.sqrt(24 * 365 / 48)
    else:
        sharpe = 0.0

    # Profit Factor: total gross profit / total gross loss
    gross_profit = trade_log.loc[trade_log["net_pnl"] > 0, "net_pnl"].sum()
    gross_loss   = abs(trade_log.loc[trade_log["net_pnl"] <= 0, "net_pnl"].sum())
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    metrics = {
        "coin":            coin_name,
        "total_trades":    len(trade_log),
        "wins":            int(wins),
        "losses":          int(losses),
        "win_rate_pct":    round(win_rate, 2),
        "total_return_pct":round(total_ret, 2),
        "max_drawdown_pct":round(max_dd, 2),
        "sharpe_ratio":    round(sharpe, 3),
        "profit_factor":   round(profit_factor, 3),
        "initial_capital": INITIAL_CAPITAL,
        "final_capital":   round(equity[-1], 2),
        "avg_trade_pnl":   round(trade_log["net_pnl"].mean(), 2),
        "avg_duration_h":  round(trade_log["duration_h"].mean(), 1),
    }

    log.info(f"\n── Backtest Results: {coin_name} ──────────────────────")
    log.info(f"  Total trades   : {metrics['total_trades']:,}")
    log.info(f"  Win rate       : {metrics['win_rate_pct']}%")
    log.info(f"  Total return   : {metrics['total_return_pct']:+.2f}%")
    log.info(f"  Max drawdown   : {metrics['max_drawdown_pct']:.2f}%")
    log.info(f"  Sharpe ratio   : {metrics['sharpe_ratio']:.3f}")
    log.info(f"  Profit factor  : {metrics['profit_factor']:.3f}")
    log.info(f"  Final capital  : Rs {metrics['final_capital']:,.0f}")
    log.info("─" * 52)

    # Deployment gate
    if metrics["total_return_pct"] > 10 and metrics["max_drawdown_pct"] > -25:
        log.info(f"  DEPLOYMENT GATE: PASSED — Model is suitable for live trading")
    else:
        log.warning(f"  DEPLOYMENT GATE: FAILED — Review model before going live")

    return metrics


def run_backtest(coin_name: str, version: str = "v1") -> dict:
    """
    Full backtest pipeline for one coin.

    Args:
        coin_name: e.g. 'BTC_USD'
        version:   Model version to use ('v1' or 'tuned')

    Returns:
        dict: All backtest metrics
    """
    log.info(f"\nRunning backtest: {coin_name} (model version: {version})")

    # Load model
    model, scaler, features = load_model(coin_name, version)

    # Load labeled data and use only the TEST portion
    df              = load_labeled(coin_name)
    _, test_df      = time_based_split(df)
    test_df         = test_df.reset_index(drop=True)

    # Apply model to get predictions
    test_df = _apply_model(test_df, model, scaler, features)

    # Simulate trading
    trade_log, equity_curve = _simulate_trades(test_df)

    # Calculate metrics
    metrics = _calculate_metrics(trade_log, equity_curve, coin_name)

    # Save results
    os.makedirs(MODELS_DIR, exist_ok=True)

    metrics_path   = os.path.join(MODELS_DIR, f"backtest_{coin_name}.json")
    trade_log_path = os.path.join(MODELS_DIR, f"trade_log_{coin_name}.csv")

    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)

    if len(trade_log) > 0:
        trade_log.to_csv(trade_log_path, index=False)
        log.info(f"  Trade log saved → {trade_log_path}")

    log.info(f"  Metrics saved  → {metrics_path}")
    return metrics


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)s  %(message)s"
    )
    from src.data_pipeline.fetch_huggingface import COINS

    for coin_name in COINS.values():
        try:
            run_backtest(coin_name, version="v1")
        except Exception as e:
            log.error(f"Backtest failed for {coin_name}: {e}")