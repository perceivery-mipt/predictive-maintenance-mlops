# Запуск и проверка Predictive Maintenance MLOps System (отчет)

Этот ноутбук фиксирует воспроизводимый запуск MLOps-системы для задачи предиктивного обслуживания промышленного оборудования.

Цель отчёта — показать, что проект можно поднять из репозитория, проверить тестами, запустить инфраструктуру, открыть основные UI, выполнить inference-запросы, проверить мониторинг, SLO rules, data drift report и canary traffic switching.

Проект включает:

- FastAPI inference service;
- Feast Feature Store;
- Redis Online Store;
- PostgreSQL;
- MLflow Tracking Server и Model Registry;
- Airflow orchestration;
- Prometheus monitoring;
- Grafana dashboard;
- Node Exporter infrastructure monitoring;
- Evidently data drift report;
- Nginx-based canary gateway;
- Docker Compose и Ansible как Infrastructure as Code.

Все команды ниже предполагают запуск из корня репозитория `predictive-maintenance-mlops`.

# Порты 

```text
8000   FastAPI API
8010   Canary Gateway
5050   MLflow UI
8081   Airflow UI
9090   Prometheus
9100   Node Exporter
3000   Grafana
15432  PostgreSQL
16379  Redis
```

# Корень проекта


```python
%env PROJECT_ROOT=/Users/perceivery/Desktop/predictive-maintenance-mlops
```

    env: PROJECT_ROOT=/Users/perceivery/Desktop/predictive-maintenance-mlops


# Проверка файлов проекта


```bash
%%bash
cd "$PROJECT_ROOT"
pwd
ls -la | head
```

    /Users/perceivery/Desktop/predictive-maintenance-mlops
    total 104
    drwxr-xr-x@ 29 perceivery  staff    928 May 30 20:46 [34m.[m[m
    drwx------@ 59 perceivery  staff   1888 May 30 20:46 [34m..[m[m
    -rw-r--r--@  1 perceivery  staff    496 May 25 17:25 .env.example
    drwxr-xr-x@ 13 perceivery  staff    416 May 30 20:38 [34m.git[m[m
    drwxr-xr-x@  3 perceivery  staff     96 May 27 14:45 [34m.github[m[m
    -rw-r--r--@  1 perceivery  staff    319 May 27 18:31 .gitignore
    drwxr-xr-x@  6 perceivery  staff    192 May 27 14:45 [34m.pytest_cache[m[m
    drwxr-xr-x@  7 perceivery  staff    224 May 30 20:06 [34m.venv[m[m
    -rw-r--r--@  1 perceivery  staff   2466 May 27 17:58 Makefile


# Проверка состояния репозитория

Перед запуском сервисов фиксируем состояние Git-репозитория.


```bash
%%bash
cd "$PROJECT_ROOT"
git status
git log --oneline -8
```

    On branch main
    Untracked files:
      (use "git add <file>..." to include in what will be committed)
    	notebooks/service_up_report.ipynb
    
    nothing added to commit but untracked files present (use "git add" to track)
    2cb17ed Add MDD latency A/B test notebook and ADR reference
    fdcd059 Add canary and infrastructure health checks to Ansible vars
    60893b7 Extend Ansible deployment with canary and smoke checks
    09fb502 Ignore local MLflow file store
    722e719 Add Makefile commands for canary deployment
    e3651eb Show pytest summary while suppressing warnings
    773cc70 Disable third-party warnings output in pytest
    842fda1 Document canary deployment for inference service


# Проверка локального окружения

Проверяем, что доступны Python, Docker, Docker Compose и Makefile. Эти инструменты нужны для запуска тестов, сборки контейнеров и поднятия MLOps-инфраструктуры.


```bash
%%bash
cd "$PROJECT_ROOT"
python --version
docker --version
docker compose version
make --version | head -n 1
```

    Python 3.12.0
    Docker version 29.1.2, build 890dcca
    Docker Compose version v2.40.3-desktop.1
    GNU Make 3.81


# Создание venv  и установка зависимостей

Создаём локальное Python-окружение `.venv` и устанавливаем зависимости проекта из `requirements.txt`.

В проекте установка обёрнута в Makefile-команду

```bash
make install
```


```bash
%%bash
cd "$PROJECT_ROOT"
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

. .venv/bin/activate
```


```bash
%%bash
cd "$PROJECT_ROOT"
make install
```

# Запуск тестов проекта

После проверки окружения запускаем автоматические тесты проекта.

Команда `make test` использует pytest и проверяет базовую работоспособность API-логики и вспомогательных компонентов.

Ожидаемый результат:

```text
9 passed
```


```bash
%%bash
cd "$PROJECT_ROOT"
make test
```

    python -m pytest -q
    [32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m                                                                [100%][0m
    [32m[32m[1m9 passed[0m[32m in 1.86s[0m[0m


# Проверка Docker Compose конфигурации основного контура

Перед запуском сервисов проверяем, что основной Docker Compose файл синтаксически корректен и может быть собран Docker Compose.

Основной контур описан в файле:

```text
infra/docker-compose.yml
```
В него входят PostgreSQL, Redis, MLflow, FastAPI, Airflow, Prometheus, Grafana и Node Exporter.


```bash
%%bash
cd "$PROJECT_ROOT"
docker compose -f infra/docker-compose.yml config >/tmp/main-compose-config.txt
echo "Main Docker Compose config is valid."
```

    Main Docker Compose config is valid.


# Проверка Docker Compose конфигурации canary-контура

Canary-контур описан в отдельном файле:

```text
infra/docker-compose.canary.yml
```

Он поднимает два экземпляра inference service:

- stable;
- canary;

и Nginx gateway, который переключает трафик между ними.


```bash
%%bash
cd "$PROJECT_ROOT"
docker compose -f infra/docker-compose.canary.yml config >/tmp/canary-compose-config.txt
echo "Canary Docker Compose config is valid."
```

    Canary Docker Compose config is valid.


# Запуск основного MLOps-контура

Поднимаем основной Docker Compose контур из файла:

```text
infra/docker-compose.yml
```

В этом контуре запускаются основные сервисы проекта: PostgreSQL, Redis, MLflow, FastAPI, Airflow, Prometheus, Grafana и Node Exporter.

Команда выполняет сборку образов при необходимости и запускает контейнеры в фоне.


```bash
%%bash
cd "$PROJECT_ROOT"
docker compose -f infra/docker-compose.yml up -d --build
```

    #1 [internal] load local bake definitions
    #1 reading from stdin 2.12kB done
    #1 DONE 0.0s
    
    #2 [api internal] load build definition from Dockerfile.api
    #2 transferring dockerfile: 680B done
    #2 DONE 0.0s
    
    #3 [airflow-scheduler internal] load build definition from Dockerfile.airflow
    #3 transferring dockerfile: 231B done
    #3 DONE 0.0s
    
    #4 [airflow-webserver internal] load metadata for docker.io/apache/airflow:2.10.4-python3.12
    #4 DONE 4.2s
    
    #5 [airflow-init internal] load .dockerignore
    #5 transferring context: 2B done
    #5 DONE 0.0s
    
    #6 [airflow-scheduler 1/3] FROM docker.io/apache/airflow:2.10.4-python3.12@sha256:04e7fba174eb5c77057f59ef18c1215179181cd5dd7189afbc39b1146f54540f
    #6 resolve docker.io/apache/airflow:2.10.4-python3.12@sha256:04e7fba174eb5c77057f59ef18c1215179181cd5dd7189afbc39b1146f54540f done
    #6 DONE 0.0s
    
    #7 [airflow-scheduler internal] load build context
    #7 transferring context: 336B done
    #7 DONE 0.0s
    
    #8 [airflow-scheduler 2/3] COPY infra/requirements-airflow.txt /tmp/requirements-airflow.txt
    #8 CACHED
    
    #9 [airflow-scheduler 3/3] RUN pip install --no-cache-dir -r /tmp/requirements-airflow.txt
    #9 CACHED
    
    #10 [airflow-webserver] exporting to image
    #10 exporting layers done
    #10 exporting manifest sha256:62f75158850c482059c47e654a920b9975d60660d0dfa737bf242ab47c527175 done
    #10 exporting config sha256:687845260f80c21cd3e7db6c5f6bd46003f962832a0f9b89bee65eafe235fb89 done
    #10 exporting attestation manifest sha256:11c7da2bf9c8441ec6cb8b5865bf958149598009b583607557711f48117812ab 0.0s done
    #10 exporting manifest list sha256:70f112112ee6503af063071ba0612c6414c902b443f29ebf11c30c1713a252c9 done
    #10 naming to docker.io/library/infra-airflow-webserver:latest done
    #10 unpacking to docker.io/library/infra-airflow-webserver:latest done
    #10 DONE 0.1s
    
    #11 [airflow-init] exporting to image
    #11 exporting layers done
    #11 exporting manifest sha256:075a29915c23e0bc61b37a7702c91e86da6d6d7fadd5a12ab59c64a92b97fb42 done
    #11 exporting config sha256:2f7da54a0cbbc8cf3d3c5bbccf87a877d0a0d68eaaf4a33d8eb1c5f0cba63893 done
    #11 exporting attestation manifest sha256:d9ed31d66bf0bca339c6b4b27aba44fd47f852fe2b145fa974d9a973cfb3ca77 0.0s done
    #11 exporting manifest list sha256:afe79c373109080170fd931322d8b98b8f8444460825945c8bbd00a1b845c6c4 done
    #11 naming to docker.io/library/infra-airflow-init:latest done
    #11 unpacking to docker.io/library/infra-airflow-init:latest done
    #11 DONE 0.1s
    
    #12 [airflow-scheduler] exporting to image
    #12 exporting layers done
    #12 exporting manifest sha256:9f67a8edae5629f5e13f6ca5f6463649c036b965490acba219e233df551673b8 done
    #12 exporting config sha256:6ce49e6781b1e0aaef34c4cdfb5a25ed9c12fc0ef0e85a76ae97d8e9d3cd061c done
    #12 exporting attestation manifest sha256:48be26c799df39ac3c9478f6cae4caed6e78bc436eccb26410d6f7227680a996 0.0s done
    #12 exporting manifest list sha256:eb64e67380ac7716587964bf37bcc13fcac420fb178e15fccc136facf0d950b8 done
    #12 naming to docker.io/library/infra-airflow-scheduler:latest done
    #12 unpacking to docker.io/library/infra-airflow-scheduler:latest done
    #12 DONE 0.1s
    
    #13 [api internal] load metadata for docker.io/library/python:3.12-slim
    #13 DONE 4.5s
    
    #5 [api internal] load .dockerignore
    #5 transferring context: 2B done
    #5 DONE 0.0s
    
    #14 [api internal] load build context
    #14 transferring context: 30.09kB done
    #14 DONE 0.0s
    
    #15 [api 1/7] FROM docker.io/library/python:3.12-slim@sha256:090ba77e2958f6af52a5341f788b50b032dd4ca28377d2893dcf1ecbdfdfe203
    #15 resolve docker.io/library/python:3.12-slim@sha256:090ba77e2958f6af52a5341f788b50b032dd4ca28377d2893dcf1ecbdfdfe203 0.0s done
    #15 DONE 0.0s
    
    #16 [api 6/7] COPY app /app/app
    #16 CACHED
    
    #17 [api 2/7] WORKDIR /app
    #17 CACHED
    
    #18 [api 3/7] RUN apt-get update     && apt-get install -y --no-install-recommends curl     && rm -rf /var/lib/apt/lists/*
    #18 CACHED
    
    #19 [api 4/7] COPY requirements.txt /app/requirements.txt
    #19 CACHED
    
    #20 [api 5/7] RUN python -m pip install --upgrade pip setuptools wheel     && python -m pip install -r /app/requirements.txt
    #20 CACHED
    
    #21 [api 7/7] COPY src /app/src
    #21 CACHED
    
    #22 [airflow-init] resolving provenance for metadata file
    #22 DONE 0.0s
    
    #23 [airflow-webserver] resolving provenance for metadata file
    #23 DONE 0.0s
    
    #24 [airflow-scheduler] resolving provenance for metadata file
    #24 DONE 0.0s
    
    #25 [api] exporting to image
    #25 exporting layers done
    #25 exporting manifest sha256:92ca4fc5fa9e0e8e541d653c61222bef97f8158bac23cb179ad48a5da1046975 done
    #25 exporting config sha256:2c5ef586eeb54040816f1ca46306e46adf988a1c2fa182120ff7af1ffa21e0ee done
    #25 exporting attestation manifest sha256:029f45ec69b259be15ba4cea2613b4e6809b453a07e0bd5f8aa19a82cedcf927 done
    #25 exporting manifest list sha256:5b8c649cd2f2fe0ed0295749ee47128384e259ea4eb7d261dd626df33a4e943a done
    #25 naming to docker.io/library/infra-api:latest done
    #25 unpacking to docker.io/library/infra-api:latest done
    #25 DONE 0.1s
    
    #26 [api] resolving provenance for metadata file
    #26 DONE 0.0s


     infra-airflow-webserver  Built
     infra-airflow-init  Built
     infra-airflow-scheduler  Built
     infra-api  Built
    time="2026-05-30T20:54:13+03:00" level=warning msg="Found orphan containers ([predictive-maintenance-canary-gateway predictive-maintenance-api-canary predictive-maintenance-api-stable molvit-minio]) for this project. If you removed or renamed this service in your compose file, you can run this command with the --remove-orphans flag to clean it up."
     Container predictive-maintenance-airflow-init  Recreate
     Container predictive-maintenance-api  Recreate
     Container predictive-maintenance-api  Recreated
     Container predictive-maintenance-airflow-init  Recreated
     Container predictive-maintenance-airflow-webserver  Recreate
     Container predictive-maintenance-airflow-scheduler  Recreate
     Container predictive-maintenance-airflow-webserver  Recreated
     Container predictive-maintenance-airflow-scheduler  Recreated
     Container predictive-maintenance-redis  Starting
     Container predictive-maintenance-postgres  Starting
     Container predictive-maintenance-node-exporter  Starting
     Container predictive-maintenance-node-exporter  Started
     Container predictive-maintenance-redis  Started
     Container predictive-maintenance-postgres  Started
     Container predictive-maintenance-postgres  Waiting
     Container predictive-maintenance-postgres  Healthy
     Container predictive-maintenance-mlflow  Starting
     Container predictive-maintenance-mlflow  Started
     Container predictive-maintenance-postgres  Waiting
     Container predictive-maintenance-mlflow  Waiting
     Container predictive-maintenance-redis  Waiting
     Container predictive-maintenance-mlflow  Waiting
     Container predictive-maintenance-postgres  Healthy
     Container predictive-maintenance-redis  Healthy
     Container predictive-maintenance-mlflow  Healthy
     Container predictive-maintenance-api  Starting
     Container predictive-maintenance-mlflow  Healthy
     Container predictive-maintenance-airflow-init  Starting
     Container predictive-maintenance-airflow-init  Started
     Container predictive-maintenance-airflow-init  Waiting
     Container predictive-maintenance-airflow-init  Waiting
     Container predictive-maintenance-api  Started
     Container predictive-maintenance-api  Waiting
     Container predictive-maintenance-node-exporter  Waiting
     Container predictive-maintenance-node-exporter  Healthy
     Container predictive-maintenance-api  Healthy
     Container predictive-maintenance-prometheus  Starting
     Container predictive-maintenance-prometheus  Started
     Container predictive-maintenance-prometheus  Waiting
     Container predictive-maintenance-airflow-init  Exited
     Container predictive-maintenance-airflow-scheduler  Starting
     Container predictive-maintenance-airflow-init  Exited
     Container predictive-maintenance-airflow-webserver  Starting
     Container predictive-maintenance-airflow-webserver  Started
     Container predictive-maintenance-airflow-scheduler  Started
     Container predictive-maintenance-prometheus  Healthy
     Container predictive-maintenance-grafana  Starting
     Container predictive-maintenance-grafana  Started


# Проверка статусов контейнеров основного контура

После запуска проверяем состояние контейнеров. Для backend-сервисов важно увидеть, что контейнеры находятся в статусе `Up`, а сервисы с healthcheck имеют статус `healthy`.

Эта проверка нужна для подтверждения, что заявленные компоненты MLOps-системы действительно запущены.


```bash
%%bash
cd "$PROJECT_ROOT"

docker compose -f infra/docker-compose.yml ps
```

    NAME                                       IMAGE                           COMMAND                  SERVICE             CREATED              STATUS                        PORTS
    predictive-maintenance-airflow-scheduler   infra-airflow-scheduler         "/usr/bin/dumb-init …"   airflow-scheduler   About a minute ago   Up About a minute             8080/tcp
    predictive-maintenance-airflow-webserver   infra-airflow-webserver         "/usr/bin/dumb-init …"   airflow-webserver   About a minute ago   Up About a minute (healthy)   0.0.0.0:8081->8080/tcp, [::]:8081->8080/tcp
    predictive-maintenance-api                 infra-api                       "uvicorn app.main:ap…"   api                 About a minute ago   Up About a minute (healthy)   0.0.0.0:8000->8000/tcp, [::]:8000->8000/tcp
    predictive-maintenance-grafana             grafana/grafana:11.3.1          "/run.sh"                grafana             3 days ago           Up About a minute (healthy)   0.0.0.0:3000->3000/tcp, [::]:3000->3000/tcp
    predictive-maintenance-mlflow              ghcr.io/mlflow/mlflow:v2.18.0   "/bin/sh -c 'pip ins…"   mlflow              3 days ago           Up About a minute (healthy)   0.0.0.0:5050->5000/tcp, [::]:5050->5000/tcp
    predictive-maintenance-node-exporter       prom/node-exporter:v1.8.2       "/bin/node_exporter"     node-exporter       3 days ago           Up About a minute (healthy)   0.0.0.0:9100->9100/tcp, [::]:9100->9100/tcp
    predictive-maintenance-postgres            postgres:16                     "docker-entrypoint.s…"   postgres            3 days ago           Up About a minute (healthy)   0.0.0.0:15432->5432/tcp, [::]:15432->5432/tcp
    predictive-maintenance-prometheus          prom/prometheus:v2.55.1         "/bin/prometheus --c…"   prometheus          3 days ago           Up About a minute (healthy)   0.0.0.0:9090->9090/tcp, [::]:9090->9090/tcp
    predictive-maintenance-redis               redis:7                         "docker-entrypoint.s…"   redis               3 days ago           Up About a minute (healthy)   0.0.0.0:16379->6379/tcp, [::]:16379->6379/tcp


# Проверка FastAPI health endpoint

Проверяем, что inference API доступен по HTTP и возвращает статус сервиса.

Endpoint: GET /health


Ожидаемый результат: HTTP-запрос должен вернуть JSON со статусом ok, признаком загруженной модели и deployment track.


```bash
%%bash

cd "$PROJECT_ROOT"
curl -s http://127.0.0.1:8000/health
```

    {"status":"ok","model_loaded":true,"deployment_track":"single","model_alias":"champion"}

# Проверка информации о production-модели

Проверяем endpoint: GET /model/info

Он показывает, какую модель FastAPI service загрузил из MLflow Model Registry.

Ожидаемый результат:

- model_name = predictive-maintenance-model;
- model_alias = champion;
- status = loaded.


```bash
%%bash

cd "$PROJECT_ROOT"
curl -s http://127.0.0.1:8000/model/info
```

    {"model_name":"predictive-maintenance-model","model_alias":"champion","model_uri":"models:/predictive-maintenance-model@champion","status":"loaded"}

# Проверка inference endpoint `/predict`

Проверяем endpoint: POST /predict

Этот endpoint принимает полный набор признаков в request body и возвращает прогноз отказа оборудования, вероятность отказа, уровень риска и рекомендуемое действие.

Ожидаемый результат: HTTP-запрос должен вернуть JSON с полями failure_probability, prediction, risk_level, recommended_action, model_name и model_alias.


```bash
%%bash
cd "$PROJECT_ROOT"

curl -s -X POST http://127.0.0.1:8000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "air_temperature_k": 298.1,
    "process_temperature_k": 308.6,
    "rotational_speed_rpm": 1551,
    "torque_nm": 42.8,
    "tool_wear_min": 120,
    "machine_type_H": 0,
    "machine_type_L": 0,
    "machine_type_M": 1
  }'
```

    {"failure_probability":0.01965044927029856,"prediction":0,"risk_level":"low","recommended_action":"continue_normal_operation","model_name":"predictive-maintenance-model","model_alias":"champion"}

# Проверка Feast Feature Store

Feast используется для управления признаками модели.

В проекте проверяются два сценария работы Feature Store:

- offline retrieval  — получение исторических признаков для обучения
- online retrieval   — получение online-признаков из Redis для inference
  
Проверка выполняется скриптом: pipelines/check_feature_store.py

Скрипт проверяет offline retrieval, материализацию признаков в Redis Online Store и online retrieval по machine_id.


```bash
%%bash
cd "$PROJECT_ROOT"

. .venv/bin/activate
FEAST_REDIS_CONNECTION_STRING=localhost:16379 python pipelines/check_feature_store.py
```

    Offline feature retrieval passed.
       machine_id           event_timestamp  ...  machine_type_L  machine_type_M
    0           1 2026-01-01 00:00:00+00:00  ...               0               1
    1           2 2026-01-01 01:00:00+00:00  ...               1               0
    2           3 2026-01-01 02:00:00+00:00  ...               1               0
    
    [3 rows x 10 columns]
    Materializing [1m[32m1[0m feature views from [1m[32m2026-01-01 00:00:00+00:00[0m to [1m[32m2027-03-01 00:00:00+00:00[0m into the [1m[32mredis[0m online store.
    
    [1m[32mmachine_sensor_features[0m:
    Feature materialization to Redis passed.
    Online feature retrieval from Redis passed.
    {'machine_id': [1, 2, 3], 'machine_type_L': [0, 1, 1], 'machine_type_M': [1, 0, 0], 'machine_type_H': [0, 0, 0], 'torque_nm': [42.79999923706055, 46.29999923706055, 49.400001525878906], 'rotational_speed_rpm': [1551, 1408, 1498], 'tool_wear_min': [0, 3, 5], 'air_temperature_k': [298.1000061035156, 298.20001220703125, 298.1000061035156], 'process_temperature_k': [308.6000061035156, 308.70001220703125, 308.5]}


# Проверка production-like inference через Feast Redis

Проверяем endpoint: POST /predict/from-feature-store

Этот endpoint принимает только machine_id, получает online-признаки из Feast Redis Online Store и затем выполняет inference champion-моделью из MLflow Model Registry.

Эта проверка важна, потому что она показывает не просто ручную передачу признаков в API, а прод путь:

**machine_id -> Feast Redis Online Store -> FastAPI -> MLflow champion model -> prediction**


```bash
%%bash
cd "$PROJECT_ROOT"

curl -s -X POST http://127.0.0.1:8000/predict/from-feature-store \
  -H "Content-Type: application/json" \
  -d '{"machine_id": 1}'
```

    {"failure_probability":0.014700660952716337,"prediction":0,"risk_level":"low","recommended_action":"continue_normal_operation","model_name":"predictive-maintenance-model","model_alias":"champion"}

# Проверка FastAPI Prometheus metrics endpoint

FastAPI service отдаёт технические метрики на endpoint: GET /metrics

Prometheus использует этот endpoint для сбора метрик inference service.

Проверяем наличие основных метрик:

- predict_requests_total;
- predict_errors_total;
- predict_latency_seconds;
- feature_retrieval_requests_total;
- feature_retrieval_errors_total;
- feature_retrieval_latency_seconds.


```bash
%%bash

cd "$PROJECT_ROOT"
curl -s http://127.0.0.1:8000/metrics | grep -E "predict_requests_total|predict_errors_total|predict_latency_seconds|feature_retrieval_requests_total|feature_retrieval_errors_total|feature_retrieval_latency_seconds" | head -n 40
```

    # HELP predict_requests_total Total number of prediction requests
    # TYPE predict_requests_total counter
    predict_requests_total 2.0
    # HELP predict_errors_total Total number of prediction errors
    # TYPE predict_errors_total counter
    predict_errors_total 0.0
    # HELP predict_latency_seconds Prediction latency in seconds
    # TYPE predict_latency_seconds histogram
    predict_latency_seconds_bucket{le="0.005"} 0.0
    predict_latency_seconds_bucket{le="0.01"} 0.0
    predict_latency_seconds_bucket{le="0.025"} 0.0
    predict_latency_seconds_bucket{le="0.05"} 0.0
    predict_latency_seconds_bucket{le="0.075"} 1.0
    predict_latency_seconds_bucket{le="0.1"} 1.0
    predict_latency_seconds_bucket{le="0.25"} 1.0
    predict_latency_seconds_bucket{le="0.5"} 2.0
    predict_latency_seconds_bucket{le="0.75"} 2.0
    predict_latency_seconds_bucket{le="1.0"} 2.0
    predict_latency_seconds_bucket{le="2.5"} 2.0
    predict_latency_seconds_bucket{le="5.0"} 2.0
    predict_latency_seconds_bucket{le="7.5"} 2.0
    predict_latency_seconds_bucket{le="10.0"} 2.0
    predict_latency_seconds_bucket{le="+Inf"} 2.0
    predict_latency_seconds_count 2.0
    predict_latency_seconds_sum 0.35690154100001337
    # HELP predict_latency_seconds_created Prediction latency in seconds
    # TYPE predict_latency_seconds_created gauge
    predict_latency_seconds_created 1.7801636729608984e+09
    # HELP feature_retrieval_requests_total Total number of online feature retrieval requests
    # TYPE feature_retrieval_requests_total counter
    feature_retrieval_requests_total 1.0
    # HELP feature_retrieval_errors_total Total number of online feature retrieval errors
    # TYPE feature_retrieval_errors_total counter
    feature_retrieval_errors_total 0.0
    # HELP feature_retrieval_latency_seconds Online feature retrieval latency in seconds
    # TYPE feature_retrieval_latency_seconds histogram
    feature_retrieval_latency_seconds_bucket{le="0.005"} 0.0
    feature_retrieval_latency_seconds_bucket{le="0.01"} 0.0
    feature_retrieval_latency_seconds_bucket{le="0.025"} 0.0
    feature_retrieval_latency_seconds_bucket{le="0.05"} 0.0


# Проверка Prometheus health endpoint

Prometheus используется для сбора технических метрик FastAPI service, Node Exporter и самого Prometheus.

Проверяем health endpoint: GET /-/healthy


```bash
%%bash
cd "$PROJECT_ROOT"

curl -s http://127.0.0.1:9090/-/healthy
```

    Prometheus Server is Healthy.


# Проверка Prometheus targets

Проверяем, что Prometheus видит основные адреса сервисов:

- `predictive-maintenance-api` - метрики FastAPI: latency, ошибки, количество запросов, feature retrieval.
- `node-exporter` - метрики машины/инфраструктуры: CPU, память, диск итд
- `prometheus` — метрики самого Prometheus.

Нужно показать, что мониторинг не только запущен, но и реально собирает метрики с сервисов.


```bash
%%bash
cd "$PROJECT_ROOT"

curl -s "http://127.0.0.1:9090/api/v1/targets" \
  | python -m json.tool \
  | grep -E '"job"|"health"|"scrapeUrl"' \
  | head -n 40
```

                        "job": "node-exporter"
                        "job": "node-exporter"
                    "scrapeUrl": "http://node-exporter:9100/metrics",
                    "health": "up",
                        "job": "predictive-maintenance-api"
                        "job": "predictive-maintenance-api"
                    "scrapeUrl": "http://api:8000/metrics",
                    "health": "up",
                        "job": "prometheus"
                        "job": "prometheus"
                    "scrapeUrl": "http://prometheus:9090/metrics",
                    "health": "up",


# Проверка Prometheus alert rules / SLO rules

Проверяем, что Prometheus загрузил alert rules, связанные с SLO inference service.

В проекте используются правила для контроля:

- высокой latency;
- высокого error rate;
- недоступности API;
- ошибок online feature retrieval из Feast Redis.


```bash
%%bash
cd "$PROJECT_ROOT"

curl -s "http://127.0.0.1:9090/api/v1/rules" \
  | python -m json.tool \
  | grep -E '"name": "PredictiveMaintenance|state|health|query' \
  | head -n 80
```

                            "state": "inactive",
                            "name": "PredictiveMaintenanceHighLatency",
                            "query": "histogram_quantile(0.95, sum by (le) (rate(predict_latency_seconds_bucket[5m]))) > 1",
                            "health": "ok",
                            "state": "inactive",
                            "name": "PredictiveMaintenanceHighErrorRate",
                            "query": "(sum(rate(predict_errors_total[5m])) / clamp_min(sum(rate(predict_requests_total[5m])), 1)) > 0.01",
                            "health": "ok",
                            "state": "inactive",
                            "name": "PredictiveMaintenanceApiDown",
                            "query": "up{job=\"predictive-maintenance-api\"} == 0",
                            "health": "ok",
                            "state": "inactive",
                            "name": "PredictiveMaintenanceFeatureRetrievalErrors",
                            "query": "(sum(rate(feature_retrieval_errors_total[5m])) / clamp_min(sum(rate(feature_retrieval_requests_total[5m])), 1)) > 0.01",
                            "health": "ok",


# Проверка Grafana health endpoint

Grafana используется для визуализации метрик Prometheus.

Проверяем health endpoint Grafana: GET /api/health


```bash
%%bash
cd "$PROJECT_ROOT"

curl -s http://127.0.0.1:3000/api/health
```

    {
      "database": "ok",
      "version": "11.3.1",
      "commit": "64b556c137a1d9bcacd19ccb16c4cf138c78ca40"
    }

# Проверка MLflow Tracking Server

MLflow используется для отслеживания экспериментов, хранения метрик обучения, артефактов моделей и ведения реестра моделей.

Проверяем, что MLflow-сервер доступен по HTTP.

В локальном Docker Compose контуре веб-интерфейс MLflow открыт на порту: http://127.0.0.1:5050


```bash
%%bash
cd "$PROJECT_ROOT"

curl -s -I http://127.0.0.1:5050 | head
```

    HTTP/1.1 200 OK
    Server: gunicorn
    Date: Sat, 30 May 2026 18:12:18 GMT
    Connection: close
    Content-Disposition: inline; filename=index.html
    Content-Type: text/html; charset=utf-8
    Content-Length: 645
    Last-Modified: Mon, 18 Nov 2024 15:25:23 GMT
    Cache-Control: no-cache
    ETag: "1731943523.0-645-3609271048"


# Проверка Airflow

Airflow используется для оркестрации пайплайна обучения и продвижения модели.

Проверяем служебный endpoint Airflow: GET /health

В локальном Docker Compose контуре веб-интерфейс Airflow открыт на порту: http://127.0.0.1:8081


```bash
%%bash
cd "$PROJECT_ROOT"

curl -s http://127.0.0.1:8081/health
```

    {"dag_processor": {"latest_dag_processor_heartbeat": null, "status": null}, "metadatabase": {"status": "healthy"}, "scheduler": {"latest_scheduler_heartbeat": "2026-05-30T18:13:14.209696+00:00", "status": "healthy"}, "triggerer": {"latest_triggerer_heartbeat": null, "status": null}}

# Проверка DAG в Airflow

Проверяем, что Airflow видит DAG пайплайна обучения: predictive_maintenance_training_pipeline

Этот DAG отвечает за запуск этапов подготовки данных, построения признаков, проверки Feature Store, обучения моделей и продвижения лучшей модели.


```bash
%%bash
cd "$PROJECT_ROOT"

docker compose -f infra/docker-compose.yml exec airflow-scheduler \
  airflow dags list | grep predictive_maintenance_training_pipeline
```

    predictive_maintenance_training_pipeline | /opt/airflow/dags/predictive_maintenance_training_dag.py | airflow | False    


# Запуск Airflow DAG

Запускаем DAG `predictive_maintenance_training_pipeline`.


```bash
%%bash
cd "$PROJECT_ROOT"

docker compose -f infra/docker-compose.yml exec airflow-scheduler \
  airflow dags trigger predictive_maintenance_training_pipeline
```

    [2026-05-30T18:16:23.601+0000] {__init__.py:43} INFO - Loaded API auth backend: airflow.api.auth.backend.session
         |                     |                     |                     |                     |          |                  | last_scheduling_deci |                     |          |            |       
    conf | dag_id              | dag_run_id          | data_interval_start | data_interval_end   | end_date | external_trigger | sion                 | logical_date        | run_type | start_date | state 
    =====+=====================+=====================+=====================+=====================+==========+==================+======================+=====================+==========+============+=======
    {}   | predictive_maintena | manual__2026-05-30T | 2026-05-30          | 2026-05-30          | None     | True             | None                 | 2026-05-30          | manual   | None       | queued
         | nce_training_pipeli | 18:16:23+00:00      | 18:16:23+00:00      | 18:16:23+00:00      |          |                  |                      | 18:16:23+00:00      |          |            |       
         | ne                  |                     |                     |                     |          |                  |                      |                     |          |            |       
                                                                                                                                                                                                            


# Проверка статуса запущенного DAG

После запуска DAG проверяем его состояние.  
Сначала DAG может быть в статусе `queued` или `running`. После завершения успешного пайплайна ожидаемый статус `success`.


```bash
%%bash
cd "$PROJECT_ROOT"

sleep 20

docker compose -f infra/docker-compose.yml exec airflow-scheduler \
  airflow dags list-runs -d predictive_maintenance_training_pipeline | head -n 20
```

    dag_id                                   | run_id                            | state   | execution_date            | start_date                       | end_date                        
    =========================================+===================================+=========+===========================+==================================+=================================
    predictive_maintenance_training_pipeline | manual__2026-05-30T18:16:23+00:00 | success | 2026-05-30T18:16:23+00:00 | 2026-05-30T18:16:24.756295+00:00 | 2026-05-30T18:16:46.837752+00:00
    predictive_maintenance_training_pipeline | manual__2026-05-27T12:32:55+00:00 | success | 2026-05-27T12:32:55+00:00 | 2026-05-27T12:32:55.903753+00:00 | 2026-05-27T12:33:16.943774+00:00
    predictive_maintenance_training_pipeline | manual__2026-05-27T12:27:47+00:00 | failed  | 2026-05-27T12:27:47+00:00 | 2026-05-27T12:27:48.531776+00:00 | 2026-05-27T12:27:57.620754+00:00
                                                                                                                                                                                            


# Повторная проверка production-модели после запуска DAG

После успешного запуска Airflow DAG повторно проверяем endpoint `/model/info`.

Это подтвердит, что FastAPI service видит production-модель из MLflow Model Registry и загружает её по alias `champion`.


```bash
%%bash
cd "$PROJECT_ROOT"

curl -s http://127.0.0.1:8000/model/info
```

    {"model_name":"predictive-maintenance-model","model_alias":"champion","model_uri":"models:/predictive-maintenance-model@champion","status":"loaded"}

# Проверка Node Exporter

Node Exporter используется для сбора инфраструктурных метрик машины таких как CPU, памяти, диска и других системных показателей.

Проверяем, что Node Exporter отдаёт метрики на endpoint: GET /metrics

В локальном контуре Node Exporter доступен на порту 9100.


```bash
%%bash
cd "$PROJECT_ROOT"

curl -s http://127.0.0.1:9100/metrics | grep -E "node_cpu_seconds_total|node_memory|node_filesystem" | head -n 20
```

    # HELP node_cpu_seconds_total Seconds the CPUs spent in each mode.
    # TYPE node_cpu_seconds_total counter
    node_cpu_seconds_total{cpu="0",mode="idle"} 1479.66
    node_cpu_seconds_total{cpu="0",mode="iowait"} 2.1
    node_cpu_seconds_total{cpu="0",mode="irq"} 0
    node_cpu_seconds_total{cpu="0",mode="nice"} 0
    node_cpu_seconds_total{cpu="0",mode="softirq"} 13.5
    node_cpu_seconds_total{cpu="0",mode="steal"} 0
    node_cpu_seconds_total{cpu="0",mode="system"} 7.63
    node_cpu_seconds_total{cpu="0",mode="user"} 30.28
    node_cpu_seconds_total{cpu="1",mode="idle"} 1502.37
    node_cpu_seconds_total{cpu="1",mode="iowait"} 2.42
    node_cpu_seconds_total{cpu="1",mode="irq"} 0
    node_cpu_seconds_total{cpu="1",mode="nice"} 0
    node_cpu_seconds_total{cpu="1",mode="softirq"} 5.44
    node_cpu_seconds_total{cpu="1",mode="steal"} 0
    node_cpu_seconds_total{cpu="1",mode="system"} 4.72
    node_cpu_seconds_total{cpu="1",mode="user"} 17.97
    node_cpu_seconds_total{cpu="10",mode="idle"} 1511.03
    node_cpu_seconds_total{cpu="10",mode="iowait"} 0.63


# Проверка инфраструктурных метрик через Prometheus

Теперь проверяем не только сам Node Exporter, но и то что Prometheus успешно собирает его метрики.

Для этого запрашиваем метрику `node_cpu_seconds_total` через API Prometheus.


```bash
%%bash
cd "$PROJECT_ROOT"
curl -s "http://127.0.0.1:9090/api/v1/query?query=node_cpu_seconds_total" \
  | python -m json.tool \
  | grep -E '"status"|"__name__"|"job"|"instance"' \
  | head -n 20
```

        "status": "success",
                        "__name__": "node_cpu_seconds_total",
                        "instance": "node-exporter:9100",
                        "job": "node-exporter",
                        "__name__": "node_cpu_seconds_total",
                        "instance": "node-exporter:9100",
                        "job": "node-exporter",
                        "__name__": "node_cpu_seconds_total",
                        "instance": "node-exporter:9100",
                        "job": "node-exporter",
                        "__name__": "node_cpu_seconds_total",
                        "instance": "node-exporter:9100",
                        "job": "node-exporter",
                        "__name__": "node_cpu_seconds_total",
                        "instance": "node-exporter:9100",
                        "job": "node-exporter",
                        "__name__": "node_cpu_seconds_total",
                        "instance": "node-exporter:9100",
                        "job": "node-exporter",
                        "__name__": "node_cpu_seconds_total",


# Проверка data drift report через Evidently

Evidently используется для контроля дрифта входных данных.

Скрипт `pipelines/check_data_drift.py` сравнивает reference dataset и current dataset, строит HTML-отчёт и сохраняет JSON summary.

Ожидаемые артефакты:

```text
reports/evidently/data_drift_report.html
reports/evidently/data_drift_summary.json
```


```bash
%%bash
cd "$PROJECT_ROOT"

. .venv/bin/activate
make drift-check
```

    python pipelines/check_data_drift.py
    Evidently data drift report was created.
    HTML report: reports/evidently/data_drift_report.html
    JSON summary: reports/evidently/data_drift_summary.json
    {
      "reference_rows": 7000,
      "current_rows": 3000,
      "features": [
        "air_temperature_k",
        "process_temperature_k",
        "rotational_speed_rpm",
        "torque_nm",
        "tool_wear_min",
        "machine_type_H",
        "machine_type_L",
        "machine_type_M"
      ],
      "dataset_drift": false,
      "share_of_drifted_columns": 0.25,
      "number_of_drifted_columns": 2,
      "html_report_path": "reports/evidently/data_drift_report.html"
    }


# Проверка артефактов Evidently

Проверяем, что после запуска drift-check были созданы оба артефакта

- HTML-отчёт для визуального анализа;
- JSON summary для машинно-читаемого результата.


```bash
%%bash
cd "$PROJECT_ROOT"

ls -lh reports/evidently/data_drift_report.html
ls -lh reports/evidently/data_drift_summary.json
```

    -rw-r--r--@ 1 perceivery  staff   3.1M May 30 21:21 reports/evidently/data_drift_report.html
    -rw-r--r--@ 1 perceivery  staff   420B May 30 21:21 reports/evidently/data_drift_summary.json


# Запуск canary-контура

Теперь запускаем отдельный canary-контур из файла: infra/docker-compose.canary.yml

Он поднимает:

- stable inference service;
- canary inference service;
- Nginx gateway на порту 8010.

Canary gateway нужен для демонстрации постепенного переключения трафика между stable и canary API-сервисами.


```bash
%%bash
cd "$PROJECT_ROOT"

docker compose -f infra/docker-compose.canary.yml up -d --build
```

    #1 [internal] load local bake definitions
    #1 reading from stdin 1.05kB done
    #1 DONE 0.0s
    
    #2 [canary internal] load build definition from Dockerfile.api
    #2 transferring dockerfile: 680B done
    #2 DONE 0.0s
    
    #3 [stable internal] load metadata for docker.io/library/python:3.12-slim
    #3 DONE 1.9s
    
    #4 [canary internal] load .dockerignore
    #4 transferring context: 2B done
    #4 DONE 0.0s
    
    #5 [canary internal] load build context
    #5 transferring context: 751B done
    #5 DONE 0.0s
    
    #6 [canary 1/7] FROM docker.io/library/python:3.12-slim@sha256:090ba77e2958f6af52a5341f788b50b032dd4ca28377d2893dcf1ecbdfdfe203
    #6 resolve docker.io/library/python:3.12-slim@sha256:090ba77e2958f6af52a5341f788b50b032dd4ca28377d2893dcf1ecbdfdfe203 done
    #6 DONE 0.0s
    
    #7 [canary 5/7] RUN python -m pip install --upgrade pip setuptools wheel     && python -m pip install -r /app/requirements.txt
    #7 CACHED
    
    #8 [canary 2/7] WORKDIR /app
    #8 CACHED
    
    #9 [canary 3/7] RUN apt-get update     && apt-get install -y --no-install-recommends curl     && rm -rf /var/lib/apt/lists/*
    #9 CACHED
    
    #10 [canary 4/7] COPY requirements.txt /app/requirements.txt
    #10 CACHED
    
    #11 [canary 6/7] COPY app /app/app
    #11 CACHED
    
    #12 [canary 7/7] COPY src /app/src
    #12 CACHED
    
    #13 [canary] exporting to image
    #13 exporting layers done
    #13 exporting manifest sha256:13751aad085bcec435092683f97270da069c62f258eb109335e4d1bc08b7177f done
    #13 exporting config sha256:e735875051a9f57ccebef4d511006e7e324e04b8b76deb4ddbcdd3dacd8ea78a done
    #13 exporting attestation manifest sha256:e315adadcfa535f47f48f7bbad4b66e5f62885311af5334352049c5dc07f06d9 0.0s done
    #13 exporting manifest list sha256:af45bc6f9d6359d11b53e31fe2730706d08c5b37338c39c14f60d3fe7ce2a13b done
    #13 naming to docker.io/library/infra-canary:latest done
    #13 unpacking to docker.io/library/infra-canary:latest done
    #13 DONE 0.1s
    
    #14 [stable] exporting to image
    #14 exporting layers done
    #14 exporting manifest sha256:743e178ba85c433dc3aed35dc841c6e99c1ccabbcdc6f6aafb4303ed7998c3a7 done
    #14 exporting config sha256:f32d866014d0c01603b29899c9d0c8f066148ec889c07e269796232dacfee010 done
    #14 exporting attestation manifest sha256:a774ce853485400d66a1acd3c2fe3d6e713effdaed79f8a19f3a67fd40d8801e 0.0s done
    #14 exporting manifest list sha256:6469cfdad69f20d2323f6b8f651ad7f50b249057c0f10e607bda712571eb52bc done
    #14 naming to docker.io/library/infra-stable:latest done
    #14 unpacking to docker.io/library/infra-stable:latest done
    #14 DONE 0.1s
    
    #15 [canary] resolving provenance for metadata file
    #15 DONE 0.0s
    
    #16 [stable] resolving provenance for metadata file
    #16 DONE 0.0s


     infra-canary  Built
     infra-stable  Built
    time="2026-05-30T21:23:43+03:00" level=warning msg="Found orphan containers ([predictive-maintenance-airflow-scheduler predictive-maintenance-airflow-webserver predictive-maintenance-airflow-init predictive-maintenance-api predictive-maintenance-prometheus predictive-maintenance-node-exporter predictive-maintenance-grafana predictive-maintenance-redis predictive-maintenance-mlflow predictive-maintenance-postgres molvit-minio]) for this project. If you removed or renamed this service in your compose file, you can run this command with the --remove-orphans flag to clean it up."
     Container predictive-maintenance-api-canary  Recreate
     Container predictive-maintenance-api-stable  Recreate
     Container predictive-maintenance-api-stable  Recreated
     Container predictive-maintenance-api-canary  Recreated
     Container predictive-maintenance-api-canary  Starting
     Container predictive-maintenance-api-stable  Starting
     Container predictive-maintenance-api-stable  Started
     Container predictive-maintenance-api-canary  Started
     Container predictive-maintenance-api-canary  Waiting
     Container predictive-maintenance-api-stable  Waiting
     Container predictive-maintenance-api-stable  Healthy
     Container predictive-maintenance-api-canary  Healthy
     Container predictive-maintenance-canary-gateway  Starting
     Container predictive-maintenance-canary-gateway  Started


# Проверка статусов canary-контура

Проверяем, что поднялись оба экземпляра inference service:

- `stable`;
- `canary`;

а также Nginx gateway, который принимает внешний трафик на порту `8010`.


```bash
%%bash
cd "$PROJECT_ROOT"

docker compose -f infra/docker-compose.canary.yml ps
```

    NAME                                       IMAGE                           COMMAND                  SERVICE             CREATED          STATUS                             PORTS
    predictive-maintenance-airflow-scheduler   infra-airflow-scheduler         "/usr/bin/dumb-init …"   airflow-scheduler   30 minutes ago   Up 29 minutes                      8080/tcp
    predictive-maintenance-airflow-webserver   infra-airflow-webserver         "/usr/bin/dumb-init …"   airflow-webserver   30 minutes ago   Up 29 minutes (healthy)            0.0.0.0:8081->8080/tcp, [::]:8081->8080/tcp
    predictive-maintenance-api                 infra-api                       "uvicorn app.main:ap…"   api                 30 minutes ago   Up 30 minutes (healthy)            0.0.0.0:8000->8000/tcp, [::]:8000->8000/tcp
    predictive-maintenance-api-canary          infra-canary                    "uvicorn app.main:ap…"   canary              48 seconds ago   Up 47 seconds (healthy)            8000/tcp
    predictive-maintenance-api-stable          infra-stable                    "uvicorn app.main:ap…"   stable              48 seconds ago   Up 47 seconds (healthy)            8000/tcp
    predictive-maintenance-canary-gateway      nginx:1.27-alpine               "/docker-entrypoint.…"   canary-gateway      3 days ago       Up 42 seconds (health: starting)   0.0.0.0:8010->80/tcp, [::]:8010->80/tcp
    predictive-maintenance-grafana             grafana/grafana:11.3.1          "/run.sh"                grafana             3 days ago       Up 29 minutes (healthy)            0.0.0.0:3000->3000/tcp, [::]:3000->3000/tcp
    predictive-maintenance-mlflow              ghcr.io/mlflow/mlflow:v2.18.0   "/bin/sh -c 'pip ins…"   mlflow              3 days ago       Up 30 minutes (healthy)            0.0.0.0:5050->5000/tcp, [::]:5050->5000/tcp
    predictive-maintenance-node-exporter       prom/node-exporter:v1.8.2       "/bin/node_exporter"     node-exporter       3 days ago       Up 30 minutes (healthy)            0.0.0.0:9100->9100/tcp, [::]:9100->9100/tcp
    predictive-maintenance-postgres            postgres:16                     "docker-entrypoint.s…"   postgres            3 days ago       Up 30 minutes (healthy)            0.0.0.0:15432->5432/tcp, [::]:15432->5432/tcp
    predictive-maintenance-prometheus          prom/prometheus:v2.55.1         "/bin/prometheus --c…"   prometheus          3 days ago       Up 29 minutes (healthy)            0.0.0.0:9090->9090/tcp, [::]:9090->9090/tcp
    predictive-maintenance-redis               redis:7                         "docker-entrypoint.s…"   redis               3 days ago       Up 30 minutes (healthy)            0.0.0.0:16379->6379/tcp, [::]:16379->6379/tcp


# Проверка canary gateway

Проверяем, что Nginx доступен на порту `8010` и проксирует запросы к inference service.

Endpoint: GET /health

Ожидаемый результат: JSON с status = ok и полем deployment_track, которое показывает какой backend ответил на запрос (stable или canary).


```bash
%%bash
cd "$PROJECT_ROOT"

curl -s http://127.0.0.1:8010/health
```

    {"status":"ok","model_loaded":true,"deployment_track":"stable","model_alias":"champion"}

# Проверка распределения трафика через canary

Проверяем, как Nginx-шлюз распределяет запросы между двумя версиями сервиса:

- `stable` — стабильная версия сервиса;
- `canary` — тестовая версия сервиса.

Скрипт `scripts/check_canary_distribution.sh` выполняет несколько запросов к endpoint `/health` через Nginx-шлюз и считает, какая версия сервиса ответила на запрос.


```bash
%%bash
cd "$PROJECT_ROOT"

N=50 scripts/check_canary_distribution.sh | grep deployment_track | sort | uniq -c
```

      50 {"status":"ok","model_loaded":true,"deployment_track":"stable","model_alias":"champion"}


# Переключение трафика в режим 50/50

Проверяем механизм canary переключения.

Скрипт `scripts/switch_canary_50_50.sh` меняет конфигурацию Nginx-шлюза так, чтобы примерно половина запросов шла в `stable`, а половина в `canary`.

После переключения повторно проверим распределение запросов.


```bash
%%bash
cd "$PROJECT_ROOT"

scripts/switch_canary_50_50.sh
sleep 5
N=50 scripts/check_canary_distribution.sh | grep deployment_track | sort | uniq -c
```

     Container predictive-maintenance-canary-gateway  Restarting
     Container predictive-maintenance-canary-gateway  Started


    Traffic switched to canary mode 50/50.
      25 {"status":"ok","model_loaded":true,"deployment_track":"canary","model_alias":"champion"}
      25 {"status":"ok","model_loaded":true,"deployment_track":"stable","model_alias":"champion"}


# Переключение 100% трафика на canary

Проверяем сценарий полного переключения трафика на canary версию сервиса.

Скрипт `scripts/switch_canary_100.sh` меняет конфигурацию Nginx-шлюза так, чтобы все запросы через порт `8010` направлялись в `canary`.


```bash
%%bash
cd "$PROJECT_ROOT"

scripts/switch_canary_100.sh
sleep 5
N=20 scripts/check_canary_distribution.sh | grep deployment_track | sort | uniq -c
```

     Container predictive-maintenance-canary-gateway  Restarting
     Container predictive-maintenance-canary-gateway  Started


    Traffic switched to 100% canary.
      20 {"status":"ok","model_loaded":true,"deployment_track":"canary","model_alias":"champion"}


# Rollback возврат трафика на stable

Проверяем сценарий отката.

Скрипт `scripts/rollback_canary_to_stable.sh` возвращает конфигурацию Nginx-шлюза в безопасный режим то есть все запросы снова направляются в `stable`.


```bash
%%bash
cd "$PROJECT_ROOT"

scripts/rollback_canary_to_stable.sh
sleep 5
N=20 scripts/check_canary_distribution.sh | grep deployment_track | sort | uniq -c
```

     Container predictive-maintenance-canary-gateway  Restarting
     Container predictive-maintenance-canary-gateway  Started


    Rollback completed: traffic switched back to 100% stable.
      20 {"status":"ok","model_loaded":true,"deployment_track":"stable","model_alias":"champion"}


# Итоговая проверка canary-контура после rollback

После проверки переключения трафика повторно проверяем состояние canary-контейнеров.

Важно чтобы после rollback оба сервиса `stable` и `canary` оставались работоспособными, а Nginx-шлюз продолжал отвечать на запросы.


```bash
%%bash
cd "$PROJECT_ROOT"

docker compose -f infra/docker-compose.canary.yml ps
curl -s http://127.0.0.1:8010/health
```

    NAME                                       IMAGE                           COMMAND                  SERVICE             CREATED          STATUS                             PORTS
    predictive-maintenance-airflow-scheduler   infra-airflow-scheduler         "/usr/bin/dumb-init …"   airflow-scheduler   36 minutes ago   Up 36 minutes                      8080/tcp
    predictive-maintenance-airflow-webserver   infra-airflow-webserver         "/usr/bin/dumb-init …"   airflow-webserver   36 minutes ago   Up 36 minutes (healthy)            0.0.0.0:8081->8080/tcp, [::]:8081->8080/tcp
    predictive-maintenance-api                 infra-api                       "uvicorn app.main:ap…"   api                 36 minutes ago   Up 36 minutes (healthy)            0.0.0.0:8000->8000/tcp, [::]:8000->8000/tcp
    predictive-maintenance-api-canary          infra-canary                    "uvicorn app.main:ap…"   canary              7 minutes ago    Up 7 minutes (healthy)             8000/tcp
    predictive-maintenance-api-stable          infra-stable                    "uvicorn app.main:ap…"   stable              7 minutes ago    Up 7 minutes (healthy)             8000/tcp
    predictive-maintenance-canary-gateway      nginx:1.27-alpine               "/docker-entrypoint.…"   canary-gateway      3 days ago       Up 56 seconds (health: starting)   0.0.0.0:8010->80/tcp, [::]:8010->80/tcp
    predictive-maintenance-grafana             grafana/grafana:11.3.1          "/run.sh"                grafana             3 days ago       Up 36 minutes (healthy)            0.0.0.0:3000->3000/tcp, [::]:3000->3000/tcp
    predictive-maintenance-mlflow              ghcr.io/mlflow/mlflow:v2.18.0   "/bin/sh -c 'pip ins…"   mlflow              3 days ago       Up 36 minutes (healthy)            0.0.0.0:5050->5000/tcp, [::]:5050->5000/tcp
    predictive-maintenance-node-exporter       prom/node-exporter:v1.8.2       "/bin/node_exporter"     node-exporter       3 days ago       Up 36 minutes (healthy)            0.0.0.0:9100->9100/tcp, [::]:9100->9100/tcp
    predictive-maintenance-postgres            postgres:16                     "docker-entrypoint.s…"   postgres            3 days ago       Up 36 minutes (healthy)            0.0.0.0:15432->5432/tcp, [::]:15432->5432/tcp
    predictive-maintenance-prometheus          prom/prometheus:v2.55.1         "/bin/prometheus --c…"   prometheus          3 days ago       Up 36 minutes (healthy)            0.0.0.0:9090->9090/tcp, [::]:9090->9090/tcp
    predictive-maintenance-redis               redis:7                         "docker-entrypoint.s…"   redis               3 days ago       Up 36 minutes (healthy)            0.0.0.0:16379->6379/tcp, [::]:16379->6379/tcp
    {"status":"ok","model_loaded":true,"deployment_track":"stable","model_alias":"champion"}

# Проверка CI/CD через GitHub Actions

GitHub Actions используется как CI-контур проекта.

В CI автоматически проверяется, что проект устанавливается и проходит тесты. Это дополняет локальную проверку `make test` то есть код проверяется не только на машине разработчика, но и в удалённом CI-окружении GitHub.


```bash
%%bash
cd "$PROJECT_ROOT"

ls -la .github/workflows
cat .github/workflows/ci.yml
```

    total 8
    drwxr-xr-x@ 3 perceivery  staff   96 May 27 14:45 [34m.[m[m
    drwxr-xr-x@ 3 perceivery  staff   96 May 27 14:45 [34m..[m[m
    -rw-r--r--@ 1 perceivery  staff  585 May 27 14:29 ci.yml
    name: CI
    
    on:
      push:
        branches:
          - main
      pull_request:
        branches:
          - main
    
    jobs:
      tests:
        name: Run tests
        runs-on: ubuntu-latest
    
        steps:
          - name: Checkout repository
            uses: actions/checkout@v4
    
          - name: Set up Python
            uses: actions/setup-python@v5
            with:
              python-version: "3.12"
    
          - name: Install dependencies
            run: |
              python -m pip install --upgrade pip setuptools wheel
              python -m pip install -r requirements.txt
    
          - name: Run tests
            run: |
              python -m pytest -q


CI workflow находится в файле `.github/workflows/ci.yml`.

Он запускается при `push` и `pull_request` в ветку `main`. В workflow выполняются установка Python 3.12, установка зависимостей из `requirements.txt` и запуск тестов через `pytest`.

<h3>СI</h3>
<img src="../screenshots/10_github_actions_success.png" alt="MLflow experiments" width="900">

# Проверка Ansible Infrastructure as Code

Ansible используется как Infrastructure as Code слой для развёртывания проекта на виртуальной машине.

Docker Compose описывает состав контейнеров, а Ansible описывает воспроизводимый процесс подготовки сервера и запуска проекта:

```text
пустая VM
-> установка системных пакетов
-> установка и запуск Docker
-> копирование проекта на VM
-> сборка Docker-образов
-> запуск MLOps-инфраструктуры
-> обучение и promotion модели
-> проверка health endpoints

Основные файлы Ansible-контура:
- ansible/inventory.ini
- ansible/group_vars/all.yml
- ansible/playbook.yml
- ansible/README.md
```


```bash
%%bash
cd "$PROJECT_ROOT"

ls -la ansible/
echo "----- group_vars -----"
ls -la ansible/group_vars/

python - <<'PY'
import yaml

for file in [
    "ansible/group_vars/all.yml",
    "ansible/playbook.yml",
]:
    with open(file, "r", encoding="utf-8") as f:
        yaml.safe_load(f)
    print(f"YAML OK: {file}")
PY
```

    total 32
    drwxr-xr-x@  6 perceivery  staff   192 May 27 18:38 [34m.[m[m
    drwxr-xr-x@ 31 perceivery  staff   992 May 31 00:00 [34m..[m[m
    -rw-------@  1 perceivery  staff  2522 May 27 16:17 README.md
    drwxr-xr-x@  3 perceivery  staff    96 May 27 18:37 [34mgroup_vars[m[m
    -rw-r--r--@  1 perceivery  staff   119 May 27 16:10 inventory.ini
    -rw-r--r--@  1 perceivery  staff  6066 May 27 18:09 playbook.yml
    ----- group_vars -----
    total 8
    drwxr-xr-x@ 3 perceivery  staff   96 May 27 18:37 [34m.[m[m
    drwxr-xr-x@ 6 perceivery  staff  192 May 27 18:38 [34m..[m[m
    -rw-r--r--@ 1 perceivery  staff  701 May 27 18:11 all.yml
    YAML OK: ansible/group_vars/all.yml
    YAML OK: ansible/playbook.yml


Фактический запуск на виртуальной машине выполняется командой:

```bash
ansible-playbook -i ansible/inventory.ini ansible/playbook.yml
```

# Дадим нагрузку на инференс


```bash
%%bash
cd "$PROJECT_ROOT"

echo "Starting inference load for 120 seconds..."
echo "Endpoint: /predict/from-feature-store"

end=$((SECONDS + 120))

while [ $SECONDS -lt $end ]; do
  for i in $(seq 1 20); do
    curl -s -X POST http://127.0.0.1:8000/predict/from-feature-store \
      -H "Content-Type: application/json" \
      -d '{"machine_id": 1}' >/dev/null &
  done

  wait
  sleep 1
done

echo "Inference load finished."

curl -s http://127.0.0.1:8000/metrics \
  | grep -E "^predict_requests_total|^predict_errors_total|^feature_retrieval_requests_total|^feature_retrieval_errors_total"
```

    Starting inference load for 120 seconds...
    Endpoint: /predict/from-feature-store
    Inference load finished.
    predict_requests_total 3472.0
    predict_errors_total 0.0
    feature_retrieval_requests_total 3471.0
    feature_retrieval_errors_total 0.0


<h3>Grafana dashboard</h3>
<img src="../screenshots/11_grafana_dashboard_after_load.png" alt="Grafana dashboard" width="900">

# Веб-интерфейсы для ручной проверки

После запуска сервисов доступны следующие веб-интерфейсы:

| Компонент | Адрес | Что проверить |
|---|---|---|
| FastAPI | `http://127.0.0.1:8000/docs` | Наличие endpoint-ов `/health`, `/model/info`, `/predict`, `/predict/from-feature-store`, `/metrics` |
| MLflow | `http://127.0.0.1:5050` | Эксперименты, запуски обучения, зарегистрированная модель `predictive-maintenance-model` |
| Airflow | `http://127.0.0.1:8081` | DAG `predictive_maintenance_training_pipeline` и последний запуск со статусом `success` |
| Prometheus targets | `http://127.0.0.1:9090/targets` | Targets `predictive-maintenance-api`, `node-exporter`, `prometheus` в состоянии `UP` |
| Prometheus rules | `http://127.0.0.1:9090/rules` | Правила `PredictiveMaintenanceHighLatency`, `PredictiveMaintenanceHighErrorRate`, `PredictiveMaintenanceApiDown`, `PredictiveMaintenanceFeatureRetrievalErrors` |
| Grafana | `http://127.0.0.1:3000` | Dashboard `Predictive Maintenance API` |
| Evidently report | `reports/evidently/data_drift_report.html` | HTML-отчёт по drift данных |
| Canary gateway | `http://127.0.0.1:8010/health` | Ответ от `stable` после rollback |

Логин и пароль для Airflow, Grafana:

```text
admin / admin
```

<h2>Скриншоты работающей системы</h2>

<h3>MLflow: эксперименты</h3>
<img src="../screenshots/01_mlflow_experiments.png" alt="MLflow experiments" width="900">

<h3>MLflow Model Registry: champion-модель</h3>
<img src="../screenshots/02_mlflow_model_registry_champion.png" alt="MLflow champion model" width="900">

<h3>Airflow: успешный запуск DAG</h3>
<img src="../screenshots/03_airflow_dag_success.png" alt="Airflow DAG success" width="900">

<h3>Prometheus targets</h3>
<img src="../screenshots/04_prometheus_targets.png" alt="Prometheus targets" width="900">

<h3>Prometheus rules</h3>
<img src="../screenshots/05_prometheus_rules1.png" alt="Prometheus rules" width="900">
<img src="../screenshots/05_prometheus_rules2.png" alt="Prometheus rules" width="900">

<h3>Grafana dashboard</h3>
<img src="../screenshots/06_grafana_dashboard1.png" alt="Grafana dashboard" width="900">
<img src="../screenshots/06_grafana_dashboard2.png" alt="Grafana dashboard" width="900">

<h3>FastAPI Swagger UI</h3>
<img src="../screenshots/07_fastapi_docs.png" alt="FastAPI docs" width="900">

<h3>Evidently drift report</h3>
<img src="../screenshots/08_evidently_report1.png" alt="Evidently drift report" width="900">
<img src="../screenshots/08_evidently_report2.png" alt="Evidently drift report" width="900">

<h3>Canary traffic switching</h3>
<img src="../screenshots/09_canary.png" alt="Canary traffic distribution" width="900">

