from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

import mlflow
import mlflow.sklearn
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

from src.quality_gate import evaluate_quality_gate


PROCESSED_DATA_PATH = Path("data/processed/ai4i2020_processed.csv")

RANDOM_STATE = 42
TEST_SIZE = 0.2

EXPERIMENT_NAME = "predictive-maintenance"
REGISTERED_MODEL_NAME = "predictive-maintenance-model"

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


def build_logistic_regression_model() -> Pipeline:
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

    return Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("classifier", classifier),
        ]
    )


def build_random_forest_model() -> Pipeline:
    classifier = RandomForestClassifier(
        n_estimators=300,
        max_depth=8,
        min_samples_leaf=5,
        class_weight="balanced",
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )

    return Pipeline(
        steps=[
            ("classifier", classifier),
        ]
    )


def evaluate_model(model: Pipeline, x_test: pd.DataFrame, y_test: pd.Series) -> dict:
    y_pred = model.predict(x_test)
    y_proba = model.predict_proba(x_test)[:, 1]

    metrics = {
        "recall": recall_score(y_test, y_pred),
        "precision": precision_score(y_test, y_pred),
        "f1": f1_score(y_test, y_pred),
        "roc_auc": roc_auc_score(y_test, y_proba),
    }

    report = classification_report(y_test, y_pred, digits=4)
    matrix = confusion_matrix(y_test, y_pred)

    print("Classification report:")
    print(report)

    print("Confusion matrix:")
    print(matrix)

    print("Metrics:")
    for name, value in metrics.items():
        print(f"{name}: {value:.4f}")

    metrics["true_negative"] = int(matrix[0, 0])
    metrics["false_positive"] = int(matrix[0, 1])
    metrics["false_negative"] = int(matrix[1, 0])
    metrics["true_positive"] = int(matrix[1, 1])

    return metrics


def train_and_log_model(
    model_name: str,
    model: Pipeline,
    x_train: pd.DataFrame,
    x_test: pd.DataFrame,
    y_train: pd.Series,
    y_test: pd.Series,
) -> dict:
    with mlflow.start_run(run_name=model_name):
        model.fit(x_train, y_train)
        metrics = evaluate_model(model, x_test, y_test)

        mlflow.log_param("model_type", model_name)
        mlflow.log_param("random_state", RANDOM_STATE)
        mlflow.log_param("test_size", TEST_SIZE)
        mlflow.log_param("target_column", TARGET_COLUMN)
        mlflow.log_param("feature_columns", ",".join(FEATURE_COLUMNS))
        mlflow.log_param("train_rows", len(x_train))
        mlflow.log_param("test_rows", len(x_test))

        for metric_name, metric_value in metrics.items():
            mlflow.log_metric(metric_name, metric_value)

        mlflow.sklearn.log_model(
            sk_model=model,
            artifact_path="model",
            registered_model_name=REGISTERED_MODEL_NAME,
        )

        run_id = mlflow.active_run().info.run_id
        metrics["run_id"] = run_id
        metrics["model_name"] = model_name

        print(f"MLflow run_id: {run_id}")

        return metrics


def main() -> None:
    mlflow.set_experiment(EXPERIMENT_NAME)

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

    candidates = {
        "logistic_regression_balanced": build_logistic_regression_model(),
        "random_forest_balanced": build_random_forest_model(),
    }

    results = []

    for candidate_name, candidate_model in candidates.items():
        print("=" * 80)
        print(f"Training candidate: {candidate_name}")
        metrics = train_and_log_model(
            model_name=candidate_name,
            model=candidate_model,
            x_train=x_train,
            x_test=x_test,
            y_train=y_train,
            y_test=y_test,
        )
        results.append(metrics)

    results_df = pd.DataFrame(results)

    print("=" * 80)
    print("Candidate comparison:")
    print(
        results_df[
            [
                "model_name",
                "recall",
                "precision",
                "f1",
                "roc_auc",
                "false_negative",
                "run_id",
            ]
        ]
    )

    quality_gate_results = []

    for _, row in results_df.iterrows():
        gate_result = evaluate_quality_gate(row.to_dict())
        quality_gate_results.append(gate_result.passed)

        print("=" * 80)
        print(f"Quality gate result for {row['model_name']}:")
        print(f"passed: {gate_result.passed}")

        if gate_result.passed_checks:
            print("passed checks:")
            for check in gate_result.passed_checks:
                print(f"  - {check}")

        if gate_result.failed_checks:
            print("failed checks:")
            for check in gate_result.failed_checks:
                print(f"  - {check}")

    results_df["quality_gate_passed"] = quality_gate_results

    passed_candidates = results_df[results_df["quality_gate_passed"]].copy()

    if passed_candidates.empty:
        print("=" * 80)
        print("No candidate passed the quality gate.")
        best_model = results_df.sort_values(
            by=["recall", "f1", "roc_auc"],
            ascending=False,
        ).iloc[0]
        print("Best rejected candidate:")
    else:
        print("=" * 80)
        best_model = passed_candidates.sort_values(
            by=["recall", "f1", "roc_auc"],
            ascending=False,
        ).iloc[0]
        print("Best candidate that passed the quality gate:")

    print(
        best_model[
            [
                "model_name",
                "recall",
                "precision",
                "f1",
                "roc_auc",
                "quality_gate_passed",
                "run_id",
            ]
        ]
    )


if __name__ == "__main__":
    main()
