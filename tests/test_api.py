import numpy as np
from fastapi.testclient import TestClient

from app import main


class DummyModel:
    def predict(self, features):
        return np.array([0])


class DummyModelImpl:
    def predict_proba(self, features):
        return np.array([[0.95, 0.05]])


def test_health_endpoint(monkeypatch):
    monkeypatch.setattr(main, "model", DummyModel())

    client = TestClient(main.app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["model_loaded"] is True


def test_model_info_endpoint(monkeypatch):
    monkeypatch.setattr(main, "model", DummyModel())

    client = TestClient(main.app)
    response = client.get("/model/info")

    assert response.status_code == 200

    payload = response.json()
    assert payload["model_name"] == "predictive-maintenance-model"
    assert payload["model_alias"] == "champion"
    assert payload["status"] == "loaded"


def test_predict_endpoint(monkeypatch):
    dummy_model = DummyModel()
    dummy_model._model_impl = DummyModelImpl()

    monkeypatch.setattr(main, "model", dummy_model)

    client = TestClient(main.app)

    request_payload = {
        "air_temperature_k": 298.1,
        "process_temperature_k": 308.6,
        "rotational_speed_rpm": 1551,
        "torque_nm": 42.8,
        "tool_wear_min": 120,
        "machine_type_H": 0,
        "machine_type_L": 0,
        "machine_type_M": 1,
    }

    response = client.post("/predict", json=request_payload)

    assert response.status_code == 200

    payload = response.json()
    assert payload["prediction"] == 0
    assert payload["failure_probability"] == 0.05
    assert payload["risk_level"] == "low"
    assert payload["recommended_action"] == "continue_normal_operation"


def test_predict_validation_error(monkeypatch):
    monkeypatch.setattr(main, "model", DummyModel())

    client = TestClient(main.app)

    invalid_payload = {
        "air_temperature_k": 298.1,
    }

    response = client.post("/predict", json=invalid_payload)

    assert response.status_code == 422
