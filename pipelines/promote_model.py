from pathlib import Path
import sys

import mlflow
from mlflow.tracking import MlflowClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))


EXPERIMENT_NAME = "predictive-maintenance"
REGISTERED_MODEL_NAME = "predictive-maintenance-model"

MIN_RECALL = 0.80
MIN_F1 = 0.60
MIN_ROC_AUC = 0.85


def get_candidate_runs(client: MlflowClient) -> list:
    experiment = client.get_experiment_by_name(EXPERIMENT_NAME)

    if experiment is None:
        raise ValueError(
            f"Experiment '{EXPERIMENT_NAME}' was not found. "
            "Run `python pipelines/train_mlflow.py` first."
        )

    runs = client.search_runs(
        experiment_ids=[experiment.experiment_id],
        filter_string="",
        order_by=[
            "metrics.recall DESC",
            "metrics.f1 DESC",
            "metrics.roc_auc DESC",
        ],
    )

    return runs


def run_passes_quality_gate(run) -> bool:
    metrics = run.data.metrics

    return (
        metrics.get("recall", 0.0) >= MIN_RECALL
        and metrics.get("f1", 0.0) >= MIN_F1
        and metrics.get("roc_auc", 0.0) >= MIN_ROC_AUC
    )


def find_best_candidate_run(runs):
    passed_runs = [run for run in runs if run_passes_quality_gate(run)]

    if not passed_runs:
        raise ValueError("No MLflow run passed the quality gate.")

    best_run = sorted(
        passed_runs,
        key=lambda run: (
            run.data.metrics.get("recall", 0.0),
            run.data.metrics.get("f1", 0.0),
            run.data.metrics.get("roc_auc", 0.0),
        ),
        reverse=True,
    )[0]

    return best_run


def find_model_version_by_run_id(
    client: MlflowClient,
    model_name: str,
    run_id: str,
):
    versions = client.search_model_versions(f"name='{model_name}'")

    matching_versions = [
        version for version in versions
        if version.run_id == run_id
    ]

    if not matching_versions:
        raise ValueError(
            f"No registered model version found for run_id={run_id} "
            f"and model_name={model_name}."
        )

    return sorted(
        matching_versions,
        key=lambda version: int(version.version),
        reverse=True,
    )[0]


def promote_model_version(
    client: MlflowClient,
    model_name: str,
    version: str,
) -> None:
    client.set_registered_model_alias(
        name=model_name,
        alias="champion",
        version=version,
    )

    client.set_model_version_tag(
        name=model_name,
        version=version,
        key="deployment_status",
        value="champion",
    )

    client.set_model_version_tag(
        name=model_name,
        version=version,
        key="promotion_reason",
        value="passed_quality_gate",
    )


def main() -> None:
    client = MlflowClient()

    runs = get_candidate_runs(client)
    best_run = find_best_candidate_run(runs)

    best_version = find_model_version_by_run_id(
        client=client,
        model_name=REGISTERED_MODEL_NAME,
        run_id=best_run.info.run_id,
    )

    promote_model_version(
        client=client,
        model_name=REGISTERED_MODEL_NAME,
        version=best_version.version,
    )

    print("Model promotion completed.")
    print(f"Model name: {REGISTERED_MODEL_NAME}")
    print(f"Champion version: {best_version.version}")
    print(f"Run ID: {best_run.info.run_id}")
    print("Metrics:")
    for metric_name in ["recall", "precision", "f1", "roc_auc"]:
        print(f"  {metric_name}: {best_run.data.metrics.get(metric_name):.6f}")


if __name__ == "__main__":
    main()
