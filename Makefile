PYTHON := python

COMPOSE := docker compose -f infra/docker-compose.yml
MLFLOW_URI := http://127.0.0.1:5050

.PHONY: install test download-data prepare-data train train-mlflow promote docker-up docker-up-core docker-up-api docker-down docker-ps api-local

install:
	$(PYTHON) -m pip install --upgrade pip setuptools wheel
	$(PYTHON) -m pip install -r requirements.txt

test:
	$(PYTHON) -m pytest -q

download-data:
	$(PYTHON) pipelines/download_data.py

prepare-data:
	$(PYTHON) pipelines/prepare_data.py

train:
	$(PYTHON) pipelines/train_baseline.py

train-mlflow:
	MLFLOW_TRACKING_URI=$(MLFLOW_URI) $(PYTHON) pipelines/train_mlflow.py

promote:
	MLFLOW_TRACKING_URI=$(MLFLOW_URI) $(PYTHON) pipelines/promote_model.py

docker-up-core:
	$(COMPOSE) up -d postgres mlflow

docker-up-api:
	$(COMPOSE) up -d api

docker-up:
	$(COMPOSE) up -d

docker-down:
	$(COMPOSE) down

docker-ps:
	$(COMPOSE) ps

api-local:
	uvicorn app.main:app --host 127.0.0.1 --port 8000
