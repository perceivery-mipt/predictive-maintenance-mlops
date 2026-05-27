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
- мониторинг сервиса и модели через Prometheus и Grafana;
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
| Мониторинг | Prometheus, Grafana | Технический и модельный мониторинг |
| Infrastructure as Code | Docker Compose | Воспроизводимое развертывание инфраструктуры |
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
  - /metrics
        ↓
Monitoring
  - Prometheus
  - Grafana
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
Airflow        — orchestration DAG
Prometheus     — сбор метрик API
Grafana        — dashboard мониторинга
```

## 4. Основные компоненты проекта

```text
app/
  main.py                         FastAPI-приложение
  model_loader.py                 загрузка champion-модели из MLflow Registry
  schemas.py                      Pydantic-схемы request/response

pipelines/
  download_data.py                воспроизводимая загрузка датасета
  prepare_data.py                 подготовка признаков
  build_feature_store_dataset.py  подготовка parquet-source для Feast
  check_feature_store.py          проверка offline и online retrieval в Feast
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
  Dockerfile.api                  Dockerfile для FastAPI
  Dockerfile.airflow              Dockerfile для Airflow
  requirements-airflow.txt        отдельные зависимости Airflow
  prometheus/prometheus.yml       конфигурация Prometheus
  grafana/                        provisioning Grafana datasource/dashboard

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
GET  /metrics
```

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

## 7. Порты сервисов

```text
FastAPI API       http://127.0.0.1:8000
MLflow UI         http://127.0.0.1:5050
PostgreSQL        localhost:15432
Redis             localhost:16379
Airflow UI        http://127.0.0.1:8081
Prometheus        http://127.0.0.1:9090
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

## 11. Monitoring

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
```

Prometheus scrape target:

```text
api:8000/metrics
```

Проверка Prometheus:

```bash
curl http://127.0.0.1:9090/-/healthy
curl "http://127.0.0.1:9090/api/v1/query?query=predict_requests_total"
```

Проверка Grafana:

```bash
curl http://127.0.0.1:3000/api/health
```

Grafana dashboard:

```text
Predictive Maintenance / Predictive Maintenance API
```

## 12. CI

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

## 13. Проверочные команды для защиты

Проверка API:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/model/info
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

Проверка Grafana:

```bash
curl http://127.0.0.1:3000/api/health
```

Проверка всех контейнеров:

```bash
docker compose -f infra/docker-compose.yml ps
```

## Жизненный цикл модели

1. Сырые сенсорные данные сохраняются в PostgreSQL.
2. Airflow запускает валидацию данных и построение признаков.
3. Feast хранит определения признаков и материализует признаки в Redis.
4. Training pipeline получает исторические признаки из Feast.
5. Модели-кандидаты обучаются и логируются в MLflow.
6. Evaluation pipeline сравнивает модель-кандидат с текущей champion-моделью.
7. Quality gate принимает решение о продвижении или отклонении модели.
8. FastAPI обслуживает текущую champion-модель.
9. Мониторинг отслеживает технические сбои, деградацию модели и drift данных.
10. При деградации качества запускается переобучение, и устаревшая модель заменяется новой валидированной моделью.

## Структура репозитория

```text
app/              FastAPI-сервис инференса
dags/             DAG-файлы Airflow
pipelines/        Скрипты загрузки данных, обучения, оценки и продвижения модели
src/              Общие Python-модули проекта
feature_repo/     Репозиторий Feast Feature Store
infra/            Docker Compose и конфигурации мониторинга
sql/              SQL-скрипты инициализации базы данных
docs/             Манифест, архитектура, SLI/SLO, ADR-документы
tests/            Unit- и API-тесты
data/             Локальные данные для разработки
models/           Локальные артефакты моделей
```

## Дополнение: Infrastructure as Code

Формальный слой Infrastructure as Code реализуется через Ansible и Docker Compose.

Docker Compose описывает состав микросервисов и их связи: PostgreSQL, Redis, MLflow, FastAPI, Airflow, Prometheus, Node Exporter и Grafana.

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

Для контроля деградации входных данных может использоваться Evidently AI или Deepchecks. В этом проекте рекомендуется использовать Evidently AI как более лёгкий инструмент для проверки drift без ручной настройки внешнего DQOps.

Целевая логика drift-контроля:

1. Reference dataset берётся из исторической части подготовленного датасета.
2. Current dataset берётся из более поздней части подготовленного датасета.
3. Evidently строит отчёт о drift по входным признакам.
4. Отчёт сохраняется в каталог `reports/`.
5. Airflow может запускать drift-check как отдельную task перед обучением или перед promotion модели.

Ожидаемая структура:

```text
reports/
  data_drift_report.html
  data_drift_report.json

pipelines/
  check_data_drift.py

docs/
  data_drift.md
```

Пример команды запуска:

```bash
python pipelines/check_data_drift.py
```

Проверочный результат:

```text
Data drift report was created.
HTML report: reports/data_drift_report.html
JSON report: reports/data_drift_report.json
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
```

Проверить успешный DAG run:

```bash
docker compose -f infra/docker-compose.yml exec airflow-scheduler \
  airflow dags list-runs -d predictive_maintenance_training_pipeline
```

Проверить API-метрики:

```bash
curl "http://127.0.0.1:9090/api/v1/query?query=predict_requests_total"
```

Проверить инфраструктурные метрики:

```bash
curl "http://127.0.0.1:9090/api/v1/query?query=node_cpu_seconds_total"
```

Проверить Grafana:

```bash
curl http://127.0.0.1:3000/api/health
```

Проверить Airflow:

```bash
curl http://127.0.0.1:8081/health
```

## Дополнение: рекомендуемые скриншоты для отчёта

1. `docker compose ps` со всеми сервисами.
2. Airflow UI с успешным DAG run.
3. MLflow UI с экспериментами и registered model.
4. FastAPI `/docs` или успешный `/predict`.
5. Prometheus targets: `api`, `node-exporter`, `prometheus` в состоянии `up`.
6. Grafana dashboard `Predictive Maintenance API`.
7. Git log с последовательными коммитами по компонентам.
