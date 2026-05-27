PYTHON := python

COMPOSE := docker compose -f infra/docker-compose.yml
CANARY_COMPOSE := docker compose -f infra/docker-compose.canary.yml

MLFLOW_URI := http://127.0.0.1:5050
FEAST_REDIS_CONNECTION_STRING := localhost:16379

.PHONY: install test download-data prepare-data build-feast-dataset feast-apply feast-check train train-mlflow promote docker-up docker-up-core docker-up-api docker-down docker-ps api-local airflow-init airflow-up airflow-trigger airflow-logs drift-check canary-up canary-down canary-ps canary-check canary-90-10 canary-50-50 canary-100 canary-rollback

install:
	$(PYTHON) -m pip install --upgrade pip setuptools wheel
	$(PYTHON) -m pip install -r requirements.txt

test:
	$(PYTHON) -m pytest -q

download-data:
	$(PYTHON) pipelines/download_data.py

prepare-data:
	$(PYTHON) pipelines/prepare_data.py

build-feast-dataset:
	$(PYTHON) pipelines/build_feature_store_dataset.py

feast-apply:
	FEAST_REDIS_CONNECTION_STRING=$(FEAST_REDIS_CONNECTION_STRING) cd feature_repo && feast apply

feast-check:
	FEAST_REDIS_CONNECTION_STRING=$(FEAST_REDIS_CONNECTION_STRING) $(PYTHON) pipelines/check_feature_store.py

train:
	$(PYTHON) pipelines/train_baseline.py

train-mlflow:
	MLFLOW_TRACKING_URI=$(MLFLOW_URI) $(PYTHON) pipelines/train_mlflow.py

promote:
	MLFLOW_TRACKING_URI=$(MLFLOW_URI) $(PYTHON) pipelines/promote_model.py

docker-up-core:
	$(COMPOSE) up -d postgres redis mlflow

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


airflow-init:
	$(COMPOSE) up -d airflow-init

airflow-up:
	$(COMPOSE) up -d airflow-webserver airflow-scheduler

airflow-trigger:
	$(COMPOSE) exec airflow-scheduler airflow dags unpause predictive_maintenance_training_pipeline
	$(COMPOSE) exec airflow-scheduler airflow dags trigger predictive_maintenance_training_pipeline

airflow-logs:
	$(COMPOSE) logs --tail=120 airflow-webserver airflow-scheduler


drift-check:
	$(PYTHON) pipelines/check_data_drift.py


canary-up:
	$(CANARY_COMPOSE) up -d --build

canary-down:
	$(CANARY_COMPOSE) down

canary-ps:
	$(CANARY_COMPOSE) ps

canary-check:
	N=50 scripts/check_canary_distribution.sh | grep deployment_track | sort | uniq -c

canary-90-10:
	scripts/switch_canary_90_10.sh

canary-50-50:
	scripts/switch_canary_50_50.sh

canary-100:
	scripts/switch_canary_100.sh

canary-rollback:
	scripts/rollback_canary_to_stable.sh
