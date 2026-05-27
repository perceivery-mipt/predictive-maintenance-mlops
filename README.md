# Predictive Maintenance MLOps System

Итоговая работа по развертыванию ML-моделей: промышленный MLOps-контур для задачи предиктивного обслуживания промышленного оборудования.

Система предсказывает риск отказа оборудования по телеметрическим признакам: температура воздуха, температура процесса, скорость вращения, крутящий момент, износ инструмента и тип оборудования.

## Заявленный уровень зрелости ML-системы

В проекте заявлен уровень зрелости ML-системы 2.

Система включает:

- версионирование исходного кода с помощью Git;
- CI/CD с помощью GitHub Actions;
- Feature Store на базе Feast;
- offline-хранилище признаков в PostgreSQL;
- online-хранилище признаков в Redis;
- систему управления экспериментами и реестр моделей на базе MLflow;
- оркестрацию пайплайнов с помощью Airflow;
- сервинг модели через FastAPI;
- canary deployment inference service через Nginx weighted upstream;
- monitoring сервиса и модели через Prometheus и Grafana;
- infrastructure monitoring через Node Exporter;
- SLO as Code и Prometheus alert rules для latency, error rate и online feature retrieval;
- data drift monitoring через Evidently AI;
- Infrastructure as Code через Docker Compose и Ansible;
- quality gate для принятия решения о продвижении модели;
- логику переобучения и замены production-модели.

## Основные компоненты

| Компонент | Технология | Назначение |
|---|---|---|
| API-сервис | FastAPI | Онлайн-инференс модели |
| Feature Store | Feast | Единое управление признаками для обучения и инференса |
| Offline Store | PostgreSQL | Исторические признаки и исходные данные |
| Online Store | Redis | Быстрый доступ к online-признакам |
| Оркестратор | Airflow | Автоматизация ML-пайплайна |
| Управление экспериментами | MLflow | Логирование параметров, метрик и артефактов |
| Реестр моделей | MLflow Model Registry | Хранение версий моделей и champion/challenger-логика |
| API traffic switching | Nginx, Docker Compose | Canary rollout 90/10, 50/50, 100% и rollback |
| Мониторинг | Prometheus, Grafana | Технический и модельный мониторинг |
| Инфраструктурный мониторинг | Node Exporter | Метрики виртуальной машины и контейнерной инфраструктуры |
| Drift monitoring | Evidently AI | HTML-отчёт и JSON summary по data drift |
| Infrastructure as Code | Docker Compose, Ansible | Воспроизводимое развертывание инфраструктуры |
| CI/CD | GitHub Actions | Проверка, сборка и подготовка к деплою |

## 1. Бизнес-задача

Цель системы — заранее обнаруживать риск отказа промышленной машины и выдавать рекомендацию по действию:

- `low` — продолжить штатную эксплуатацию;
- `medium` — усилить мониторинг;
- `high` — запланировать обслуживание;
- `critical` — остановить машину и провести срочное обслуживание.

Такой сценарий полезен для производственных линий, где внеплановый простой оборудования приводит к финансовым потерям, нарушению SLA и росту операционных рисков.

## 2. Датасет

Используется открытый учебный датасет AI4I 2020 Predictive Maintenance Dataset.

Целевая переменная:

```text
machine_failure
```

Размер датасета после загрузки:

```text
10000 строк
14 исходных столбцов
```

После подготовки данных:

```text
10000 строк
19 столбцов
```

Класс отказов несбалансирован:

```text
0 — 9661 наблюдение
1 — 339 наблюдений
```

Поэтому в моделях используется балансировка классов, а главным бизнес-показателем является recall по классу отказа.

## 3. Архитектура системы

Фактическая архитектура проекта:

```text
Data download / preparation
        ↓
Feast Feature Store
  - offline source: parquet file
  - online store: Redis
        ↓
ML training pipeline
  - baseline model
  - MLflow experiment tracking
  - candidate comparison
  - quality gate
        ↓
MLflow Model Registry
  - registered model
  - champion alias
        ↓
FastAPI inference service
  - /health
  - /model/info
  - /predict
  - /predict/from-feature-store
  - /metrics
        ↓
Canary traffic switching
  - stable API instance
  - canary API instance
  - Nginx weighted upstream
  - rollback to stable
        ↓
Monitoring
  - Prometheus
  - Grafana
  - Node Exporter
        ↓
Data drift monitoring
  - Evidently HTML report
  - Evidently JSON summary
        ↓
Orchestration
  - Airflow DAG
```

Инфраструктура поднимается через Docker Compose:

```text
PostgreSQL     — MLflow backend store и Airflow metadata database
MLflow         — Tracking Server и Model Registry
Redis          — Feast online store
FastAPI        — online inference API
Nginx          — canary gateway для распределения traffic между stable и canary
Airflow        — orchestration DAG
Prometheus     — сбор метрик API и инфраструктуры
Node Exporter  — инфраструктурные метрики VM/container host
Grafana        — dashboard мониторинга
```

Формальный слой Infrastructure as Code реализуется через Docker Compose и Ansible: Docker Compose описывает микросервисный контур, а Ansible отвечает за подготовку виртуальной машины и воспроизводимый deployment.

## 4. Основные компоненты проекта

```text
app/
  main.py                         FastAPI-приложение
  model_loader.py                 загрузка champion-модели из MLflow Registry
  feature_store_loader.py         загрузка Feast FeatureStore для online retrieval
  schemas.py                      Pydantic-схемы request/response

pipelines/
  download_data.py                воспроизводимая загрузка датасета
  prepare_data.py                 подготовка признаков
  build_feature_store_dataset.py  подготовка parquet-source для Feast
  check_feature_store.py          проверка offline и online retrieval в Feast
  check_data_drift.py             Evidently data drift report pipeline
  train_baseline.py               baseline training
  train_mlflow.py                 обучение кандидатов с логированием в MLflow
  promote_model.py                promotion лучшей модели в champion

src/
  quality_gate.py                 reusable quality gate

feature_repo/
  feature_store.yaml              конфигурация Feast
  features.py                     Entity, FeatureView, FeatureService

dags/
  predictive_maintenance_training_dag.py
                                  Airflow DAG полного ML pipeline

infra/
  docker-compose.yml              инфраструктурный контур
  docker-compose.canary.yml       canary-контур stable/canary/gateway
  Dockerfile.api                  Dockerfile для FastAPI
  Dockerfile.airflow              Dockerfile для Airflow
  requirements-airflow.txt        отдельные зависимости Airflow
  nginx/                          Nginx configs для 90/10, 50/50, 100% canary и rollback
  prometheus/prometheus.yml       конфигурация Prometheus
  prometheus/rules/               Prometheus alert rules / SLO rules
  grafana/                        provisioning Grafana datasource/dashboard

scripts/
  switch_canary_90_10.sh          переключение traffic на 90% stable / 10% canary
  switch_canary_50_50.sh          переключение traffic на 50% stable / 50% canary
  switch_canary_100.sh            переключение traffic на 100% canary
  rollback_canary_to_stable.sh    rollback traffic на 100% stable
  check_canary_distribution.sh    проверка распределения traffic через /health

ansible/
  inventory.ini                   inventory для VM
  group_vars/all.yml              параметры deployment
  playbook.yml                    Ansible IaC deployment
  README.md                       инструкция по Ansible-развёртыванию

docs/
  adr/                            ADR-документы
  slo/                            Sloth-compatible SLO specification
  sli_slo.md                      описание SLI/SLO, quality gate и drift monitoring

tests/
  test_api.py                     API-тесты
```

## 5. Качество модели

В MLflow training pipeline обучаются две модели-кандидата:

```text
logistic_regression_balanced
random_forest_balanced
```

Quality gate:

```text
recall  >= 0.80
f1      >= 0.60
roc_auc >= 0.85
```

Фактический лучший кандидат:

```text
random_forest_balanced
recall    = 0.808824
precision = 0.539216
f1        = 0.647059
roc_auc   = 0.967528
```

Логистическая регрессия отклоняется quality gate из-за низкого F1, несмотря на высокий recall. Random Forest проходит quality gate и переводится в champion-версию в MLflow Model Registry.

## 6. API

FastAPI service предоставляет endpoints:

```text
GET  /health
GET  /model/info
POST /predict
POST /predict/from-feature-store
GET  /metrics
```

Endpoint `/predict` принимает полный набор признаков в request body.

Endpoint `/predict/from-feature-store` принимает только `machine_id`, получает online-признаки из Feast Redis Online Store и выполняет inference champion-моделью из MLflow Model Registry.

Endpoint `/health` дополнительно возвращает `deployment_track` и `model_alias`. Эти поля используются в canary-контуре для проверки, какой backend обработал запрос: `stable` или `canary`.

Пример запроса:

```bash
curl -X POST http://127.0.0.1:8000/predict \
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

Пример ответа:

```json
{
  "failure_probability": 0.01965044927029856,
  "prediction": 0,
  "risk_level": "low",
  "recommended_action": "continue_normal_operation",
  "model_name": "predictive-maintenance-model",
  "model_alias": "champion"
}
```

Пример запроса через Feast Online Store:

```bash
curl -X POST http://127.0.0.1:8000/predict/from-feature-store \
  -H "Content-Type: application/json" \
  -d '{"machine_id": 1}'
```

Пример ответа:

```json
{
  "failure_probability": 0.014700660952716337,
  "prediction": 0,
  "risk_level": "low",
  "recommended_action": "continue_normal_operation",
  "model_name": "predictive-maintenance-model",
  "model_alias": "champion"
}
```

## 7. Порты сервисов

```text
FastAPI API       http://127.0.0.1:8000
Canary Gateway    http://127.0.0.1:8010
MLflow UI         http://127.0.0.1:5050
PostgreSQL        localhost:15432
Redis             localhost:16379
Airflow UI        http://127.0.0.1:8081
Prometheus        http://127.0.0.1:9090
Node Exporter     http://127.0.0.1:9100
Grafana           http://127.0.0.1:3000
```

Airflow login:

```text
username: admin
password: admin
```

Grafana login:

```text
username: admin
password: admin
```

## 8. Быстрый запуск

Создать окружение и установить зависимости:

```bash
python3 -m venv .venv
source .venv/bin/activate
make install
```

Проверить тесты:

```bash
make test
```

Поднять базовую инфраструктуру:

```bash
make docker-up-core
```

Подготовить данные:

```bash
make download-data
make prepare-data
make build-feast-dataset
```

Применить Feast definitions и проверить Feature Store:

```bash
make feast-apply
make feast-check
```

Обучить модели в MLflow и продвинуть лучшую модель:

```bash
make train-mlflow
make promote
```

Поднять API:

```bash
make docker-up-api
```

Проверить сервисы:

```bash
make docker-ps
```

Проверить drift данных:

```bash
make drift-check
open reports/evidently/data_drift_report.html
```

## 9. Полный Docker Compose контур

Поднять все сервисы:

```bash
docker compose -f infra/docker-compose.yml up -d
```

Проверить статусы:

```bash
docker compose -f infra/docker-compose.yml ps
```

Ожидаемый результат: основные сервисы находятся в статусе `Up`, а критичные сервисы имеют healthcheck `healthy`.

## 10. Airflow orchestration

DAG:

```text
predictive_maintenance_training_pipeline
```

Состав DAG:

```text
download_data
→ prepare_data
→ build_feature_store_dataset
→ apply_feast_definitions
→ check_feature_store
→ train_models
→ promote_model
```

Запуск Airflow:

```bash
make airflow-init
make airflow-up
```

Запуск DAG:

```bash
make airflow-trigger
```

Проверка статуса DAG run:

```bash
docker compose -f infra/docker-compose.yml exec airflow-scheduler \
  airflow dags list-runs -d predictive_maintenance_training_pipeline
```

В рабочем запуске DAG должен завершиться со статусом:

```text
success
```

## 11. Canary deployment

Для демонстрации постепенного вывода новой версии inference service в production используется отдельный canary-контур:

```text
infra/docker-compose.canary.yml
```

Он поднимает три сервиса:

```text
stable          — стабильная версия FastAPI inference service
canary          — новая версия FastAPI inference service
canary-gateway  — Nginx gateway с weighted upstream
```

Nginx распределяет traffic между `stable` и `canary` по активному конфигу:

```text
infra/nginx/nginx.active.conf
```

Доступные режимы:

```text
90/10       90% stable, 10% canary
50/50       50% stable, 50% canary
100 canary  100% canary
rollback    100% stable
```

Запуск canary-контурa:

```bash
docker compose -f infra/docker-compose.canary.yml up -d --build
```

Проверка gateway:

```bash
curl http://127.0.0.1:8010/health
```

Проверка распределения traffic:

```bash
N=50 scripts/check_canary_distribution.sh | grep deployment_track | sort | uniq -c
```

Фактическая проверка 90/10:

```text
5  {"status":"ok","model_loaded":true,"deployment_track":"canary","model_alias":"champion"}
45 {"status":"ok","model_loaded":true,"deployment_track":"stable","model_alias":"champion"}
```

Переключение на 50/50:

```bash
scripts/switch_canary_50_50.sh
N=50 scripts/check_canary_distribution.sh | grep deployment_track | sort | uniq -c
```

Фактическая проверка 50/50:

```text
25 {"status":"ok","model_loaded":true,"deployment_track":"canary","model_alias":"champion"}
25 {"status":"ok","model_loaded":true,"deployment_track":"stable","model_alias":"champion"}
```

Переключение на 100% canary:

```bash
scripts/switch_canary_100.sh
N=20 scripts/check_canary_distribution.sh | grep deployment_track | sort | uniq -c
```

Фактическая проверка 100% canary:

```text
20 {"status":"ok","model_loaded":true,"deployment_track":"canary","model_alias":"champion"}
```

Rollback на stable:

```bash
scripts/rollback_canary_to_stable.sh
N=20 scripts/check_canary_distribution.sh | grep deployment_track | sort | uniq -c
```

Фактическая проверка rollback:

```text
20 {"status":"ok","model_loaded":true,"deployment_track":"stable","model_alias":"champion"}
```

Версии модели для stable и canary не захардкожены. Они задаются через переменные окружения:

```text
STABLE_MODEL_ALIAS
CANARY_MODEL_ALIAS
```

По умолчанию обе версии используют `champion`, чтобы canary-контур можно было поднять без отдельного MLflow alias `challenger`. Для реального canary новой модели можно запустить:

```bash
STABLE_MODEL_ALIAS=champion CANARY_MODEL_ALIAS=challenger \
  docker compose -f infra/docker-compose.canary.yml up -d --build
```

Если challenger-модель не проходит quality gate или после переключения нарушаются SLO, traffic возвращается на stable через `rollback_canary_to_stable.sh`.

## 12. Monitoring

FastAPI отдаёт Prometheus-метрики на endpoint:

```text
/metrics
```

Кастомные метрики:

```text
predict_requests_total
predict_errors_total
predict_latency_seconds
prediction_risk_level_total
feature_retrieval_requests_total
feature_retrieval_errors_total
feature_retrieval_latency_seconds
```

Prometheus scrape target:

```text
api:8000/metrics
node-exporter:9100/metrics
prometheus:9090/metrics
```

Prometheus alert rules:

```text
PredictiveMaintenanceHighLatency
PredictiveMaintenanceHighErrorRate
PredictiveMaintenanceApiDown
PredictiveMaintenanceFeatureRetrievalErrors
```

SLO as Code specification:

```text
docs/slo/predictive-maintenance-slo.yaml
```

Prometheus rules:

```text
infra/prometheus/rules/predictive-maintenance-alerts.yml
```

Проверка Prometheus:

```bash
curl http://127.0.0.1:9090/-/healthy
curl "http://127.0.0.1:9090/api/v1/query?query=predict_requests_total"
curl "http://127.0.0.1:9090/api/v1/query?query=feature_retrieval_requests_total"
curl "http://127.0.0.1:9090/api/v1/query?query=node_cpu_seconds_total"
curl "http://127.0.0.1:9090/api/v1/rules"
```

Проверка Grafana:

```bash
curl http://127.0.0.1:3000/api/health
```

Grafana dashboard:

```text
Predictive Maintenance / Predictive Maintenance API
```

## 13. CI

GitHub Actions workflow:

```text
.github/workflows/ci.yml
```

CI выполняет:

```text
checkout
setup Python 3.12
install dependencies
python -m pytest -q
```

Локально тесты запускаются так:

```bash
python -m pytest -q
```

Или через Makefile:

```bash
make test
```

## 14. Проверочные команды для защиты

Проверка API:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/model/info
curl -X POST http://127.0.0.1:8000/predict/from-feature-store \
  -H "Content-Type: application/json" \
  -d '{"machine_id": 1}'
```

Проверка canary gateway:

```bash
curl http://127.0.0.1:8010/health
N=50 scripts/check_canary_distribution.sh | grep deployment_track | sort | uniq -c
```

Проверка canary switching и rollback:

```bash
scripts/switch_canary_50_50.sh
N=50 scripts/check_canary_distribution.sh | grep deployment_track | sort | uniq -c

scripts/switch_canary_100.sh
N=20 scripts/check_canary_distribution.sh | grep deployment_track | sort | uniq -c

scripts/rollback_canary_to_stable.sh
N=20 scripts/check_canary_distribution.sh | grep deployment_track | sort | uniq -c
```

Проверка MLflow:

```bash
curl -I http://127.0.0.1:5050
```

Проверка Airflow:

```bash
curl http://127.0.0.1:8081/health
```

Проверка Prometheus target:

```bash
curl "http://127.0.0.1:9090/api/v1/targets"
```

Проверка Prometheus SLO rules:

```bash
curl "http://127.0.0.1:9090/api/v1/rules"
```

Проверка Grafana:

```bash
curl http://127.0.0.1:3000/api/health
```

Проверка всех контейнеров:

```bash
docker compose -f infra/docker-compose.yml ps
docker compose -f infra/docker-compose.canary.yml ps
```

Проверка Evidently drift report:

```bash
make drift-check
open reports/evidently/data_drift_report.html
cat reports/evidently/data_drift_summary.json
```

## Жизненный цикл модели

1. Сырые сенсорные данные сохраняются в PostgreSQL.
2. Airflow запускает валидацию данных и построение признаков.
3. Feast хранит определения признаков и материализует признаки в Redis.
4. Training pipeline получает исторические признаки из Feast.
5. Модели-кандидаты обучаются и логируются в MLflow.
6. Evaluation pipeline сравнивает модель-кандидат с текущей champion-моделью.
7. Quality gate принимает решение о продвижении или отклонении модели.
8. FastAPI обслуживает текущую champion-модель через прямой inference endpoint `/predict` и production-like endpoint `/predict/from-feature-store` с online feature retrieval из Feast Redis.
9. Canary gateway позволяет постепенно перевести traffic со stable API instance на canary API instance и выполнить rollback при нарушении SLO.
10. Мониторинг отслеживает технические сбои, latency, error rate, online feature retrieval, деградацию модели и drift данных.
11. При деградации качества запускается переобучение, и устаревшая модель заменяется новой валидированной моделью.

## Структура репозитория

```text
app/              FastAPI-сервис инференса
dags/             DAG-файлы Airflow
pipelines/        Скрипты загрузки данных, обучения, оценки, drift monitoring и продвижения модели
src/              Общие Python-модули проекта
feature_repo/     Репозиторий Feast Feature Store
infra/            Docker Compose, Nginx canary и конфигурации мониторинга
scripts/          Скрипты canary switching, rollback и проверок
ansible/          Infrastructure as Code deployment через Ansible
sql/              SQL-скрипты инициализации базы данных
docs/             Манифест, архитектура, SLI/SLO, ADR-документы
tests/            Unit- и API-тесты
data/             Локальные данные для разработки
models/           Локальные артефакты моделей
reports/          Генерируемые Evidently-отчёты drift monitoring
```

## Дополнение: Infrastructure as Code

Формальный слой Infrastructure as Code реализуется через Ansible и Docker Compose.

Docker Compose описывает состав микросервисов и их связи: PostgreSQL, Redis, MLflow, FastAPI, Airflow, Prometheus, Node Exporter, Grafana и canary gateway на базе Nginx.

Ansible отвечает за подготовку виртуальной машины и воспроизводимое развёртывание проекта: установку системных пакетов, установку Docker, копирование проекта, сборку образов, запуск инфраструктуры и проверку health endpoints.

Ожидаемая структура IaC-модуля:

```text
ansible/
  inventory.ini
  group_vars/
    all.yml
  playbook.yml
  README.md
```

Запуск развёртывания на VM:

```bash
ansible-playbook -i ansible/inventory.ini ansible/playbook.yml
```

Проект допускает развёртывание всех микросервисов на одной виртуальной машине. Ресурсы VM могут быть обоснованы суммарным потреблением контейнеров по команде:

```bash
docker stats --no-stream
```

## Дополнение: инфраструктурный мониторинг через Node Exporter

Для мониторинга инфраструктуры используется Prometheus Node Exporter.

Node Exporter поднимается отдельным контейнером:

```text
predictive-maintenance-node-exporter
```

Prometheus собирает с него системные метрики через scrape target:

```text
node-exporter:9100/metrics
```

Проверка Node Exporter:

```bash
curl http://127.0.0.1:9100/metrics | head
```

Проверка метрик Node Exporter через Prometheus:

```bash
curl "http://127.0.0.1:9090/api/v1/query?query=node_cpu_seconds_total"
```

Ожидаемый результат: Prometheus возвращает `status: success`, а поле `result` содержит значения метрики `node_cpu_seconds_total`.

## Дополнение: контроль drift данных

Для контроля деградации входных данных может использоваться Evidently AI или Deepchecks. В этом проекте используется Evidently AI как более лёгкий инструмент для проверки drift без ручной настройки внешнего DQOps.

Целевая логика drift-контроля:

1. Reference dataset берётся из исторической части подготовленного датасета.
2. Current dataset берётся из более поздней части подготовленного датасета.
3. Evidently строит отчёт о drift по входным признакам.
4. Отчёт сохраняется в каталог `reports/evidently/`.
5. Airflow может запускать drift-check как отдельную task перед обучением или перед promotion модели.

Фактическая структура:

```text
reports/evidently/
  data_drift_report.html
  data_drift_summary.json

pipelines/
  check_data_drift.py
```

Пример команды запуска:

```bash
python pipelines/check_data_drift.py
```

Или через Makefile:

```bash
make drift-check
```

Проверочный результат:

```text
Evidently data drift report was created.
HTML report: reports/evidently/data_drift_report.html
JSON summary: reports/evidently/data_drift_summary.json
```

Фактический результат текущего запуска:

```text
dataset_drift = false
share_of_drifted_columns = 0.25
number_of_drifted_columns = 2
```

## Дополнение: команды для демонстрации на защите

Проверить, что репозиторий чистый:

```bash
git status
```

Проверить тесты:

```bash
python -m pytest -q
```

Проверить контейнеры:

```bash
docker compose -f infra/docker-compose.yml ps
docker compose -f infra/docker-compose.canary.yml ps
```

Проверить успешный DAG run:

```bash
docker compose -f infra/docker-compose.yml exec airflow-scheduler \
  airflow dags list-runs -d predictive_maintenance_training_pipeline
```

Проверить API-метрики:

```bash
curl "http://127.0.0.1:9090/api/v1/query?query=predict_requests_total"
curl "http://127.0.0.1:9090/api/v1/query?query=feature_retrieval_requests_total"
```

Проверить инфраструктурные метрики:

```bash
curl "http://127.0.0.1:9090/api/v1/query?query=node_cpu_seconds_total"
```

Проверить Prometheus rules:

```bash
curl "http://127.0.0.1:9090/api/v1/rules"
```

Проверить Grafana:

```bash
curl http://127.0.0.1:3000/api/health
```

Проверить Airflow:

```bash
curl http://127.0.0.1:8081/health
```

Проверить production-like inference через Feast Redis:

```bash
curl -X POST http://127.0.0.1:8000/predict/from-feature-store \
  -H "Content-Type: application/json" \
  -d '{"machine_id": 1}'
```

Проверить canary traffic distribution:

```bash
N=50 scripts/check_canary_distribution.sh | grep deployment_track | sort | uniq -c
```

Проверить rollback:

```bash
scripts/rollback_canary_to_stable.sh
N=20 scripts/check_canary_distribution.sh | grep deployment_track | sort | uniq -c
```

## Дополнение: рекомендуемые скриншоты для отчёта

1. `docker compose ps` со всеми сервисами.
2. Airflow UI с успешным DAG run.
3. MLflow UI с экспериментами и registered model.
4. FastAPI `/docs` или успешный `/predict`.
5. FastAPI `/predict/from-feature-store` с online retrieval из Feast Redis.
6. Canary gateway: распределение 90/10, 50/50, 100% canary и rollback.
7. Prometheus targets: `api`, `node-exporter`, `prometheus` в состоянии `up`.
8. Prometheus rules с `PredictiveMaintenanceFeatureRetrievalErrors`.
9. Grafana dashboard `Predictive Maintenance API`.
10. Evidently HTML report `reports/evidently/data_drift_report.html`.
11. Git log с последовательными коммитами по компонентам.
