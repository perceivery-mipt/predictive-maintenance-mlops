# Predictive Maintenance MLOps System

Итоговая работа по развертыванию ML-моделей: промышленный MLOps-контур для задачи предиктивного обслуживания промышленного оборудования.

Система предсказывает риск отказа оборудования по телеметрическим признакам: температура воздуха, температура процесса, скорость вращения, крутящий момент, износ инструмента и тип оборудования.

## Публичный cloud deployment

Проект развёрнут на виртуальной машине через Ansible. Файл `ansible/inventory.ini` в репозитории оставлен как шаблон; для реального запуска в нём нужно указать IP виртуальной машины, SSH-пользователя и путь к приватному ключу.

### Публичные UI и endpoints

| Сервис | Публичная ссылка | Назначение |
|---|---|---|
| FastAPI health | http://158.160.13.227:8000/health | Проверка доступности API и загруженной champion-модели |
| FastAPI Swagger UI | http://158.160.13.227:8000/docs | Интерактивная документация API |
| MLflow UI | http://158.160.13.227:5050 | Эксперименты, метрики, артефакты и Model Registry |
| Airflow UI | http://158.160.13.227:8081 | Оркестрация ML-пайплайна |
| Prometheus UI | http://158.160.13.227:9090 | Метрики, targets и alert rules |
| Grafana UI | http://158.160.13.227:3000 | Dashboard мониторинга API и инфраструктуры |
| Canary gateway health | http://158.160.13.227:8010/health | Проверка Nginx canary gateway |

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

### Быстрая проверка облачного сервиса

```bash
curl http://158.160.13.227:8000/health

curl -X POST http://158.160.13.227:8000/predict/from-feature-store \
  -H "Content-Type: application/json" \
  -d '{"machine_id": 1}'

curl http://158.160.13.227:8010/health
```

Ожидаемый ответ production-like inference через Feast Redis и MLflow champion model:

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

## Заявленный уровень зрелости ML-системы

В проекте заявлен уровень зрелости ML-системы 2.

Система включает:

- версионирование исходного кода с помощью Git;
- CI с помощью GitHub Actions;
- воспроизводимый deployment на VM через Ansible;
- Feature Store на базе Feast;
- offline source для Feast на базе parquet-файла;
- online store признаков в Redis;
- PostgreSQL как backend store для MLflow и metadata database для Airflow;
- систему управления экспериментами и реестр моделей на базе MLflow;
- оркестрацию ML-пайплайна с помощью Airflow;
- сервинг модели через FastAPI;
- canary deployment inference service через Nginx weighted upstream;
- monitoring сервиса и модели через Prometheus и Grafana;
- infrastructure monitoring через Node Exporter;
- SLO as Code и Prometheus alert rules для latency, error rate, API availability и online feature retrieval;
- data drift monitoring через Evidently AI;
- Infrastructure as Code через Docker Compose и Ansible;
- quality gate для принятия решения о продвижении модели;
- повторяемую логику обучения, оценки и замены champion-модели после прохождения quality gate.

## Основные компоненты

| Компонент | Технология | Назначение |
|---|---|---|
| API-сервис | FastAPI | Онлайн-инференс модели |
| Feature Store | Feast | Единое управление признаками для обучения и инференса |
| Offline source | Parquet | Исторические признаки для Feast offline retrieval |
| Online Store | Redis | Быстрый доступ к online-признакам |
| Backend database | PostgreSQL | MLflow backend store и Airflow metadata database |
| Оркестратор | Airflow | Автоматизация ML-пайплайна |
| Управление экспериментами | MLflow | Логирование параметров, метрик и артефактов |
| Реестр моделей | MLflow Model Registry | Хранение версий моделей и champion-логика |
| API traffic switching | Nginx, Docker Compose | Canary rollout 90/10, 50/50, 100% и rollback |
| Мониторинг | Prometheus, Grafana | Технический и модельный мониторинг |
| Инфраструктурный мониторинг | Node Exporter | Метрики виртуальной машины и container host |
| Drift monitoring | Evidently AI | HTML-отчёт и JSON summary по data drift |
| Infrastructure as Code | Docker Compose, Ansible | Воспроизводимое развертывание инфраструктуры |
| CI | GitHub Actions | Автоматический запуск тестов при push и pull request |

## 1. Бизнес-задача

Цель системы — заранее обнаруживать риск отказа промышленной машины и выдавать рекомендацию по действию:

- `low` — продолжить штатную эксплуатацию;
- `medium` — усилить мониторинг;
- `high` — запланировать обслуживание;
- `critical` — остановить машину и провести срочное обслуживание.

Такой сценарий полезен для производственных линий, где внеплановый простой оборудования приводит к финансовым потерям, нарушению SLA и росту операционных рисков.

Главная бизнес-метрика проекта — снижение пропущенных отказов оборудования. Поэтому для ML-модели приоритетным показателем является recall по классу отказа.

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

Поэтому в моделях используется балансировка классов, а главным ML-показателем для business goal является recall по классу отказа.

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
        ↓
Infrastructure as Code
  - Docker Compose
  - Ansible VM deployment
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

Формальный слой Infrastructure as Code реализуется через Docker Compose и Ansible: Docker Compose описывает микросервисный контур, а Ansible отвечает за подготовку виртуальной машины, копирование проекта, сборку образов, запуск контейнеров и проверку health endpoints.

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
  docker-compose.yml              основной инфраструктурный контур
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
  export_service_report.sh        экспорт GitHub-readable отчёта из notebook в markdown

ansible/
  inventory.ini                   шаблон inventory для VM
  group_vars/all.yml              параметры deployment
  playbook.yml                    Ansible IaC deployment
  README.md                       инструкция по Ansible-развёртыванию

docs/
  adr/                            ADR-документы
  slo/                            Sloth-compatible SLO specification
  sli_slo.md                      описание SLI/SLO, quality gate и drift monitoring

tests/
  test_api.py                     API-тесты

reports/
  evidently/                      Evidently drift artifacts
  final/service_up_report.md      GitHub-readable service report
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

Endpoint `/health` дополнительно возвращает `deployment_track` и `model_alias`. Эти поля используются в canary-контуре для проверки, какой backend обработал запрос: `stable`, `canary` или одиночный API-контур `single`.

Пример локального запроса:

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

Локальные адреса при запуске на машине разработчика или внутри VM:

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

Для текущего cloud deployment вместо `127.0.0.1` используется публичный IP VM:

```text
158.160.13.227
```

## 8. Быстрый локальный запуск

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

## 10. Deployment на VM через Ansible

Ansible playbook выполняет полный воспроизводимый deployment на виртуальную машину:

1. устанавливает системные пакеты;
2. устанавливает и запускает Docker;
3. копирует проект на VM в `/opt/predictive-maintenance-mlops`;
4. собирает Docker-образы;
5. поднимает core-инфраструктуру;
6. запускает training pipeline и promotion champion-модели;
7. поднимает полный MLOps-контур;
8. поднимает canary gateway;
9. проверяет health endpoints;
10. выполняет smoke-test production-like inference через Feast Redis;
11. проверяет canary traffic distribution;
12. выводит статус контейнеров.

Запуск:

```bash
ansible-playbook -i ansible/inventory.ini ansible/playbook.yml
```

`ansible/inventory.ini` в репозитории является шаблоном:

```ini
[mlops]
mlops-vm ansible_host=YOUR_VM_IP ansible_user=ubuntu

[mlops:vars]
ansible_python_interpreter=/usr/bin/python3
```

Для реального запуска нужно заменить `YOUR_VM_IP`, `ansible_user` и при необходимости добавить `ansible_ssh_private_key_file`.

На VM с 4 GB RAM рекомендуется включить swap, поскольку одновременно работают Airflow, MLflow, Prometheus, Grafana, PostgreSQL, Redis, FastAPI и canary gateway.

## 11. Airflow orchestration

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

Запуск Airflow локально:

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

В Ansible deployment training pipeline запускается напрямую из playbook, чтобы deployment был самодостаточным и не зависел от ручного запуска DAG в UI.

## 12. Canary deployment

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

## 13. Monitoring

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

Prometheus scrape targets:

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

Dashboard содержит API-метрики, latency, request rate, distribution по risk level и infrastructure CPU usage через Node Exporter.

## 14. Drift monitoring

Для контроля деградации входных данных используется Evidently AI.

Логика drift-контроля:

1. reference dataset берётся из исторической части подготовленного датасета;
2. current dataset берётся из более поздней части подготовленного датасета;
3. Evidently строит отчёт о drift по входным признакам;
4. отчёт сохраняется в каталог `reports/evidently/`;
5. JSON summary используется как компактный machine-readable артефакт проверки.

Фактическая структура:

```text
reports/evidently/
  data_drift_report.html
  data_drift_summary.json

pipelines/
  check_data_drift.py
```

Запуск:

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

Drift-check реализован отдельным pipeline `pipelines/check_data_drift.py` и запускается при deployment/проверке проекта. Его можно включить в Airflow DAG как отдельную task перед обучением или promotion.

## 15. CI

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

## 16. MDD и ADR

Metrics Driven Development оформлен отдельным ноутбуком и ADR.

В проекте проведён статистический анализ latency для двух вариантов системы: baseline и candidate. В анализе есть два набора метрик, визуальное сравнение распределений, формулировка гипотез `H0` и `H1`, выбранный уровень значимости, статистический тест и итоговое архитектурное решение.

ADR фиксирует выбранный тест, p-value, вывод по гипотезам и решение о принятии или отклонении архитектурного изменения.

## 17. Жизненный цикл модели

1. Сырые сенсорные данные загружаются воспроизводимым pipeline.
2. Подготовленные признаки сохраняются как parquet offline source для Feast.
3. Feast хранит определения признаков и материализует online-признаки в Redis.
4. Training pipeline получает исторические признаки и обучает модели-кандидаты.
5. Модели-кандидаты логируются в MLflow.
6. Evaluation pipeline сравнивает кандидатов по ML-метрикам.
7. Quality gate принимает решение о продвижении или отклонении модели.
8. Лучшая валидированная модель регистрируется в MLflow Model Registry и получает alias `champion`.
9. FastAPI обслуживает текущую champion-модель через `/predict` и production-like endpoint `/predict/from-feature-store` с online feature retrieval из Feast Redis.
10. Canary gateway позволяет постепенно перевести traffic со stable API instance на canary API instance и выполнить rollback при нарушении SLO.
11. Prometheus, Grafana и Node Exporter отслеживают техническое состояние сервиса и инфраструктуры.
12. Evidently drift report фиксирует деградацию входных данных.
13. При обнаружении drift или деградации качества retraining pipeline может быть запущен повторно; новая модель заменяет champion только после прохождения quality gate.

## 18. Проверочные команды для защиты

Проверка API:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/model/info
curl -X POST http://127.0.0.1:8000/predict/from-feature-store \
  -H "Content-Type: application/json" \
  -d '{"machine_id": 1}'
```

Проверка публичного cloud deployment:

```bash
curl http://158.160.13.227:8000/health
curl -I http://158.160.13.227:8000/docs
curl -X POST http://158.160.13.227:8000/predict/from-feature-store \
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

Проверка Ansible deployment:

```bash
ansible -i ansible/inventory.ini mlops -m ping
ansible-playbook -i ansible/inventory.ini ansible/playbook.yml --syntax-check
ansible-playbook -i ansible/inventory.ini ansible/playbook.yml
```

## 19. Структура репозитория

```text
app/              FastAPI-сервис инференса
dags/             DAG-файлы Airflow
pipelines/        Скрипты загрузки данных, обучения, оценки, drift monitoring и продвижения модели
src/              Общие Python-модули проекта
feature_repo/     Репозиторий Feast Feature Store
infra/            Docker Compose, Nginx canary и конфигурации мониторинга
scripts/          Скрипты canary switching, rollback, export отчёта и проверок
ansible/          Infrastructure as Code deployment через Ansible
sql/              SQL-скрипты инициализации базы данных
docs/             Манифест, архитектура, SLI/SLO, ADR-документы
tests/            Unit- и API-тесты
data/             Локальные данные для разработки
models/           Локальные артефакты моделей
reports/          Evidently-отчёты и финальный GitHub-readable service report
```

## 20. Финальный отчёт

GitHub-readable версия отчёта находится в:

```text
reports/final/service_up_report.md
```

Исходный исполняемый notebook находится в:

```text
notebooks/service_up_report.ipynb
```

Markdown-отчёт генерируется из notebook командой:

```bash
scripts/export_service_report.sh
```
