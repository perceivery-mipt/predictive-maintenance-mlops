from contextlib import asynccontextmanager
import os
from time import perf_counter

import pandas as pd
from fastapi import FastAPI, HTTPException, Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

from app.feature_store_loader import get_feature_store
from app.model_loader import MODEL_ALIAS, MODEL_NAME, get_model_uri, load_model
from app.schemas import (
    FeatureStorePredictionRequest,
    ModelInfoResponse,
    PredictionRequest,
    PredictionResponse,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global model
    model = load_model()
    yield


app = FastAPI(
    title="Predictive Maintenance Inference API",
    description="API for predicting industrial equipment failure risk.",
    version="0.1.0",
    lifespan=lifespan,
)

REQUEST_COUNT = Counter(
    "predict_requests_total",
    "Total number of prediction requests",
)

PREDICTION_ERROR_COUNT = Counter(
    "predict_errors_total",
    "Total number of prediction errors",
)

PREDICTION_LATENCY = Histogram(
    "predict_latency_seconds",
    "Prediction latency in seconds",
)

PREDICTION_RISK_COUNT = Counter(
    "prediction_risk_level_total",
    "Number of predictions by risk level",
    ["risk_level"],
)

FEATURE_RETRIEVAL_REQUEST_COUNT = Counter(
    "feature_retrieval_requests_total",
    "Total number of online feature retrieval requests",
)

FEATURE_RETRIEVAL_ERROR_COUNT = Counter(
    "feature_retrieval_errors_total",
    "Total number of online feature retrieval errors",
)

FEATURE_RETRIEVAL_LATENCY = Histogram(
    "feature_retrieval_latency_seconds",
    "Online feature retrieval latency in seconds",
)

model = None

DEPLOYMENT_TRACK = os.getenv("DEPLOYMENT_TRACK", "single")


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



def get_risk_level(probability: float) -> str:
    if probability >= 0.75:
        return "critical"
    if probability >= 0.50:
        return "high"
    if probability >= 0.25:
        return "medium"
    return "low"


def get_recommended_action(risk_level: str) -> str:
    actions = {
        "critical": "stop_machine_and_schedule_urgent_maintenance",
        "high": "schedule_maintenance",
        "medium": "increase_monitoring_frequency",
        "low": "continue_normal_operation",
    }
    return actions[risk_level]


def request_to_dataframe(request: PredictionRequest) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "air_temperature_k": request.air_temperature_k,
                "process_temperature_k": request.process_temperature_k,
                "rotational_speed_rpm": request.rotational_speed_rpm,
                "torque_nm": request.torque_nm,
                "tool_wear_min": request.tool_wear_min,
                "machine_type_H": request.machine_type_H,
                "machine_type_L": request.machine_type_L,
                "machine_type_M": request.machine_type_M,
            }
        ],
        columns=FEATURE_COLUMNS,
    )


def online_features_to_dataframe(features: dict) -> pd.DataFrame:
    row = {}

    for column in FEATURE_COLUMNS:
        values = features.get(column)
        if not values or values[0] is None:
            raise ValueError(f"Online feature '{column}' was not found in Feast Redis.")
        row[column] = values[0]

    return pd.DataFrame([row], columns=FEATURE_COLUMNS)


def predict_from_features(features: pd.DataFrame) -> PredictionResponse:
    raw_prediction = model.predict(features)
    prediction = int(raw_prediction[0])

    if hasattr(model, "_model_impl") and hasattr(model._model_impl, "predict_proba"):
        probability = float(model._model_impl.predict_proba(features)[0, 1])
    else:
        probability = float(prediction)

    risk_level = get_risk_level(probability)
    recommended_action = get_recommended_action(risk_level)

    PREDICTION_RISK_COUNT.labels(risk_level=risk_level).inc()

    return PredictionResponse(
        failure_probability=probability,
        prediction=prediction,
        risk_level=risk_level,
        recommended_action=recommended_action,
        model_name=MODEL_NAME,
        model_alias=MODEL_ALIAS,
    )


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "model_loaded": model is not None,
        "deployment_track": DEPLOYMENT_TRACK,
        "model_alias": MODEL_ALIAS,
    }


@app.get("/model/info", response_model=ModelInfoResponse)
def model_info() -> ModelInfoResponse:
    return ModelInfoResponse(
        model_name=MODEL_NAME,
        model_alias=MODEL_ALIAS,
        model_uri=get_model_uri(),
        status="loaded" if model is not None else "not_loaded",
    )


@app.post("/predict", response_model=PredictionResponse)
def predict(request: PredictionRequest) -> PredictionResponse:
    global model

    if model is None:
        raise HTTPException(status_code=503, detail="Model is not loaded.")

    REQUEST_COUNT.inc()
    start_time = perf_counter()

    try:
        features = request_to_dataframe(request)
        return predict_from_features(features)

    except Exception as error:
        PREDICTION_ERROR_COUNT.inc()
        raise HTTPException(status_code=500, detail=str(error)) from error

    finally:
        latency = perf_counter() - start_time
        PREDICTION_LATENCY.observe(latency)


@app.post("/predict/from-feature-store", response_model=PredictionResponse)
def predict_from_feature_store(request: FeatureStorePredictionRequest) -> PredictionResponse:
    global model

    if model is None:
        raise HTTPException(status_code=503, detail="Model is not loaded.")

    REQUEST_COUNT.inc()
    FEATURE_RETRIEVAL_REQUEST_COUNT.inc()

    prediction_start_time = perf_counter()

    try:
        retrieval_start_time = perf_counter()

        try:
            feature_store = get_feature_store()
            feature_vector = feature_store.get_online_features(
                features=[
                    "machine_sensor_features:air_temperature_k",
                    "machine_sensor_features:process_temperature_k",
                    "machine_sensor_features:rotational_speed_rpm",
                    "machine_sensor_features:torque_nm",
                    "machine_sensor_features:tool_wear_min",
                    "machine_sensor_features:machine_type_H",
                    "machine_sensor_features:machine_type_L",
                    "machine_sensor_features:machine_type_M",
                ],
                entity_rows=[{"machine_id": request.machine_id}],
            ).to_dict()

            FEATURE_RETRIEVAL_LATENCY.observe(perf_counter() - retrieval_start_time)

        except Exception as error:
            FEATURE_RETRIEVAL_ERROR_COUNT.inc()
            raise HTTPException(
                status_code=503,
                detail=f"Online feature retrieval failed: {error}",
            ) from error

        features = online_features_to_dataframe(feature_vector)
        return predict_from_features(features)

    except HTTPException:
        PREDICTION_ERROR_COUNT.inc()
        raise

    except Exception as error:
        PREDICTION_ERROR_COUNT.inc()
        raise HTTPException(status_code=500, detail=str(error)) from error

    finally:
        PREDICTION_LATENCY.observe(perf_counter() - prediction_start_time)


@app.get("/metrics")
def metrics() -> Response:
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
