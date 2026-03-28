"""
src/models/evaluate.py
========================
PURPOSE:
    Standalone model evaluation module.
    Produces a detailed performance report for a trained model
    beyond what train.py shows — including feature importance,
    SHAP values, and per-class metrics.

WHY SEPARATE FROM train.py?
    train.py evaluates the model immediately after training.
    evaluate.py can be run ANY TIME on an ALREADY TRAINED model
    to get deeper analysis, compare versions, or prepare reports.

OUTPUTS:
    - Confusion matrix
    - Per-class precision / recall / F1
    - AUC-ROC (macro)
    - Top 15 most important features (from XGBoost)
    - SHAP summary (optional — requires shap library)
    - Saves report to models/evaluation_{coin}.json

DEPENDENCIES:
    pip install xgboost scikit-learn joblib pandas numpy
    pip install shap  (optional — for SHAP analysis)
"""

import os
import json
import logging
import joblib
import numpy as np
import pandas as pd

from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    roc_auc_score,
)

from config.settings import (
    FEATURE_COLUMNS,
    MODELS_DIR,
    LABELS_DIR,
    LABEL_NAMES,
    TRAIN_RATIO,
)

log = logging.getLogger(__name__)


def load_model_and_scaler(coin_name: str, version: str = "v1"):
    """
    Load trained model and scaler from disk.

    Args:
        coin_name: e.g. 'BTC_USD'
        version:   'v1' or 'tuned'

    Returns:
        tuple: (model, scaler)
    """
    model_path  = os.path.join(MODELS_DIR, f"xgb_{coin_name}_{version}.pkl")
    scaler_path = os.path.join(MODELS_DIR, f"scaler_{coin_name}.pkl")

    for p in [model_path, scaler_path]:
        if not os.path.exists(p):
            raise FileNotFoundError(
                f"Model file not found: {p}\n"
                f"Run pipeline.py --from train first."
            )

    model  = joblib.load(model_path)
    scaler = joblib.load(scaler_path)
    return model, scaler


def evaluate_model(
    coin_name: str,
    version: str = "v1",
    show_shap: bool = False,
) -> dict:
    """
    Full evaluation of a trained model on its test set.

    Args:
        coin_name:  e.g. 'BTC_USD'
        version:    Model version string
        show_shap:  If True, compute SHAP values (slower, needs shap library)

    Returns:
        dict: Complete evaluation report saved to models/evaluation_{coin}.json

    Example:
        >>> from src.models.evaluate import evaluate_model
        >>> report = evaluate_model('BTC_USD')
        >>> print(f"Accuracy: {report['accuracy']:.2%}")
    """
    log.info(f"\nEvaluating {coin_name} (version={version}) ...")

    # ── Load model + data ─────────────────────────────────────────────────────
    model, scaler = load_model_and_scaler(coin_name, version)

    labeled_path = os.path.join(LABELS_DIR, f"{coin_name}_labeled.csv")
    if not os.path.exists(labeled_path):
        raise FileNotFoundError(
            f"Labeled data not found: {labeled_path}\n"
            f"Run pipeline.py --from label first."
        )

    df = pd.read_csv(labeled_path, parse_dates=["datetime"])

    # ── Time-based test split (same as train.py) ──────────────────────────────
    split    = int(len(df) * TRAIN_RATIO)
    test_df  = df.iloc[split:].copy()

    missing = [c for c in FEATURE_COLUMNS if c not in test_df.columns]
    if missing:
        raise KeyError(f"Missing feature columns: {missing}")

    X_test  = scaler.transform(test_df[FEATURE_COLUMNS].values)
    y_test  = test_df["label"].values.astype(int)

    # ── Predictions ───────────────────────────────────────────────────────────
    y_pred  = model.predict(X_test)
    y_proba = model.predict_proba(X_test)   # shape (n, 3)

    # ── Core metrics ─────────────────────────────────────────────────────────
    accuracy = accuracy_score(y_test, y_pred)
    cm       = confusion_matrix(y_test, y_pred)

    try:
        auc = roc_auc_score(
            y_test, y_proba, multi_class="ovr", average="macro"
        )
    except Exception:
        auc = 0.0

    report_dict = classification_report(
        y_test, y_pred,
        target_names=["BUY", "SELL", "HOLD"],
        zero_division=0,
        output_dict=True,
    )

    # ── Feature importance (top 15) ───────────────────────────────────────────
    importances = model.feature_importances_
    feat_imp = sorted(
        zip(FEATURE_COLUMNS, importances),
        key=lambda x: x[1],
        reverse=True,
    )[:15]

    # ── Confidence distribution ───────────────────────────────────────────────
    max_proba   = y_proba.max(axis=1)
    conf_dist   = {
        "mean":     float(max_proba.mean()),
        "median":   float(np.median(max_proba)),
        "pct_75":   float(np.percentile(max_proba, 75)),
        "pct_90":   float(np.percentile(max_proba, 90)),
        "above_75": float((max_proba >= 0.75).mean() * 100),
        "above_85": float((max_proba >= 0.85).mean() * 100),
    }

    # ── Log full report ───────────────────────────────────────────────────────
    log.info(f"\n{'─'*52}")
    log.info(f"  Evaluation Report: {coin_name} ({version})")
    log.info(f"{'─'*52}")
    log.info(f"  Test set     : {len(test_df):,} rows")
    log.info(f"  Accuracy     : {accuracy:.4f}  ({accuracy*100:.2f}%)")
    log.info(f"  AUC-ROC      : {auc:.4f}")
    log.info(f"\n  Per-class metrics:")
    for cls in ["BUY", "SELL", "HOLD"]:
        m = report_dict.get(cls, {})
        log.info(
            f"    {cls:4s}  precision={m.get('precision',0):.3f}  "
            f"recall={m.get('recall',0):.3f}  "
            f"f1={m.get('f1-score',0):.3f}  "
            f"support={int(m.get('support',0)):,}"
        )

    log.info(f"\n  Confusion Matrix (rows=actual, cols=predicted):")
    log.info(f"             BUY    SELL   HOLD")
    label_order = [0, 1, 2]
    for i in label_order:
        if i < len(cm):
            row_label = LABEL_NAMES.get(i, str(i))
            log.info(f"  {row_label:4s}    " +
                     "  ".join(f"{cm[i][j]:6,}" for j in range(len(cm[i]))))

    log.info(f"\n  Top 10 most important features:")
    for feat, imp in feat_imp[:10]:
        bar = "█" * int(imp * 200)
        log.info(f"    {feat:<25} {imp:.4f}  {bar}")

    log.info(f"\n  Confidence distribution (of all predictions):")
    log.info(f"    Mean confidence  : {conf_dist['mean']:.1%}")
    log.info(f"    Above 75% conf   : {conf_dist['above_75']:.1f}% of predictions")
    log.info(f"    Above 85% conf   : {conf_dist['above_85']:.1f}% of predictions")
    log.info(f"{'─'*52}")

    # ── SHAP analysis (optional) ──────────────────────────────────────────────
    shap_values = None
    if show_shap:
        try:
            import shap
            log.info("\n  Computing SHAP values (this may take a minute) ...")
            explainer   = shap.TreeExplainer(model)
            shap_values = explainer.shap_values(X_test[:500])   # Use 500 rows
            log.info("  SHAP values computed successfully.")
        except ImportError:
            log.warning("  shap library not installed. Run: pip install shap")
        except Exception as e:
            log.warning(f"  SHAP computation failed: {e}")

    # ── Build and save report ─────────────────────────────────────────────────
    evaluation = {
        "coin":          coin_name,
        "version":       version,
        "test_rows":     len(test_df),
        "accuracy":      round(accuracy, 4),
        "auc_roc":       round(auc, 4),
        "confusion_matrix": cm.tolist(),
        "per_class": {
            cls: {
                "precision": round(report_dict.get(cls, {}).get("precision", 0), 4),
                "recall":    round(report_dict.get(cls, {}).get("recall", 0), 4),
                "f1":        round(report_dict.get(cls, {}).get("f1-score", 0), 4),
                "support":   int(report_dict.get(cls, {}).get("support", 0)),
            }
            for cls in ["BUY", "SELL", "HOLD"]
        },
        "top_features": [
            {"feature": feat, "importance": round(float(imp), 6)}
            for feat, imp in feat_imp
        ],
        "confidence_distribution": conf_dist,
        "deployment_ready": (
            accuracy >= 0.55 and
            auc      >= 0.60 and
            conf_dist["above_75"] >= 20.0
        ),
    }

    out_path = os.path.join(MODELS_DIR, f"evaluation_{coin_name}.json")
    with open(out_path, "w") as f:
        json.dump(evaluation, f, indent=2)
    log.info(f"\n  Report saved → {out_path}")

    return evaluation


def compare_versions(coin_name: str) -> None:
    """
    Compare v1 vs tuned model performance side by side.
    Prints a comparison table.

    Args:
        coin_name: e.g. 'BTC_USD'
    """
    results = {}
    for version in ["v1", "tuned"]:
        path = os.path.join(MODELS_DIR, f"xgb_{coin_name}_{version}.pkl")
        if not os.path.exists(path):
            log.warning(f"  {version} model not found for {coin_name}")
            continue
        try:
            results[version] = evaluate_model(coin_name, version)
        except Exception as e:
            log.error(f"  Failed to evaluate {version}: {e}")

    if len(results) < 2:
        log.info("  Need both v1 and tuned models to compare.")
        return

    print(f"\n── Version Comparison: {coin_name} ────────────────")
    print(f"  {'Metric':<20} {'v1':>10} {'tuned':>10} {'Delta':>10}")
    print("  " + "─" * 52)

    metrics = ["accuracy", "auc_roc"]
    for m in metrics:
        v1  = results["v1"].get(m, 0)
        tun = results["tuned"].get(m, 0)
        d   = tun - v1
        print(f"  {m:<20} {v1:>10.4f} {tun:>10.4f} {d:>+10.4f}")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)s  %(message)s"
    )
    from config.settings import COINS

    for coin_name in COINS.values():
        try:
            evaluate_model(coin_name, version="v1")
        except Exception as e:
            log.error(f"  Failed for {coin_name}: {e}")