# Архитектура MLOps-системы для прогнозирования отказов оборудования

## 1. Общее описание

Проект реализует MLOps-систему для задачи predictive maintenance: прогнозирования риска отказа промышленного оборудования по сенсорным и эксплуатационным признакам.

Система демонстрирует заявленный уровень зрелости ML-системы 2: она покрывает не только обучение модели, но и воспроизводимый deployment, online inference, управление версиями моделей, Feature Store, orchestration, мониторинг, quality gate, canary rollout и rollback.

Архитектура поддерживает:

- загрузку и подготовку данных;
- построение признаков;
- повторное использование признаков через Feast Feature Store;
- обучение моделей-кандидатов;
- логирование экспериментов и артефактов в MLflow;
- регистрацию модели и работу с alias `champion`;
- model quality gate по ML-метрикам;
- online-сервинг модели через FastAPI;
- production-like inference через Feast Redis Online Store;
- canary deployment через Nginx weighted upstream;
- технический мониторинг через Prometheus и Grafana;
- инфраструктурный мониторинг через Node Exporter;
- drift monitoring через Evidently AI;
- воспроизводимое развёртывание на VM через Ansible и Docker Compose.

## 2. Бизнес-контекст

Незапланированные отказы оборудования приводят к простою производства, финансовым потерям, нарушению SLA и росту операционных рисков.

Цель системы — заранее выявлять оборудование с повышенным риском отказа и выдавать рекомендацию по действию:

- `low` — продолжить штатную эксплуатацию;
- `medium` — усилить мониторинг;
- `high` — запланировать обслуживание;
- `critical` — остановить машину и провести срочное обслуживание.

Основная бизнес-метрика — снижение незапланированного времени простоя оборудования. В рамках проекта она фиксируется как целевая бизнес-метрика, а фактическая проверка качества модели выполняется через offline ML-метрики и технические SLI/SLO сервиса.

## 3. ML-постановка задачи

Задача формулируется как бинарная классификация:

- `0` — нормальная работа оборудования;
- `1` — отказ оборудования или высокий риск отказа.

Используется открытый датасет AI4I 2020 Predictive Maintenance Dataset.

Главный приоритет качества модели — `recall` по классу отказа. Ложноотрицательная ошибка означает, что реальный отказ не был предсказан, и оборудование может выйти из строя без профилактического обслуживания.

Дополнительно контролируются:

- `precision`, потому что избыток ложных предупреждений увеличивает стоимость обслуживания;
- `F1-score`, как баланс между precision и recall;
- `ROC-AUC`, как интегральная метрика ранжирования риска.

Фактический model quality gate использует пороги:

```text
recall  >= 0.80
f1      >= 0.60
roc_auc >= 0.85
```

Latency не входит напрямую в model quality gate. Она контролируется отдельно как технический SLI/SLO production-сервиса и используется в MDD-решении о serving-архитектуре.

## 4. Высокоуровневая архитектура

Фактический поток данных и модели:

```text
AI4I raw dataset
    ↓
Data preparation pipeline
    ↓
Prepared feature dataset
    ↓
Feast Feature Store
    ├── Offline source: parquet file
    └── Online store: Redis
    ↓
Training pipeline
    ↓
MLflow Tracking + MLflow Model Registry
    ↓
Model quality gate
    ↓
MLflow registered model with alias champion
    ↓
FastAPI inference service
    ├── /predict
    └── /predict/from-feature-store
    ↓
Canary gateway
    ├── stable API instance
    ├── canary API instance
    └── Nginx weighted upstream / rollback
    ↓
Monitoring
    ├── Prometheus
    ├── Grafana
    └── Node Exporter
    ↓
Drift monitoring
    ├── Evidently HTML report
    └── Evidently JSON summary
    ↓
Manual or scheduled retraining pipeline
```

Инфраструктура разворачивается на виртуальной машине через Ansible. Docker Compose описывает контейнерный контур, а Ansible готовит VM, копирует проект, собирает Docker-образы, запускает сервисы и проверяет health endpoints.

## 5. Компоненты системы

### 5.1 Data pipeline

Data pipeline реализован в каталоге `pipelines/`.

Основные шаги:

- `download_data.py` — загрузка AI4I 2020 dataset;
- `prepare_data.py` — подготовка признаков и target;
- `build_feature_store_dataset.py` — подготовка parquet-файла для Feast offline source;
- `check_feature_store.py` — проверка offline/online retrieval;
- `train_mlflow.py` — обучение моделей-кандидатов и логирование в MLflow;
- `promote_model.py` — выбор лучшей модели и назначение alias `champion`;
- `check_data_drift.py` — построение Evidently drift report.

Подготовленные данные сохраняются в файловую структуру проекта (`data/`, `feature_repo/data/`). Feast offline source в текущей реализации основан на parquet-файле, а не на PostgreSQL.

### 5.2 PostgreSQL

PostgreSQL используется как инфраструктурное хранилище для сервисов MLOps-контура.

Фактические роли PostgreSQL:

- backend store для MLflow Tracking Server;
- metadata database для Airflow.

PostgreSQL не является Feast offline store в текущей реализации. Исторические признаки для Feast offline retrieval берутся из parquet-файла.

### 5.3 Feast Feature Store

Feast используется как Feature Store для централизованного описания признаков.

Фактическая конфигурация:

- entity: `machine`;
- feature definitions описаны в `feature_repo/features.py`;
- offline source: parquet-файл с подготовленными признаками;
- online store: Redis;
- production-like inference endpoint использует Feast Redis Online Store для получения признаков по `machine_id`.

Использование Feast снижает риск training-serving skew, потому что одни и те же feature definitions используются в training pipeline и в online inference path.

### 5.4 Redis

Redis используется как online store для Feast.

FastAPI endpoint `/predict/from-feature-store` принимает `machine_id`, получает online-признаки из Feast Redis Online Store и затем применяет champion-модель из MLflow Model Registry.

Дополнительно для online retrieval собираются Prometheus-метрики:

```text
feature_retrieval_requests_total
feature_retrieval_errors_total
feature_retrieval_latency_seconds
```

### 5.5 Airflow

Airflow используется как оркестратор ML-пайплайна.

Основной DAG:

```text
predictive_maintenance_training_pipeline
```

Фактическая последовательность шагов DAG:

```text
download_data
→ prepare_data
→ build_feature_store_dataset
→ apply_feast_definitions
→ check_feature_store
→ train_models
→ promote_model
```

Drift-check реализован отдельным pipeline `pipelines/check_data_drift.py`. Его можно запускать отдельно при проверке проекта или включить в DAG как дальнейшее развитие.

### 5.6 MLflow

MLflow используется как система управления экспериментами и Model Registry.

В MLflow логируются:

- параметры моделей;
- ML-метрики;
- артефакты моделей;
- версии обученных моделей.

Фактически обучаются две модели-кандидата:

```text
logistic_regression_balanced
random_forest_balanced
```

Лучшая модель, прошедшая quality gate, регистрируется как:

```text
predictive-maintenance-model
```

и получает alias:

```text
champion
```

FastAPI загружает активную модель из MLflow Model Registry по alias `champion`.

### 5.7 Model quality gate

Model quality gate предотвращает продвижение модели, которая не удовлетворяет минимальным требованиям качества.

Фактические критерии:

```text
recall  >= 0.80
f1      >= 0.60
roc_auc >= 0.85
```

Если модель-кандидат не проходит quality gate, она не назначается champion. Если проходит, pipeline promotion назначает её alias `champion` в MLflow Model Registry.

Latency, error rate и availability контролируются отдельно как технические SLI/SLO через Prometheus/Grafana и учитываются при эксплуатационных решениях о rollout.

### 5.8 FastAPI prediction service

FastAPI обслуживает текущую champion-модель.

Сервис предоставляет endpoints:

```text
GET  /health
GET  /model/info
POST /predict
POST /predict/from-feature-store
GET  /metrics
```

Endpoint `/predict` принимает полный набор признаков в request body и выполняет прямой inference.

Endpoint `/predict/from-feature-store` принимает только `machine_id`, получает online-признаки из Feast Redis Online Store и выполняет production-like inference champion-моделью из MLflow Model Registry.

Endpoint `/health` возвращает статус сервиса, факт загрузки модели, deployment track и model alias. Это используется также в canary-контуре для проверки, какой backend обработал запрос.

Ответ prediction endpoint содержит:

- вероятность отказа;
- предсказанный класс;
- уровень риска;
- рекомендуемое действие;
- имя модели;
- alias модели.

### 5.9 Canary deployment

Canary deployment реализован отдельным Docker Compose контуром:

```text
infra/docker-compose.canary.yml
```

Он поднимает:

- `stable` — стабильную FastAPI instance;
- `canary` — canary FastAPI instance;
- `canary-gateway` — Nginx gateway с weighted upstream.

Traffic switching реализован через Nginx-конфиги и shell-скрипты:

```text
scripts/switch_canary_90_10.sh
scripts/switch_canary_50_50.sh
scripts/switch_canary_100.sh
scripts/rollback_canary_to_stable.sh
scripts/check_canary_distribution.sh
```

Поддерживаются режимы:

- 90% stable / 10% canary;
- 50% stable / 50% canary;
- 100% canary;
- rollback на 100% stable.

В текущей демонстрационной конфигурации stable и canary могут использовать один и тот же alias `champion`, чтобы canary-контур можно было поднять без отдельного alias `challenger`. Для реального canary новой модели можно задать разные alias через переменные окружения `STABLE_MODEL_ALIAS` и `CANARY_MODEL_ALIAS`.

### 5.10 Prometheus, Grafana и Node Exporter

Prometheus собирает технические и сервисные метрики:

- количество prediction requests;
- количество prediction errors;
- latency prediction endpoints;
- распределение предсказанных risk levels;
- количество feature retrieval requests;
- feature retrieval errors;
- feature retrieval latency;
- инфраструктурные метрики VM через Node Exporter.

FastAPI отдаёт метрики на endpoint:

```text
/metrics
```

Node Exporter отдаёт инфраструктурные метрики на endpoint:

```text
:9100/metrics
```

Grafana используется для визуализации Prometheus-метрик. Dashboard проекта показывает состояние API, latency, error rate, feature retrieval и распределение risk levels. Инфраструктурные CPU/RAM-метрики доступны через Node Exporter.

### 5.11 Evidently drift monitoring

Drift monitoring реализован через Evidently AI.

Pipeline:

```text
pipelines/check_data_drift.py
```

создаёт:

```text
reports/evidently/data_drift_report.html
reports/evidently/data_drift_summary.json
```

Drift-check не является автоматическим блокирующим promotion gate в текущей реализации. Он используется как отдельный диагностический отчёт и может быть включён в Airflow DAG или release process как дальнейшее развитие.

## 6. CI и deployment

### 6.1 CI

GitHub Actions используется как CI, а не как полноценный CD.

Workflow:

```text
.github/workflows/ci.yml
```

выполняет:

- checkout репозитория;
- setup Python 3.12;
- установку зависимостей;
- запуск тестов через `pytest`.

Автоматический deployment на VM из GitHub Actions в текущей реализации не выполняется.

### 6.2 Deployment на VM

Deployment выполняется через Ansible:

```bash
ansible-playbook -i ansible/inventory.ini ansible/playbook.yml
```

Ansible отвечает за:

- установку системных пакетов;
- установку и запуск Docker;
- копирование проекта на VM;
- сборку Docker-образов;
- запуск core-инфраструктуры;
- запуск training pipeline и promotion champion-модели;
- запуск полного Docker Compose контура;
- запуск canary gateway;
- проверку health endpoints;
- smoke-test production-like inference.

Docker Compose отвечает за описание и запуск микросервисов.

Файл `ansible/inventory.ini` в репозитории содержит шаблон. Для реального deployment нужно указать IP VM, SSH-пользователя и путь к приватному ключу локально.

## 7. Infrastructure as Code

IaC реализован связкой Docker Compose и Ansible.

Docker Compose описывает сервисы:

- PostgreSQL;
- Redis;
- MLflow;
- FastAPI API;
- Airflow webserver;
- Airflow scheduler;
- Prometheus;
- Grafana;
- Node Exporter;
- stable/canary API instances;
- Nginx canary gateway.

Ansible описывает процедуру воспроизводимого deployment на VM.

Критичные сервисы имеют healthcheck. Развёрнутый API предоставляет endpoint `/health` со статусом HTTP 200. Canary gateway также имеет healthcheck на `/health` и после исправления использует `127.0.0.1`, чтобы избежать проблемы IPv6 localhost внутри контейнера.

## 8. Логика замены модели

Production-модель рассматривается как champion-модель. Новая обученная модель рассматривается как candidate/challenger.

Candidate становится champion только если проходит model quality gate:

1. `recall` по классу отказа не ниже установленного порога;
2. `F1-score` не ниже установленного порога;
3. `ROC-AUC` не ниже установленного порога;
4. promotion фиксируется в MLflow Model Registry через alias `champion`.

Технические SLO, включая latency, error rate и успешность online feature retrieval, контролируются отдельно через Prometheus/Grafana. Если serving-контур нарушает SLO, такая версия не должна считаться готовой к rollout без дополнительной оптимизации, даже если offline ML-метрики хорошие.

Canary gateway позволяет постепенно направлять traffic на новую API instance и выполнить rollback на stable при нарушении SLO или ошибках.

## 9. Ограничения текущей реализации

Текущая реализация демонстрирует полный MLOps-контур, но имеет осознанные ограничения:

- автоматический CD из GitHub Actions на VM не реализован;
- automatic retraining trigger от Prometheus/Evidently не реализован;
- delayed ground truth labels для online monitoring качества предсказаний не поступают автоматически;
- drift-check реализован как отдельный Evidently pipeline, а не как обязательная task внутри Airflow DAG;
- stable и canary в демонстрации могут использовать один и тот же alias `champion`.

Эти ограничения не нарушают цели проекта, потому что реализованы ключевые компоненты MLOps-системы: Feature Store, Model Registry, orchestration, API serving, monitoring, SLO rules, canary deployment, rollback и воспроизводимый deployment на VM.
