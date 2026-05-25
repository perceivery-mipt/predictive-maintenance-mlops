from pathlib import Path

import joblib
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


PROCESSED_DATA_PATH = Path("data/processed/ai4i2020_processed.csv")
MODEL_OUTPUT_PATH = Path("models/baseline_model.joblib")
METRICS_OUTPUT_PATH = Path("models/baseline_metrics.json")

RANDOM_STATE = 42
TEST_SIZE = 0.2

TARGET_COLUMN = "machine_failure"

FEATURE_COLUMNS = [
    "air_temperature_k",
    "process_temperature_k",
    "rotational_speed_rpm",
    "torque_nm",
    "tool_wear_min",
    "machine_type_H",
    "machine_type_L",
    "machine_type_M",
]


def load_processed_data(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"Processed dataset was not found: {path}. "
            "Run `python pipelines/prepare_data.py` first."
        )

    return pd.read_csv(path)


def build_baseline_model() -> Pipeline:
    numeric_features = [
        "air_temperature_k",
        "process_temperature_k",
        "rotational_speed_rpm",
        "torque_nm",
        "tool_wear_min",
    ]

    passthrough_features = [
        "machine_type_H",
        "machine_type_L",
        "machine_type_M",
    ]

    preprocessor = ColumnTransformer(
        transformers=[
            ("numeric", StandardScaler(), numeric_features),
            ("categorical", "passthrough", passthrough_features),
        ]
    )

    classifier = LogisticRegression(
        class_weight="balanced",
        random_state=RANDOM_STATE,
        max_iter=1000,
    )

    model = Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("classifier", classifier),
        ]
    )

    return model


def evaluate_model(model: Pipeline, x_test: pd.DataFrame, y_test: pd.Series) -> dict:
    y_pred = model.predict(x_test)
    y_proba = model.predict_proba(x_test)[:, 1]

    metrics = {
        "recall": recall_score(y_test, y_pred),
        "precision": precision_score(y_test, y_pred),
        "f1": f1_score(y_test, y_pred),
        "roc_auc": roc_auc_score(y_test, y_proba),
    }

    print("Classification report:")
    print(classification_report(y_test, y_pred, digits=4))

    print("Confusion matrix:")
    print(confusion_matrix(y_test, y_pred))

    print("Metrics:")
    for name, value in metrics.items():
        print(f"{name}: {value:.4f}")

    return metrics


def save_artifacts(model: Pipeline, metrics: dict) -> None:
    import json

    MODEL_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    joblib.dump(model, MODEL_OUTPUT_PATH)

    with METRICS_OUTPUT_PATH.open("w", encoding="utf-8") as file:
        json.dump(metrics, file, indent=2)

    print(f"Model saved to: {MODEL_OUTPUT_PATH}")
    print(f"Metrics saved to: {METRICS_OUTPUT_PATH}")


def main() -> None:
    df = load_processed_data(PROCESSED_DATA_PATH)

    x = df[FEATURE_COLUMNS]
    y = df[TARGET_COLUMN]

    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
        stratify=y,
    )

    print(f"Train shape: {x_train.shape}")
    print(f"Test shape: {x_test.shape}")
    print("Train target distribution:")
    print(y_train.value_counts(normalize=True).sort_index())
    print("Test target distribution:")
    print(y_test.value_counts(normalize=True).sort_index())

    model = build_baseline_model()
    model.fit(x_train, y_train)

    metrics = evaluate_model(model, x_test, y_test)
    save_artifacts(model, metrics)


if __name__ == "__main__":
    main()
