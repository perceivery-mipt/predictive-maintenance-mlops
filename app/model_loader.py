import os

import mlflow
import mlflow.pyfunc


MODEL_NAME = os.getenv("MODEL_NAME", "predictive-maintenance-model")
MODEL_ALIAS = os.getenv("MODEL_ALIAS", "champion")
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI")


def configure_mlflow() -> None:
    if MLFLOW_TRACKING_URI:
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)


def get_model_uri() -> str:
    return f"models:/{MODEL_NAME}@{MODEL_ALIAS}"


def load_model():
    configure_mlflow()
    model_uri = get_model_uri()
    return mlflow.pyfunc.load_model(model_uri)
