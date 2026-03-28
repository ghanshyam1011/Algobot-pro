"""
src/models/registry.py
========================
PURPOSE:
    Model registry — tracks all trained model versions, their performance
    metrics, and which version is currently active in production.

WHY THIS EXISTS:
    As you retrain models over time (weekly, monthly), you accumulate
    multiple versions: v1, tuned, v2, v3 etc.

    The registry answers:
    - Which model version is currently live?
    - What was the accuracy of each version?
    - When was each model trained?
    - Should I roll back to the previous version?

    This is standard practice in ML engineering —
    called "Model Registry" or "Model Versioning".

STORAGE:
    models/registry.json — a JSON file tracking all versions

DEPENDENCIES:
    pip install joblib pandas
"""

import os
import json
import logging
import joblib
from datetime import datetime, timezone

from config.settings import MODELS_DIR, COINS, FEATURE_COLUMNS

log = logging.getLogger(__name__)

REGISTRY_PATH = os.path.join(MODELS_DIR, "registry.json")


# ── Registry I/O ──────────────────────────────────────────────────────────────

def _load_registry() -> dict:
    """Load the registry JSON file. Returns empty dict if not found."""
    if not os.path.exists(REGISTRY_PATH):
        return {"models": {}, "active_versions": {}}
    try:
        with open(REGISTRY_PATH) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        log.warning("Registry file corrupted — starting fresh.")
        return {"models": {}, "active_versions": {}}


def _save_registry(registry: dict) -> None:
    """Save the registry to disk."""
    os.makedirs(MODELS_DIR, exist_ok=True)
    with open(REGISTRY_PATH, "w") as f:
        json.dump(registry, f, indent=2, default=str)


# ── Registration ──────────────────────────────────────────────────────────────

def register_model(
    coin_name: str,
    version: str,
    metrics: dict,
    set_active: bool = True,
) -> dict:
    """
    Register a trained model in the registry.
    Called automatically by train.py after every successful training run.

    Args:
        coin_name:  e.g. 'BTC_USD'
        version:    e.g. 'v1', 'tuned', 'v2'
        metrics:    Dict with accuracy, auc_roc etc. from evaluate.py
        set_active: If True, set this version as the active production model

    Returns:
        dict: The registered model entry

    Example:
        >>> from src.models.registry import register_model
        >>> register_model('BTC_USD', 'v1', {'accuracy': 0.612, 'auc_roc': 0.734})
    """
    registry = _load_registry()

    if coin_name not in registry["models"]:
        registry["models"][coin_name] = {}

    model_path  = os.path.join(MODELS_DIR, f"xgb_{coin_name}_{version}.pkl")
    scaler_path = os.path.join(MODELS_DIR, f"scaler_{coin_name}.pkl")

    entry = {
        "coin_name":    coin_name,
        "version":      version,
        "trained_at":   datetime.now(timezone.utc).isoformat(),
        "model_path":   model_path,
        "scaler_path":  scaler_path,
        "feature_count":len(FEATURE_COLUMNS),
        "metrics": {
            "accuracy":  round(metrics.get("accuracy", 0), 4),
            "auc_roc":   round(metrics.get("auc_roc", 0), 4),
            "win_rate":  round(metrics.get("win_rate", 0), 4),
        },
        "files_exist": {
            "model":  os.path.exists(model_path),
            "scaler": os.path.exists(scaler_path),
        },
        "is_active": set_active,
    }

    registry["models"][coin_name][version] = entry

    if set_active:
        # Mark previous active version as inactive
        for v, e in registry["models"][coin_name].items():
            if v != version:
                e["is_active"] = False

        registry["active_versions"][coin_name] = version
        log.info(f"  Registered {coin_name}/{version} as ACTIVE model.")
    else:
        log.info(f"  Registered {coin_name}/{version} (not active).")

    _save_registry(registry)
    return entry


def get_active_version(coin_name: str) -> str:
    """
    Get the currently active model version for a coin.

    Args:
        coin_name: e.g. 'BTC_USD'

    Returns:
        str: Version string e.g. 'v1' or 'tuned'
             Defaults to 'v1' if no registry entry found.

    Example:
        >>> from src.models.registry import get_active_version
        >>> version = get_active_version('BTC_USD')
        >>> model = load_active_model('BTC_USD')
    """
    registry = _load_registry()
    version  = registry.get("active_versions", {}).get(coin_name, "v1")
    return version


def set_active_version(coin_name: str, version: str) -> None:
    """
    Manually set the active model version.
    Use this to roll back to a previous version if the new one performs poorly.

    Args:
        coin_name: e.g. 'BTC_USD'
        version:   e.g. 'v1' (rollback) or 'tuned' (upgrade)

    Example:
        >>> from src.models.registry import set_active_version
        >>> set_active_version('BTC_USD', 'v1')   # rollback
        >>> set_active_version('BTC_USD', 'tuned') # upgrade
    """
    registry = _load_registry()

    if coin_name not in registry["models"]:
        log.error(f"  No models registered for {coin_name}")
        return

    if version not in registry["models"][coin_name]:
        log.error(
            f"  Version '{version}' not registered for {coin_name}.\n"
            f"  Available: {list(registry['models'][coin_name].keys())}"
        )
        return

    # Check model files exist
    entry       = registry["models"][coin_name][version]
    model_path  = entry.get("model_path", "")
    if not os.path.exists(model_path):
        log.error(f"  Model file not found: {model_path}")
        return

    # Update active flags
    for v, e in registry["models"][coin_name].items():
        e["is_active"] = (v == version)

    registry["active_versions"][coin_name] = version
    _save_registry(registry)
    log.info(f"  Active version for {coin_name} set to: {version}")


def load_active_model(coin_name: str):
    """
    Load the currently active model and scaler for a coin.
    This is what generator.py calls every hour.

    Args:
        coin_name: e.g. 'BTC_USD'

    Returns:
        tuple: (model, scaler, feature_names)

    Raises:
        FileNotFoundError: If model files don't exist

    Example:
        >>> from src.models.registry import load_active_model
        >>> model, scaler, features = load_active_model('BTC_USD')
        >>> proba = model.predict_proba(scaler.transform(X))
    """
    version = get_active_version(coin_name)

    model_path  = os.path.join(MODELS_DIR, f"xgb_{coin_name}_{version}.pkl")
    scaler_path = os.path.join(MODELS_DIR, f"scaler_{coin_name}.pkl")
    feat_path   = os.path.join(MODELS_DIR, "feature_names.json")

    for path in [model_path, scaler_path]:
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"Model file not found: {path}\n"
                f"Run pipeline.py --from train to train the model first."
            )

    model  = joblib.load(model_path)
    scaler = joblib.load(scaler_path)

    features = FEATURE_COLUMNS
    if os.path.exists(feat_path):
        with open(feat_path) as f:
            features = json.load(f)

    log.debug(f"Loaded active model: {coin_name}/{version}")
    return model, scaler, features


def list_all_models() -> dict:
    """
    List all registered models with their metrics and status.

    Returns:
        dict: Full registry contents

    Example:
        >>> from src.models.registry import list_all_models
        >>> models = list_all_models()
        >>> for coin, versions in models.items():
        ...     for ver, info in versions.items():
        ...         print(coin, ver, info['metrics']['accuracy'])
    """
    registry = _load_registry()
    return registry.get("models", {})


def print_registry_summary() -> None:
    """Print a human-readable summary of all registered models."""
    registry = _load_registry()
    models   = registry.get("models", {})
    active   = registry.get("active_versions", {})

    if not models:
        print("No models registered yet. Run pipeline.py to train models.")
        return

    print("\n── Model Registry ─────────────────────────────────────────")
    print(f"  {'Coin':<12} {'Version':<10} {'Accuracy':>10} {'AUC':>8} {'Active':>8} {'Trained':>22}")
    print("  " + "─" * 72)

    for coin, versions in models.items():
        for ver, entry in sorted(versions.items()):
            m       = entry.get("metrics", {})
            is_act  = "✓ LIVE" if entry.get("is_active") else ""
            trained = entry.get("trained_at", "")[:16].replace("T", " ")
            print(
                f"  {coin:<12} {ver:<10} "
                f"{m.get('accuracy',0):>10.4f} "
                f"{m.get('auc_roc',0):>8.4f} "
                f"{is_act:>8} "
                f"{trained:>22}"
            )

    print("─" * 74)
    print(f"  Active versions: {active}")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)s  %(message)s"
    )
    print_registry_summary()