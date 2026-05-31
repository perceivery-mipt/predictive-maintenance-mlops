# SLI/SLO для MLOps-системы прогнозирования отказов оборудования

## 1. Назначение документа

Документ фиксирует ключевые SLI и SLO для ML-системы predictive maintenance. Система прогнозирует риск отказа оборудования по сенсорным данным и используется для поддержки решений о профилактическом обслуживании.

SLI используются для измерения фактического состояния системы, а SLO задают целевые уровни качества. В проекте метрики разделены на четыре группы:

- сервисные SLI/SLO для online inference API;
- инфраструктурные SLI и alerts;
- ML quality gate для продвижения модели;
- data quality / drift monitoring.

Такое разделение важно, потому что не все метрики ML-системы являются Prometheus SLO. Latency, error rate и feature retrieval success выражаются через Prometheus-запросы. Recall, F1-score и ROC-AUC относятся к model quality gate в training pipeline. Drift данных контролируется отдельным Evidently-отчётом.

## 2. Сервисные SLI/SLO prediction service

Сервисные SLO описывают работу FastAPI prediction service в production-like online-контуре.

В проекте есть два inference endpoint:

```text
POST /predict
POST /predict/from-feature-store
```

Endpoint `/predict` принимает признаки напрямую в request body. Endpoint `/predict/from-feature-store` принимает `machine_id`, получает online-признаки из Feast Redis Online Store и затем выполняет prediction champion-моделью из MLflow Model Registry.

| Компонент | SLI | Prometheus-метрика | SLO | Alert / контроль |
|---|---|---|---|---|
| FastAPI inference service | Error rate prediction requests | `predict_errors_total / predict_requests_total` | не более 1% ошибок | `PredictiveMaintenanceHighErrorRate` |
| FastAPI inference service | p95 latency prediction requests | `predict_latency_seconds_bucket` | p95 latency ≤ 1 секунда | `PredictiveMaintenanceHighLatency` |
| Feast Redis online retrieval | Error rate online feature retrieval | `feature_retrieval_errors_total / feature_retrieval_requests_total` | не более 1% ошибок retrieval | `PredictiveMaintenanceFeatureRetrievalErrors` |
| Feast Redis online retrieval | Latency online feature retrieval | `feature_retrieval_latency_seconds_bucket` | контролируется как часть inference latency | Grafana / Prometheus query |
| FastAPI scrape availability | Доступность Prometheus target | `up{job="predictive-maintenance-api"}` | target должен быть доступен | `PredictiveMaintenanceApiDown` |

Файл Sloth-compatible SLO specification:

```text
docs/slo/predictive-maintenance-slo.yaml
```

В него включены event-based SLO:

```text
api-low-error-rate
api-low-latency
feature-retrieval-success
```

Доступность API через `up{job="predictive-maintenance-api"}` контролируется отдельным Prometheus alert rule, потому что `up` является gauge-сигналом, а не event counter.

Prometheus alert rules находятся в файле:

```text
infra/prometheus/rules/predictive-maintenance-alerts.yml
```

## 3. Инфраструктурные SLI и alerts

Инфраструктурный мониторинг нужен для контроля работоспособности контейнерного контура и виртуальной машины.

| Компонент | SLI | Метрика / проверка | Целевое состояние | Действие при нарушении |
|---|---|---|---|---|
| FastAPI | Health endpoint | `GET /health` | HTTP 200, `model_loaded=true` | Проверка логов API, MLflow Registry, загрузки модели |
| MLflow | Tracking server availability | `GET http://127.0.0.1:5050` | HTTP 200 | Проверка MLflow, PostgreSQL backend store, artifacts |
| Airflow | Webserver health | `GET /health` | HTTP 200, webserver доступен | Проверка scheduler/webserver/logs, DAG runs через UI или CLI |
| Prometheus | Health endpoint | `GET /-/healthy` | `Prometheus Server is Healthy` | Проверка config, rule files, targets |
| Grafana | Health endpoint | `GET /api/health` | database `ok` | Проверка provisioning и datasource |
| Node Exporter | Infrastructure metrics | `node_cpu_seconds_total` | метрика доступна в Prometheus | Проверка node-exporter target |
| Redis | Online Store availability | container healthcheck `redis-cli ping` | healthy | Перезапуск Redis, повторная materialization |
| PostgreSQL | DB availability | container healthcheck `pg_isready` | healthy | Проверка контейнера, volume, credentials |
| Canary gateway | Gateway health | `GET /health` на `:8010` | HTTP 200, backend отвечает | Проверка Nginx config, stable/canary services, rollback |

Node Exporter используется для сбора инфраструктурных метрик VM/container host. Пример проверки:

```bash
curl "http://127.0.0.1:9090/api/v1/query?query=node_cpu_seconds_total"
```

## 4. ML quality gate

ML quality gate используется для принятия решения о продвижении модели-кандидата в champion. Эти метрики не являются Prometheus SLO, потому что они считаются в offline evaluation / training pipeline.

| Метрика | Требование | Назначение |
|---|---|---|
| Recall по классу отказа | `recall >= 0.80` | Минимизировать пропуск реальных отказов |
| F1-score | `f1 >= 0.60` | Контролировать баланс precision/recall |
| ROC-AUC | `roc_auc >= 0.85` | Проверить общую разделяющую способность модели |

Главная ML-метрика — recall по классу отказа. В задаче predictive maintenance false negative является наиболее дорогой ошибкой, потому что пропущенный отказ может привести к простою оборудования.

Фактический лучший кандидат в текущем запуске:

```text
random_forest_balanced
recall    = 0.808824
precision = 0.539216
f1        = 0.647059
roc_auc   = 0.967528
```

Модель продвигается в MLflow Model Registry как `champion` только при прохождении model quality gate.

Latency, error rate и feature retrieval success не входят напрямую в кодовый model quality gate. Они контролируются отдельно как технические SLO production-сервиса и учитываются при rollout/rollback и эксплуатационных решениях.

## 5. Data quality и drift monitoring

Для контроля drift данных используется Evidently AI. Этот контур не является Prometheus SLO, потому что drift считается периодически по reference/current batch, а не на каждом API-запросе.

Скрипт:

```text
pipelines/check_data_drift.py
```

Артефакты:

```text
reports/evidently/data_drift_report.html
reports/evidently/data_drift_summary.json
```

Контролируемые показатели:

| Показатель | Назначение |
|---|---|
| `dataset_drift` | Общий признак drift на уровне датасета |
| `share_of_drifted_columns` | Доля признаков с индивидуальным drift |
| `number_of_drifted_columns` | Количество признаков с индивидуальным drift |

Фактический результат текущего запуска:

```text
dataset_drift = false
share_of_drifted_columns = 0.25
number_of_drifted_columns = 2
```

Интерпретация: на уровне всего датасета drift не зафиксирован, но 2 из 8 признаков показали индивидуальный drift. Это является сигналом для наблюдения и возможного анализа источников данных.

DQOps в текущей версии не используется как обязательный runtime-компонент. Для drift monitoring выбран Evidently AI как более лёгкая и воспроизводимая альтернатива, допустимая для задачи контроля drift данных.

## 6. Бизнесовые SLI/SLO

Бизнесовые SLI/SLO описывают целевые показатели промышленного внедрения. В текущем учебном контуре они не измеряются автоматически, потому что для этого нужны реальные production-события отказов, downtime и действия maintenance-команды.

| Бизнес-цель | SLI | Целевое значение | Требуемые production-данные |
|---|---|---|---|
| Снижение простоев | Доля незапланированного downtime | снижение не менее чем на 10% относительно baseline | журнал простоев оборудования |
| Раннее обнаружение отказов | Доля отказов, предсказанных заранее | не менее 70% отказов имеют предупреждение до события | реальные события отказов и timestamp прогнозов |
| Контроль стоимости обслуживания | Доля ложных предупреждений | не более 35% предупреждений являются ложными | результаты maintenance-проверок |
| Операционная применимость | Доля high-risk прогнозов, обработанных командой | не менее 90% high-risk прогнозов рассмотрены | журнал действий maintenance-команды |

В рамках проекта эти бизнесовые SLO используются как целевой контекст для выбора ML-метрик и архитектуры мониторинга.

## 7. Условия operational review, rollback и retraining

Нарушение перечисленных ниже условий является основанием для operational review, rollback canary traffic, повторного запуска training pipeline/DAG или отказа от promotion модели-кандидата.

В текущей реализации это не полностью автоматический control loop. Система предоставляет мониторинг, drift report, Airflow DAG, MLflow champion promotion и canary rollback, но решение о повторном запуске retraining или замене champion-модели принимается как эксплуатационное действие.

Условия, требующие реакции:

- recall по классу отказа на новой размеченной выборке ниже 0.75;
- ROC-AUC ниже 0.80;
- F1-score ниже 0.50;
- p95 latency endpoint `/predict` или `/predict/from-feature-store` выше 1 секунды в течение периода наблюдения;
- error rate prediction service выше 1%;
- error rate online feature retrieval из Feast Redis выше 1%;
- Evidently фиксирует существенный drift данных;
- нарушена схема признаков между Feast definitions и inference service.

Замена champion-модели выполняется не прямым удалением старой модели, а обновлением alias `champion` в MLflow Model Registry после обучения новой модели и прохождения model quality gate. Для безопасного переключения serving traffic используется canary gateway и rollback на stable.

## 8. Реакция системы на нарушения

При нарушении метрик возможны следующие сценарии:

| Тип нарушения | Пример | Реакция |
|---|---|---|
| Технический инцидент | API недоступен, высокий error rate | Проверка логов, restart, rollback |
| Деградация latency | p95 latency выше SLO | Анализ нагрузки, модели, feature retrieval и инфраструктуры; rollback при необходимости |
| Ошибка Feature Store | Рост `feature_retrieval_errors_total` | Проверка Redis, Feast registry, materialization |
| Деградация модели | Recall/F1/ROC-AUC ниже quality gate | Повторный запуск training pipeline/DAG, отказ от promotion текущего кандидата |
| Drift данных | Evidently обнаружил drift | Анализ источников данных, повторный запуск training pipeline при необходимости, обновление feature pipeline |

## 9. Связь SLI/SLO с архитектурой

SLI/SLO покрывают ключевые компоненты архитектуры уровня 2:

- FastAPI отвечает за production-инференс;
- Feast и Redis отвечают за online feature retrieval;
- parquet feature dataset используется как Feast offline source;
- PostgreSQL хранит backend state MLflow и metadata database Airflow;
- Airflow автоматизирует ML pipeline;
- MLflow управляет экспериментами и версиями моделей;
- Prometheus и Grafana отвечают за мониторинг;
- Node Exporter отвечает за инфраструктурные метрики;
- Evidently AI отвечает за drift monitoring;
- Nginx canary gateway отвечает за weighted traffic switching и rollback;
- model quality gate отвечает за безопасное продвижение новой champion-модели.

Таким образом, система контролируется на техническом, модельном и бизнесовом уровнях, а решение о переобучении или замене модели принимается на основе измеримых метрик и эксплуатационного анализа.
