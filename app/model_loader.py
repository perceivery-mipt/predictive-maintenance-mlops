import os

import mlflow.pyfunc


MODEL_NAME = os.getenv("MODEL_NAME", "predictive-maintenance-model")
MODEL_ALIAS = os.getenv("MODEL_ALIAS", "champion")


def get_model_uri() -> str:
    return f"models:/{MODEL_NAME}@{MODEL_ALIAS}"


def load_model():
    model_uri = get_model_uri()
    return mlflow.pyfunc.load_model(model_uri)
