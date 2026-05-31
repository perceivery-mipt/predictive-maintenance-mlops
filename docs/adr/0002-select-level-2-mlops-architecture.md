# ADR-0002: Выбор архитектуры ML-системы уровня 2

## Статус

Принято.

## Контекст

Итоговая работа требует спроектировать ML-систему, которая демонстрирует полный жизненный цикл модели: подготовку данных, построение признаков, обучение модели, проверку качества, регистрацию модели, сервинг, мониторинг и управляемую замену production-модели.

Для максимального уровня зрелости требуется система уровня 2. В рамках проекта это означает, что система должна включать:

- версионирование исходного кода;
- CI-пайплайн для проверки проекта;
- Feature Store;
- оркестратор ML-пайплайнов;
- систему управления экспериментами и реестр моделей;
- model quality gate для решения о продвижении модели;
- API-сервинг champion-модели;
- monitoring технических SLI, inference-метрик, feature retrieval и drift входных данных;
- механизм безопасного переключения inference traffic и rollback;
- воспроизводимое развёртывание на виртуальной машине;
- работающий облачный сервис с endpoint `/health`.

В текущей реализации автоматический production-control loop вида “drift/SLO violation -> automatic retraining -> automatic replacement” не реализуется полностью. Проект реализует воспроизводимый retraining/promotion pipeline, который может быть запущен повторно вручную или через Airflow. Новая модель становится `champion` только после прохождения quality gate.

## Решение

Для проекта выбрана архитектура ML-системы уровня 2 со следующими компонентами:

- GitHub — версионирование исходного кода;
- GitHub Actions — CI: установка зависимостей и запуск тестов;
- Ansible — подготовка VM и воспроизводимый deployment проекта;
- Docker Compose — описание и запуск микросервисного контура;
- Parquet feature dataset — offline source для Feast;
- Feast — Feature Store и единое описание признаков;
- Redis — online store для Feast;
- PostgreSQL — backend store для MLflow и metadata database для Airflow;
- Airflow — оркестратор ML-пайплайна;
- MLflow — experiment tracking и model registry;
- FastAPI — сервис online-инференса;
- Nginx canary gateway — weighted traffic switching между stable/canary API и rollback;
- Prometheus — сбор технических, сервисных и feature retrieval метрик;
- Grafana — визуализация метрик;
- Node Exporter — инфраструктурные метрики VM;
- Evidently — data drift report и JSON summary;
- model quality gate — правило продвижения модели в `champion`.

Высокоуровневый поток данных и моделей:

```text
Raw AI4I dataset
    ↓
Data preparation pipeline
    ↓
Parquet feature dataset
    ↓
Feast Feature Store
    ├── Offline source: Parquet
    └── Online store: Redis
    ↓
Training pipeline
    ↓
MLflow Tracking + Model Registry
    ↓
Model Quality Gate
    ↓
Champion model alias
    ↓
FastAPI prediction service
    ├── /predict
    └── /predict/from-feature-store
    ↓
Nginx canary gateway
    ├── stable API instance
    └── canary API instance
    ↓
Prometheus + Grafana monitoring
    ↓
Manual or scheduled retraining pipeline
    ↓
Quality gate and champion alias update
```

## Обоснование

Выбранная архитектура соответствует заявленному уровню зрелости 2, потому что покрывает не только обучение модели, но и production-like эксплуатацию: управление признаками, регистрацию модели, сервинг, мониторинг, canary rollout и воспроизводимый deployment на VM.

### Feature Store

Feast выбран как Feature Store, потому что он позволяет централизованно описывать признаки и использовать одни и те же feature definitions для обучения и online-инференса. Это снижает риск training-serving skew.

В текущей реализации offline source для Feast представлен parquet-файлом, который строится пайплайном подготовки данных. Online store реализуется на Redis, потому что inference-сервису нужен быстрый доступ к актуальным признакам по `machine_id`.

PostgreSQL в проекте не является Feast offline store. Он используется как backend store для MLflow и как metadata database для Airflow.

### Оркестратор

Airflow выбран как оркестратор, потому что жизненный цикл модели состоит из последовательности зависимых шагов: загрузка данных, подготовка данных, построение feature dataset, применение Feast definitions, проверка Feature Store, обучение моделей и promotion лучшей модели.

DAG демонстрирует воспроизводимый ML pipeline. При этом deployment через Ansible также запускает training/promotion pipeline напрямую, чтобы при развёртывании на чистой VM получить готовую champion-модель и работающий inference-сервис.

### Управление экспериментами и реестр моделей

MLflow используется как система управления экспериментами и реестр моделей. Это позволяет сохранять параметры обучения, метрики, артефакты и версии моделей.

В рамках проекта используется champion-подход: лучшая модель, прошедшая quality gate, регистрируется как `predictive-maintenance-model` и получает alias `champion`. Inference-сервис загружает модель из MLflow Model Registry по этому alias.

### Model Quality Gate

Модель-кандидат может быть продвинута в `champion` только при выполнении model quality gate:

- recall по классу отказа не ниже установленного порога;
- F1-score не ниже установленного порога;
- ROC-AUC не ниже установленного порога;
- решение о promotion фиксируется в MLflow Model Registry через alias `champion`.

Фактические пороги quality gate в проекте:

```text
recall  >= 0.80
f1      >= 0.60
roc_auc >= 0.85
```

Latency инференса не входит в model quality gate. Она контролируется отдельно как технический SLI/SLO сервиса через Prometheus/Grafana и используется при эксплуатационных решениях, включая canary rollout или rollback.

### Сервинг

FastAPI выбран для online-сервинга модели. Сервис предоставляет endpoints:

```text
GET  /health
GET  /model/info
POST /predict
POST /predict/from-feature-store
GET  /metrics
```

Endpoint `/predict` принимает полный набор признаков в request body. Endpoint `/predict/from-feature-store` принимает `machine_id`, получает признаки из Feast Redis Online Store и выполняет inference champion-моделью из MLflow Model Registry.

Endpoint `/health` возвращает статус загрузки модели, `deployment_track` и `model_alias`. Эти поля используются для проверки stable/canary backends.

### Canary deployment и rollback

Для безопасной демонстрации вывода новой версии inference service используется отдельный canary-контур на базе Docker Compose и Nginx.

Canary-контур включает:

```text
stable          — стабильная FastAPI instance
canary          — canary FastAPI instance
canary-gateway  — Nginx weighted upstream
```

Traffic переключается через Nginx-конфигурации:

```text
90/10
50/50
100% canary
rollback to stable
```

По умолчанию stable и canary могут использовать один и тот же alias `champion`, чтобы инфраструктурный механизм canary rollout можно было проверить независимо от наличия отдельного alias `challenger`. Для реального canary новой модели предусмотрены переменные окружения `STABLE_MODEL_ALIAS` и `CANARY_MODEL_ALIAS`.

### Monitoring

Prometheus и Grafana используются для мониторинга технических и сервисных метрик. FastAPI отдаёт метрики на `/metrics`.

В проекте контролируются:

- prediction request rate;
- prediction error rate;
- prediction latency;
- распределение `risk_level`;
- feature retrieval requests/errors/latency;
- availability сервисов;
- инфраструктурные метрики VM через Node Exporter;
- drift входных данных через Evidently report.

Важно: online-мониторинг истинного качества предсказаний по delayed ground truth в проекте не реализован, потому что в online inference нет поступающих истинных меток отказа. Качество модели оценивается в training/evaluation pipeline и логируется в MLflow, а drift входных данных контролируется отдельно через Evidently.

### Infrastructure as Code

Infrastructure as Code реализован связкой Docker Compose и Ansible.

Docker Compose описывает состав микросервисов и их связи:

```text
PostgreSQL
Redis
MLflow
FastAPI
Airflow
Prometheus
Node Exporter
Grafana
Nginx canary gateway
```

Ansible отвечает за подготовку виртуальной машины и воспроизводимое развёртывание проекта:

- установку системных пакетов;
- установку и запуск Docker;
- копирование проекта на VM;
- сборку Docker-образов;
- запуск core/full/canary инфраструктуры;
- запуск training/promotion pipeline;
- проверку health endpoints;
- smoke-test production-like inference через Feast Redis;
- проверку canary traffic distribution.

Kubernetes не выбран как обязательная часть основной реализации, потому что важнее обеспечить стабильную работу полного MLOps-контура на одной VM. При этом архитектура допускает дальнейшую миграцию inference-сервиса в Kubernetes для масштабирования, rolling update и rollback.

### CI

GitHub Actions используется как CI, а не как полноценный CD. Workflow выполняет установку зависимостей и запуск тестов. Deployment на VM выполняется отдельно через Ansible.

## Последствия

Принятое решение определяет структуру проекта:

- `app/` содержит FastAPI-сервис;
- `dags/` содержит DAG-файлы Airflow;
- `pipelines/` содержит скрипты подготовки данных, обучения, проверки Feature Store, drift monitoring и promotion модели;
- `feature_repo/` содержит Feast-репозиторий;
- `infra/` содержит Docker Compose, Nginx canary, Prometheus и Grafana конфигурации;
- `ansible/` содержит inventory-шаблон, group variables и playbook для VM deployment;
- `docs/` содержит архитектуру, манифест, SLI/SLO и ADR-документы;
- `reports/` содержит generated reports, включая Evidently drift report.

Система становится сложнее, чем простой ML-скрипт, но зато демонстрирует production-like жизненный цикл модели: feature management, training, model registry, quality gate, model serving, monitoring, canary rollout, rollback и reproducible cloud deployment.

## Альтернативы

### Только FastAPI + модель в pickle-файле

Этот вариант проще, но не соответствует уровню 2, потому что не содержит Feature Store, оркестратора, реестра моделей, quality gate, мониторинга и воспроизводимого deployment.

### Docker Compose без Feast

Этот вариант позволил бы развернуть сервис, но не закрыл бы требование Feature Store и не решал бы проблему согласованности признаков между обучением и inference.

### PostgreSQL как Feast Offline Store

Этот вариант рассматривался как более “production-like” offline store. Однако для работы выбран parquet offline source, потому что он проще, стабильнее для локального и VM-развёртывания и достаточно хорошо демонстрирует работу Feast definitions и online retrieval через Redis.

### Kubernetes как основной контур

Kubernetes ближе к промышленному deployment, но для данной работы повышает инфраструктурную сложность и риск нестабильного результата. Поэтому основной контур реализуется через Docker Compose и Ansible, а Kubernetes рассматривается как возможное дальнейшее развитие.

### Полностью автоматический retraining loop

Полностью автоматическая цепочка “drift/SLO violation -> retraining -> promotion -> traffic switch” является более зрелым production-паттерном, но для данной работы выбрана контролируемая реализация: drift и SLO мониторятся, retraining/promotion pipeline может быть запущен повторно, а новая модель продвигается только после прохождения quality gate.

## Итог

Выбрана архитектура ML-системы уровня 2 на базе Feast, Airflow, MLflow, FastAPI, Prometheus/Grafana, Node Exporter, PostgreSQL, Redis, Nginx canary gateway, GitHub Actions, Docker Compose и Ansible.

Архитектура покрывает production-like жизненный цикл модели: подготовку данных, управление признаками, обучение, регистрацию champion-модели, сервинг, monitoring, drift report, canary rollout, rollback и воспроизводимое развёртывание на виртуальной машине.
