from __future__ import annotations

from datetime import datetime

from airflow import DAG
from airflow.operators.bash import BashOperator


PROJECT_DIR = "/opt/airflow/project"

COMMON_ENV = {
    "MLFLOW_TRACKING_URI": "http://mlflow:5000",
    "FEAST_REDIS_CONNECTION_STRING": "redis:6379",
}


with DAG(
    dag_id="predictive_maintenance_training_pipeline",
    description="End-to-end ML pipeline: data preparation, Feast materialization, training and promotion.",
    start_date=datetime(2026, 1, 1),
    schedule=None,
    catchup=False,
    tags=["mlops", "predictive-maintenance", "level-2"],
) as dag:
    download_data = BashOperator(
        task_id="download_data",
        bash_command="python pipelines/download_data.py",
        cwd=PROJECT_DIR,
        env=COMMON_ENV,
        append_env=True,
    )

    prepare_data = BashOperator(
        task_id="prepare_data",
        bash_command="python pipelines/prepare_data.py",
        cwd=PROJECT_DIR,
        env=COMMON_ENV,
        append_env=True,
    )

    build_feature_store_dataset = BashOperator(
        task_id="build_feature_store_dataset",
        bash_command="python pipelines/build_feature_store_dataset.py",
        cwd=PROJECT_DIR,
        env=COMMON_ENV,
        append_env=True,
    )

    apply_feast_definitions = BashOperator(
        task_id="apply_feast_definitions",
        bash_command="cd feature_repo && feast apply",
        cwd=PROJECT_DIR,
        env=COMMON_ENV,
        append_env=True,
    )

    check_feature_store = BashOperator(
        task_id="check_feature_store",
        bash_command="python pipelines/check_feature_store.py",
        cwd=PROJECT_DIR,
        env=COMMON_ENV,
        append_env=True,
    )

    train_models = BashOperator(
        task_id="train_models",
        bash_command="python pipelines/train_mlflow.py",
        cwd=PROJECT_DIR,
        env=COMMON_ENV,
        append_env=True,
    )

    promote_model = BashOperator(
        task_id="promote_model",
        bash_command="python pipelines/promote_model.py",
        cwd=PROJECT_DIR,
        env=COMMON_ENV,
        append_env=True,
    )

    (
        download_data
        >> prepare_data
        >> build_feature_store_dataset
        >> apply_feast_definitions
        >> check_feature_store
        >> train_models
        >> promote_model
    )
