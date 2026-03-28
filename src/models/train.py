"""
src/models/train.py
====================
PURPOSE:
    Train the XGBoost classifier on labeled feature data and save the
    trained model to the models/ directory.

WHAT IT DOES:
    1. Loads labeled data from data/labels/
    2. Splits into train (80%) and test (20%) sets — time-based split
       (NOT random, because time order matters in trading)
    3. Handles class imbalance via sample_weight
    4. Trains XGBoost classifier
    5. Evaluates: Accuracy, AUC-ROC, F1, Confusion Matrix
    6. Saves the model (.pkl) and scaler (.pkl) to models/

WHY TIME-BASED SPLIT (not random)?
    If we split randomly, future data leaks into training.
    e.g. a row from Jan 2024 ends up in train, and Jan 2023 in test.
    The model would already "know" future patterns. This gives falsely
    high accuracy. In real trading, we always train on the past and
    test on the future — never the other way.

INPUT:  data/labels/BTC_USD_labeled.csv
OUTPUT: models/xgb_BTC_USD_v1.pkl
        models/scaler_BTC_USD.pkl
        models/feature_names.json

DEPENDENCIES:
    pip install xgboost scikit-learn pandas numpy joblib
"""

import os
import sys
import json
import logging
import joblib
import numpy as np
import pandas as pd
from pathlib import Path

# Add repo root to path so absolute imports work when run directly
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    roc_auc_score,
)
from sklearn.utils.class_weight import compute_sample_weight
from xgboost import XGBClassifier

from src.features.labeler import load_labeled, LABEL_NAMES
from src.features.engineer import ENGINEERED_FEATURE_COLUMNS

log = logging.getLogger(__name__)

MODELS_DIR   = "models"
TRAIN_RATIO  = 0.80   # 80% of data for training, 20% for testing

# XGBoost default hyperparameters (will be improved by tune.py)
DEFAULT_PARAMS = {
    "n_estimators":      300,
    "max_depth":         6,
    "learning_rate":     0.05,
    "subsample":         0.8,
    "colsample_bytree":  0.8,
    "min_child_weight":  5,
    "gamma":             0.1,
    "reg_alpha":         0.1,
    "reg_lambda":        1.0,
    "objective":         "multi:softprob",
    "num_class":         3,          # BUY, SELL, HOLD
    "eval_metric":       "mlogloss",
    "random_state":      42,
    "n_jobs":            -1,         # Use all CPU cores
    "verbosity":         0,
}


def time_based_split(
    df: pd.DataFrame,
    train_ratio: float = TRAIN_RATIO
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Split DataFrame into train and test sets based on time order.

    First train_ratio% of rows → training set
    Last  (1-train_ratio)% of rows → test set

    Args:
        df:          Labeled DataFrame sorted by datetime (oldest first)
        train_ratio: Fraction of data to use for training

    Returns:
        tuple: (train_df, test_df)
    """
    split_idx = int(len(df) * train_ratio)
    train_df  = df.iloc[:split_idx].copy()
    test_df   = df.iloc[split_idx:].copy()

    log.info(f"  Train set: {len(train_df):,} rows  "
             f"({train_df['datetime'].min().date()} → {train_df['datetime'].max().date()})")
    log.info(f"  Test  set: {len(test_df):,} rows  "
             f"({test_df['datetime'].min().date()} → {test_df['datetime'].max().date()})")

    return train_df, test_df


def prepare_X_y(
    df: pd.DataFrame,
    scaler: StandardScaler = None,
    fit_scaler: bool = False,
) -> tuple[np.ndarray, np.ndarray, StandardScaler]:
    """
    Extract feature matrix X and label vector y from DataFrame.
    Optionally fit or apply a StandardScaler.

    Args:
        df:          Labeled DataFrame with all feature columns + 'label'
        scaler:      Existing scaler (for test set — apply but do not refit)
        fit_scaler:  If True, fit a new scaler on this data (for train set only)

    Returns:
        tuple: (X array, y array, fitted/applied scaler)
    """
    X = df[ENGINEERED_FEATURE_COLUMNS].values
    y = df["label"].values.astype(int)

    if fit_scaler:
        scaler = StandardScaler()
        X = scaler.fit_transform(X)
        log.info(f"  Scaler fitted on training data.")
    elif scaler is not None:
        X = scaler.transform(X)
    else:
        log.warning("  No scaler provided and fit_scaler=False — using raw features.")

    return X, y, scaler


def train_model(
    X_train: np.ndarray,
    y_train: np.ndarray,
    params: dict = None,
    X_val: np.ndarray = None,
    y_val: np.ndarray = None,
) -> XGBClassifier:
    """
    Train XGBoost classifier with sample weights to handle class imbalance.

    Args:
        X_train: Feature matrix (scaled)
        y_train: Label vector
        params:  XGBoost hyperparameters (uses DEFAULT_PARAMS if None)
        X_val:   Validation features (for early stopping)
        y_val:   Validation labels   (for early stopping)

    Returns:
        XGBClassifier: Trained model
    """
    if params is None:
        params = DEFAULT_PARAMS.copy()

    # Compute sample weights so all 3 classes are treated equally
    # This prevents the model from always predicting HOLD (the majority class)
    sample_weights = compute_sample_weight(class_weight="balanced", y=y_train)

    model = XGBClassifier(**params)

    if X_val is not None and y_val is not None:
        model.fit(
            X_train, y_train,
            sample_weight=sample_weights,
            eval_set=[(X_val, y_val)],
            verbose=False,
        )
    else:
        model.fit(X_train, y_train, sample_weight=sample_weights)

    log.info(f"  Model trained: {params['n_estimators']} trees, depth={params['max_depth']}")
    return model


def evaluate_model(
    model: XGBClassifier,
    X_test: np.ndarray,
    y_test: np.ndarray,
    coin_name: str,
) -> dict:
    """
    Evaluate model performance and log key metrics.

    Args:
        model:     Trained XGBClassifier
        X_test:    Test feature matrix (scaled)
        y_test:    True labels
        coin_name: Used for logging

    Returns:
        dict: All evaluation metrics
    """
    y_pred       = model.predict(X_test)
    y_pred_proba = model.predict_proba(X_test)

    accuracy = accuracy_score(y_test, y_pred)
    cm       = confusion_matrix(y_test, y_pred)
    report   = classification_report(
        y_test, y_pred,
        target_names=[LABEL_NAMES[i] for i in sorted(LABEL_NAMES)],
        output_dict=True,
    )

    # AUC-ROC (multiclass — one-vs-rest)
    try:
        auc = roc_auc_score(y_test, y_pred_proba, multi_class="ovr", average="macro")
    except Exception:
        auc = 0.0

    log.info(f"\n── Evaluation: {coin_name} ──────────────────────────")
    log.info(f"  Accuracy  : {accuracy:.4f}  ({accuracy*100:.2f}%)")
    log.info(f"  AUC-ROC   : {auc:.4f}")
    log.info(f"\n  Confusion Matrix (rows=actual, cols=predicted):")
    log.info(f"             BUY    SELL   HOLD")
    for i, row in enumerate(cm):
        log.info(f"  {LABEL_NAMES[i]:4s}    {row[0]:6,} {row[1]:6,} {row[2]:6,}")
    log.info(f"\n  Classification Report:")
    for cls in ["BUY", "SELL", "HOLD"]:
        m = report.get(cls, {})
        log.info(
            f"  {cls:4s}  precision={m.get('precision',0):.3f}  "
            f"recall={m.get('recall',0):.3f}  "
            f"f1={m.get('f1-score',0):.3f}  "
            f"support={int(m.get('support',0)):,}"
        )
    log.info("─" * 52)

    if accuracy < 0.55:
        log.warning(
            f"  Accuracy {accuracy:.2%} is below 55% baseline. "
            f"Consider running tune.py for hyperparameter optimisation."
        )

    return {
        "accuracy": accuracy,
        "auc_roc":  auc,
        "confusion_matrix": cm.tolist(),
        "classification_report": report,
    }


def save_model(
    model: XGBClassifier,
    scaler: StandardScaler,
    coin_name: str,
    version: str = "v1",
) -> dict:
    """
    Save trained model, scaler, and feature list to disk.

    Args:
        model:     Trained XGBClassifier
        scaler:    Fitted StandardScaler
        coin_name: e.g. 'BTC_USD'
        version:   Version tag for the file e.g. 'v1'

    Returns:
        dict: Paths of all saved files
    """
    os.makedirs(MODELS_DIR, exist_ok=True)

    model_path   = os.path.join(MODELS_DIR, f"xgb_{coin_name}_{version}.pkl")
    scaler_path  = os.path.join(MODELS_DIR, f"scaler_{coin_name}.pkl")
    feature_path = os.path.join(MODELS_DIR, "feature_names.json")

    joblib.dump(model,  model_path)
    joblib.dump(scaler, scaler_path)

    with open(feature_path, "w") as f:
        json.dump(ENGINEERED_FEATURE_COLUMNS, f, indent=2)

    log.info(f"\n  Model  saved → {model_path}")
    log.info(f"  Scaler saved → {scaler_path}")
    log.info(f"  Features     → {feature_path}")

    return {
        "model_path":   model_path,
        "scaler_path":  scaler_path,
        "feature_path": feature_path,
    }


def train_pipeline(
    coin_name: str,
    params: dict = None,
    version: str = "v1",
) -> dict:
    """
    Full training pipeline for one coin.

    Steps:
        1. Load labeled data
        2. Time-based train/test split
        3. Scale features
        4. Train XGBoost
        5. Evaluate
        6. Save model + scaler

    Args:
        coin_name: e.g. 'BTC_USD'
        params:    XGBoost hyperparameters (uses defaults if None)
        version:   Model version string for filename

    Returns:
        dict: Evaluation metrics + saved file paths

    Example:
        >>> from src.models.train import train_pipeline
        >>> results = train_pipeline('BTC_USD')
        >>> print(f"Accuracy: {results['accuracy']:.2%}")
    """
    log.info(f"\n{'='*55}")
    log.info(f"Training pipeline: {coin_name}")
    log.info(f"{'='*55}")

    # 1. Load labeled data
    df = load_labeled(coin_name)
    log.info(f"  Loaded {len(df):,} labeled rows")

    # 2. Time-based split
    train_df, test_df = time_based_split(df)

    # 3. Scale features (fit on train, apply to test)
    X_train, y_train, scaler = prepare_X_y(train_df, fit_scaler=True)
    X_test,  y_test,  _      = prepare_X_y(test_df,  scaler=scaler, fit_scaler=False)

    # 4. Train
    model = train_model(X_train, y_train, params=params, X_val=X_test, y_val=y_test)

    # 5. Evaluate
    metrics = evaluate_model(model, X_test, y_test, coin_name)

    # 6. Save
    paths = save_model(model, scaler, coin_name, version)

    return {**metrics, **paths}


def load_model(coin_name: str, version: str = "v1") -> tuple:
    """
    Load a trained model and scaler from disk.
    Used by generator.py (live signal generation).

    Args:
        coin_name: e.g. 'BTC_USD'
        version:   Model version string

    Returns:
        tuple: (XGBClassifier, StandardScaler, feature_names list)
    """
    model_path  = os.path.join(MODELS_DIR, f"xgb_{coin_name}_{version}.pkl")
    scaler_path = os.path.join(MODELS_DIR, f"scaler_{coin_name}.pkl")
    feat_path   = os.path.join(MODELS_DIR, "feature_names.json")

    for path in [model_path, scaler_path, feat_path]:
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"Model file not found: {path}\n"
                f"Run train_pipeline('{coin_name}') first."
            )

    model    = joblib.load(model_path)
    scaler   = joblib.load(scaler_path)
    with open(feat_path) as f:
        features = json.load(f)

    log.info(f"Model loaded: {model_path}")
    return model, scaler, features


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)s  %(message)s"
    )

    from src.data_pipeline.fetch_huggingface import COINS

    all_results = {}
    for coin_name in COINS.values():
        try:
            result = train_pipeline(coin_name)
            all_results[coin_name] = result
        except Exception as e:
            log.error(f"Training failed for {coin_name}: {e}")

    print("\n── Training Summary ───────────────────────────────")
    for coin, res in all_results.items():
        print(f"  {coin}: accuracy={res['accuracy']:.2%}  auc={res['auc_roc']:.4f}")