"""
src/models/tune.py
===================
PURPOSE:
    Use Optuna to automatically find the best XGBoost hyperparameters
    for each coin. Improves model accuracy from ~58% to ~63%+.

WHAT IS OPTUNA?
    Optuna is a hyperparameter search library. Instead of manually trying
    100 different combinations, Optuna intelligently searches the parameter
    space and finds the best combination in fewer trials using Bayesian optimisation.

HOW LONG DOES IT TAKE?
    Default: 50 trials × ~30s each = ~25 minutes per coin.
    You only need to run this once. The best params are saved and reused.

INPUT:  data/labels/BTC_USD_labeled.csv
OUTPUT: models/best_params_BTC_USD.json  (best hyperparameters found)
        models/xgb_BTC_USD_tuned.pkl     (retrained model with best params)

HOW TO RUN:
    python src/models/tune.py

DEPENDENCIES:
    pip install optuna xgboost scikit-learn pandas numpy joblib
"""

import os
import sys
import json
import logging
import numpy as np
import optuna
from pathlib import Path
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.utils.class_weight import compute_sample_weight
from xgboost import XGBClassifier

# Add repo root to path so absolute imports work when run directly
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.features.labeler import load_labeled
from src.features.engineer import ENGINEERED_FEATURE_COLUMNS
from src.models.train import (
    time_based_split,
    prepare_X_y,
    train_pipeline,
    MODELS_DIR,
)

log = logging.getLogger(__name__)

N_TRIALS    = 50   # Number of Optuna trials (increase for better results, takes longer)
CV_FOLDS    = 3    # Cross-validation folds (used inside each trial for robust evaluation)
RANDOM_SEED = 42

# Suppress verbose Optuna output
optuna.logging.set_verbosity(optuna.logging.WARNING)


def objective(trial: optuna.Trial, X_train: np.ndarray, y_train: np.ndarray) -> float:
    """
    Optuna objective function — defines the search space and returns the score.

    Optuna calls this function N_TRIALS times with different parameter combinations.
    Each time, it trains XGBoost and returns the cross-validated accuracy.
    Optuna learns from each result to pick better parameters next time.

    Args:
        trial:   Optuna Trial object — used to suggest parameter values
        X_train: Scaled training features
        y_train: Training labels

    Returns:
        float: Mean cross-validated accuracy (Optuna maximises this)
    """
    # Define the parameter search space
    params = {
        "n_estimators":     trial.suggest_int("n_estimators", 100, 600),
        "max_depth":        trial.suggest_int("max_depth", 3, 10),
        "learning_rate":    trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
        "subsample":        trial.suggest_float("subsample", 0.5, 1.0),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
        "min_child_weight": trial.suggest_int("min_child_weight", 1, 20),
        "gamma":            trial.suggest_float("gamma", 0.0, 1.0),
        "reg_alpha":        trial.suggest_float("reg_alpha", 0.0, 2.0),
        "reg_lambda":       trial.suggest_float("reg_lambda", 0.5, 3.0),
        "objective":        "multi:softprob",
        "num_class":        3,
        "eval_metric":      "mlogloss",
        "random_state":     RANDOM_SEED,
        "n_jobs":           -1,
        "verbosity":        0,
    }

    model          = XGBClassifier(**params)
    sample_weights = compute_sample_weight(class_weight="balanced", y=y_train)

    # 3-fold cross-validation — more robust than a single train/test split
    cv     = StratifiedKFold(n_splits=CV_FOLDS, shuffle=False)
    scores = cross_val_score(
        model, X_train, y_train,
        cv=cv,
        scoring="accuracy",
        fit_params={"sample_weight": sample_weights},
    )

    return scores.mean()


def tune_coin(coin_name: str, n_trials: int = N_TRIALS) -> dict:
    """
    Run Optuna hyperparameter search for one coin.

    Args:
        coin_name: e.g. 'BTC_USD'
        n_trials:  Number of search trials

    Returns:
        dict: Best hyperparameters found

    Example:
        >>> from src.models.tune import tune_coin
        >>> best_params = tune_coin('BTC_USD', n_trials=30)
        >>> print(best_params)
    """
    log.info(f"\nRunning Optuna tuning for {coin_name} ({n_trials} trials) ...")
    log.info(f"This will take approximately {n_trials * 0.5:.0f}–{n_trials * 1:.0f} minutes.")

    df              = load_labeled(coin_name)
    train_df, _     = time_based_split(df)
    X_train, y_train, _ = prepare_X_y(train_df, fit_scaler=True)

    # Create study and run optimisation
    study = optuna.create_study(
        direction="maximize",
        sampler=optuna.samplers.TPESampler(seed=RANDOM_SEED),
    )
    study.optimize(
        lambda trial: objective(trial, X_train, y_train),
        n_trials=n_trials,
        show_progress_bar=True,
    )

    best_params = study.best_params
    best_score  = study.best_value

    log.info(f"\n  Best CV accuracy: {best_score:.4f} ({best_score*100:.2f}%)")
    log.info(f"  Best parameters:")
    for k, v in best_params.items():
        log.info(f"    {k}: {v}")

    # Add fixed parameters back in (not searched by Optuna)
    best_params.update({
        "objective":    "multi:softprob",
        "num_class":    3,
        "eval_metric":  "mlogloss",
        "random_state": RANDOM_SEED,
        "n_jobs":       -1,
        "verbosity":    0,
    })

    # Save best params to JSON
    os.makedirs(MODELS_DIR, exist_ok=True)
    params_path = os.path.join(MODELS_DIR, f"best_params_{coin_name}.json")
    with open(params_path, "w") as f:
        json.dump(best_params, f, indent=2)
    log.info(f"  Best params saved → {params_path}")

    # Retrain final model with best params and save as 'tuned' version
    log.info(f"\n  Retraining final model with best params ...")
    results = train_pipeline(coin_name, params=best_params, version="tuned")

    log.info(f"  Final tuned model accuracy: {results['accuracy']:.4f}")

    return best_params


def load_best_params(coin_name: str) -> dict:
    """
    Load saved best hyperparameters for a coin.

    Args:
        coin_name: e.g. 'BTC_USD'

    Returns:
        dict: Best XGBoost hyperparameters
    """
    path = os.path.join(MODELS_DIR, f"best_params_{coin_name}.json")
    if not os.path.exists(path):
        log.warning(f"No tuned params found for {coin_name}. Using defaults.")
        return None
    with open(path) as f:
        return json.load(f)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)s  %(message)s"
    )
    from src.data_pipeline.fetch_huggingface import COINS

    for coin_name in COINS.values():
        try:
            tune_coin(coin_name, n_trials=N_TRIALS)
        except Exception as e:
            log.error(f"Tuning failed for {coin_name}: {e}")