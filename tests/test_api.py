import numpy as np
from fastapi.testclient import TestClient

from app import main


class DummyModelImpl:
    def __init__(self, probability: float):
        self.probability = probability

    def predict_proba(self, features):
        return np.array([[1.0 - self.probability, self.probability]])


class DummyModel:
    def __init__(self, prediction: int = 0, probability: float = 0.05):
        self.prediction = prediction
        self._model_impl = DummyModelImpl(probability)

    def predict(self, features):
        return np.array([self.prediction])


def make_client(monkeypatch, prediction: int = 0, probability: float = 0.05):
    dummy_model = DummyModel(prediction=prediction, probability=probability)
    monkeypatch.setattr(main, "load_model", lambda: dummy_model)
    return TestClient(main.app)


def valid_payload():
    return {
        "air_temperature_k": 298.1,
        "process_temperature_k": 308.6,
        "rotational_speed_rpm": 1551,
        "torque_nm": 42.8,
        "tool_wear_min": 120,
        "machine_type_H": 0,
        "machine_type_L": 0,
        "machine_type_M": 1,
    }


def test_health_endpoint(monkeypatch):
    client = make_client(monkeypatch)

    with client:
        response = client.get("/health")

    assert response.status_code == 200

    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["model_loaded"] is True
    assert payload["deployment_track"] == "single"
    assert payload["model_alias"] == "champion"


def test_model_info_endpoint(monkeypatch):
    client = make_client(monkeypatch)

    with client:
        response = client.get("/model/info")

    assert response.status_code == 200

    payload = response.json()
    assert payload["model_name"] == "predictive-maintenance-model"
    assert payload["model_alias"] == "champion"
    assert payload["model_uri"] == "models:/predictive-maintenance-model@champion"
    assert payload["status"] == "loaded"


def test_predict_endpoint_low_risk(monkeypatch):
    client = make_client(monkeypatch, prediction=0, probability=0.05)

    with client:
        response = client.post("/predict", json=valid_payload())

    assert response.status_code == 200

    payload = response.json()
    assert payload["prediction"] == 0
    assert payload["failure_probability"] == 0.05
    assert payload["risk_level"] == "low"
    assert payload["recommended_action"] == "continue_normal_operation"
    assert payload["model_name"] == "predictive-maintenance-model"
    assert payload["model_alias"] == "champion"


def test_predict_endpoint_medium_risk(monkeypatch):
    client = make_client(monkeypatch, prediction=0, probability=0.30)

    with client:
        response = client.post("/predict", json=valid_payload())

    assert response.status_code == 200
    assert response.json()["risk_level"] == "medium"
    assert response.json()["recommended_action"] == "increase_monitoring_frequency"


def test_predict_endpoint_high_risk(monkeypatch):
    client = make_client(monkeypatch, prediction=1, probability=0.60)

    with client:
        response = client.post("/predict", json=valid_payload())

    assert response.status_code == 200
    assert response.json()["risk_level"] == "high"
    assert response.json()["recommended_action"] == "schedule_maintenance"


def test_predict_endpoint_critical_risk(monkeypatch):
    client = make_client(monkeypatch, prediction=1, probability=0.90)

    with client:
        response = client.post("/predict", json=valid_payload())

    assert response.status_code == 200
    assert response.json()["risk_level"] == "critical"
    assert response.json()["recommended_action"] == "stop_machine_and_schedule_urgent_maintenance"


def test_predict_validation_error_for_missing_fields(monkeypatch):
    client = make_client(monkeypatch)

    invalid_payload = {
        "air_temperature_k": 298.1,
    }

    with client:
        response = client.post("/predict", json=invalid_payload)

    assert response.status_code == 422


def test_predict_validation_error_for_invalid_machine_type_flag(monkeypatch):
    client = make_client(monkeypatch)

    payload = valid_payload()
    payload["machine_type_M"] = 2

    with client:
        response = client.post("/predict", json=payload)

    assert response.status_code == 422


def test_metrics_endpoint(monkeypatch):
    client = make_client(monkeypatch)

    with client:
        response = client.get("/metrics")

    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert b"predict_requests_total" in response.content
