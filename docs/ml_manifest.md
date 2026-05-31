# ML-манифест проекта

## 1. Предыстория

Промышленное оборудование работает в условиях изменяющихся нагрузок, температуры, скорости вращения, крутящего момента, износа инструмента и других эксплуатационных факторов. Незапланированный отказ оборудования приводит к простою производства, затратам на аварийный ремонт, нарушению SLA и потере выручки.

Цель проекта — построить учебно-промышленный MLOps-прототип, который заранее оценивает риск отказа оборудования по телеметрическим признакам и демонстрирует полный воспроизводимый жизненный цикл ML-модели: подготовку данных, обучение, регистрацию модели, production-like inference, мониторинг, canary rollout и rollback.

## 2. Ценностное предложение

Проектируемая ML-система снижает риск незапланированного простоя оборудования за счёт раннего обнаружения потенциальных отказов.

Система создаёт ценность для бизнеса за счёт:

- раннего выявления оборудования с повышенным риском отказа;
- перехода от реактивного ремонта к профилактическому обслуживанию;
- снижения вероятности незапланированного downtime;
- уменьшения затрат на аварийное восстановление;
- повышения прозрачности состояния оборудования через технический, модельный и инфраструктурный мониторинг;
- безопасного обновления inference-сервиса через canary rollout и rollback.

## 3. Цели проекта

Ключевые цели проекта:

1. Построить воспроизводимый ML-пайплайн для задачи прогнозирования отказов оборудования.
2. Реализовать управление признаками через Feast Feature Store.
3. Использовать единые feature definitions для обучения и production-like inference.
4. Обеспечить обучение, оценку и регистрацию моделей через MLflow.
5. Реализовать model quality gate, предотвращающий promotion модели с недостаточным качеством.
6. Развернуть FastAPI-сервис для online-инференса.
7. Реализовать production-like endpoint, который получает online-признаки из Feast Redis Online Store.
8. Настроить мониторинг технических метрик, inference-метрик, feature retrieval и инфраструктуры.
9. Реализовать data drift monitoring через Evidently.
10. Реализовать canary gateway для безопасного переключения traffic между stable и canary inference instances.
11. Обеспечить воспроизводимое развёртывание проекта на облачной VM через Ansible и Docker Compose.

## 4. Решение

Система реализована как MLOps-система заявленного уровня зрелости 2.

Фактический сценарий работы:

1. Открытый AI4I 2020 Predictive Maintenance Dataset загружается воспроизводимым pipeline.
2. Data preparation pipeline формирует подготовленный датасет и parquet feature dataset.
3. Feast использует parquet-файл как offline source для исторических признаков.
4. Feast Redis Online Store используется для online retrieval признаков при inference.
5. PostgreSQL используется как backend store для MLflow и metadata database для Airflow.
6. Airflow DAG оркестрирует основные шаги ML lifecycle: загрузку данных, подготовку данных, построение feature dataset, применение Feast definitions, проверку Feature Store, обучение моделей и promotion модели.
7. MLflow логирует параметры, метрики и артефакты моделей, а MLflow Model Registry хранит модель с alias `champion`.
8. Model quality gate проверяет модельные метрики: recall, F1-score и ROC-AUC.
9. FastAPI обслуживает текущую champion-модель.
10. Endpoint `/predict` выполняет inference по признакам, переданным напрямую в request body.
11. Endpoint `/predict/from-feature-store` принимает `machine_id`, получает online-признаки из Feast Redis и применяет champion-модель.
12. Prometheus собирает technical API metrics, inference metrics, feature retrieval metrics и Node Exporter metrics.
13. Grafana визуализирует состояние сервиса и инфраструктуры.
14. Evidently формирует HTML-отчёт и JSON summary по data drift.
15. Nginx canary gateway распределяет traffic между stable и canary inference instances и поддерживает rollback на stable.
16. Deployment на облачную VM выполняется через Ansible playbook.

В продукт входит:

- подготовка данных;
- Feast Feature Store;
- Redis Online Store для online-признаков;
- MLflow Tracking и MLflow Model Registry;
- Airflow DAG для ML lifecycle;
- FastAPI inference service;
- production-like inference через `/predict/from-feature-store`;
- Prometheus/Grafana monitoring;
- Node Exporter для инфраструктурных метрик VM;
- Evidently drift report;
- model quality gate;
- canary deployment через Nginx weighted upstream;
- rollback scripts;
- воспроизводимое развёртывание через Docker Compose и Ansible;
- CI через GitHub Actions.


## 5. Осуществимость

Решение осуществимо в рамках учебного проекта, потому что задача имеет табличную структуру, а все ключевые компоненты могут быть воспроизведены через Docker Compose на одной VM.

Используемые ресурсы:

- открытый датасет AI4I 2020 Predictive Maintenance Dataset;
- Python training pipeline;
- Feast Feature Store;
- parquet как offline source для Feast;
- Redis как Feast Online Store;
- PostgreSQL как backend store для MLflow и metadata database для Airflow;
- MLflow для experiment tracking и Model Registry;
- Airflow для оркестрации;
- FastAPI для online inference;
- Nginx для canary gateway;
- Prometheus и Grafana для мониторинга;
- Node Exporter для инфраструктурных метрик;
- Evidently для drift report;
- Docker Compose для контейнерного контура;
- Ansible для подготовки VM и deployment;
- GitHub Actions для CI;
- облачная VM для демонстрационного развёртывания.

Основное ограничение проекта: система является учебно-промышленным прототипом. Она демонстрирует архитектуру и жизненный цикл ML-модели, но не подключается к реальному промышленному оборудованию и не получает реальные delayed labels из production.

## 6. Данные

В качестве обучающего набора используется AI4I 2020 Predictive Maintenance Dataset. Он содержит наблюдения по оборудованию и эксплуатационные признаки: температуру воздуха, температуру процесса, скорость вращения, крутящий момент, износ инструмента и тип оборудования.

Целевая переменная:

- `0` — нормальная работа оборудования;
- `1` — отказ оборудования.

Фактические источники данных в проекте:

- исходный открытый датасет AI4I 2020;
- подготовленный CSV dataset после preprocessing;
- parquet feature dataset для Feast offline source;
- online-признаки, материализованные в Redis;
- MLflow metrics и artifacts;
- Prometheus metrics inference service, feature retrieval и инфраструктуры;
- Evidently HTML/JSON drift report.

Процесс разметки:

- в датасете целевая переменная уже задана;
- в реальном production-сценарии метка отказа появилась бы позднее, после фактического события отказа или подтверждения нормальной работы оборудования;
- delayed labels и автоматическая online-оценка качества по новым размеченным данным в текущем прототипе не реализованы.

## 7. Метрики

Основная бизнес-метрика:

- снижение незапланированного времени простоя оборудования.

Дополнительные бизнес-метрики для production-сценария:

- доля предотвращённых отказов;
- доля оборудования высокого риска, проверенного до аварии;
- снижение числа аварийных ремонтов;
- снижение стоимости незапланированного обслуживания.

Основные ML-метрики:

- recall по классу отказа;
- precision по классу отказа;
- F1-score;
- ROC-AUC;
- false negative rate.

Фактические пороги model quality gate:

```text
recall  >= 0.80
f1      >= 0.60
roc_auc >= 0.85
```

Технические и сервисные метрики:

- API latency;
- p95 latency;
- error rate;
- uptime / health status;
- количество prediction requests;
- количество feature retrieval requests;
- feature retrieval error rate;
- feature retrieval latency;
- распределение risk levels;
- CPU и memory usage через Node Exporter.

## 8. Оценка качества модели

Offline-оценка качества выполняется на отложенной тестовой выборке.

Основной приоритет — recall по классу отказа. Это связано с тем, что пропуск реального отказа является наиболее дорогой ошибкой для бизнеса.

Дополнительно контролируются:

- precision, чтобы не создавать чрезмерное число ложных предупреждений;
- F1-score как баланс precision и recall;
- ROC-AUC как качество ранжирования объектов по риску;
- confusion matrix для анализа типов ошибок.

В текущей реализации online monitoring включает:

- technical API metrics;
- latency и error rate;
- feature retrieval metrics;
- distribution of risk levels;
- data drift report через Evidently;
- infrastructure metrics через Node Exporter.

Полноценная online-оценка качества по delayed labels не реализована и рассматривается как дальнейшее production-расширение.

## 9. Подбор модели

Подбор модели выполняется итеративно и логируется в MLflow.

Фактически реализованные модели-кандидаты:

- `logistic_regression_balanced`;
- `random_forest_balanced`.

Итеративный подход:

1. Обучить baseline-модель.
2. Зафиксировать параметры, метрики и артефакты в MLflow.
3. Обучить модель-кандидат.
4. Сравнить качество моделей по recall, F1-score и ROC-AUC.
5. Проверить model quality gate.
6. Зарегистрировать модель в MLflow Model Registry.
7. Продвинуть лучшую модель в alias `champion` только при выполнении требований качества.

Фактический результат текущего pipeline: Random Forest проходит quality gate и используется как champion-модель.

Gradient Boosting, CatBoost или XGBoost могут быть добавлены как дальнейшее расширение, но не являются обязательной частью текущей реализации.

## 10. Инференс

Система выполняет online inference через FastAPI.

Доступны два основных inference endpoint:

```text
POST /predict
POST /predict/from-feature-store
```

Endpoint `/predict` принимает полный набор признаков в request body и выполняет прямой inference champion-моделью.

Endpoint `/predict/from-feature-store` принимает только `machine_id`, получает online-признаки из Feast Redis Online Store и выполняет production-like inference champion-моделью из MLflow Model Registry.

Ответ inference service содержит:

- вероятность отказа;
- предсказанный класс;
- уровень риска;
- рекомендуемое действие;
- имя модели;
- alias активной модели.

Дополнительные service endpoints:

```text
GET /health
GET /model/info
GET /metrics
```

Endpoint `/health` возвращает статус сервиса, факт загрузки модели, deployment track и model alias. Эти поля используются для проверки stable/canary traffic distribution.

## 11. Обратная связь и MDD

Источники обратной связи и контроля в текущем прототипе:

- offline model metrics из MLflow;
- Prometheus metrics по inference service;
- Prometheus metrics по online feature retrieval;
- Prometheus/Node Exporter infrastructure metrics;
- Evidently data drift report;
- Airflow DAG run status;
- canary traffic distribution и rollback result.

В реальном production-сценарии дополнительно потребовались бы:

- фактические события отказа оборудования;
- подтверждения нормальной работы оборудования;
- delayed labels;
- prediction logs в долговременном хранилище;
- регулярная online-оценка качества production-модели.

MDD используется: да.

Архитектурные решения принимаются на основе метрик, статистических тестов и ADR-документов. Для анализа latency используется сравнение распределений времени отклика baseline/improved serving-сценариев, формулирование гипотез H0/H1, выбор Welch's t-test, p-value и фиксация решения в ADR.

Важно: latency не является прямой частью model quality gate в коде. Model quality gate проверяет recall, F1-score и ROC-AUC. Latency, error rate и feature retrieval success контролируются отдельно как technical SLI/SLO и учитываются при rollout/rollback serving-сервиса.

## 12. Управление проектом

Для реализации учебно-промышленного прототипа требуются следующие роли:

- ML Engineer — подготовка данных, обучение моделей, MLflow;
- MLOps Engineer — Docker Compose, Airflow, Feast, Ansible, CI;
- Backend Engineer — FastAPI inference service;
- Data Engineer — data pipelines и feature store;
- DevOps Engineer — облачное развёртывание и мониторинг.

В рамках индивидуальной работы роли совмещаются одним исполнителем.

Ожидаемые результаты проекта:

- GitHub/GitLab-репозиторий с кодом и документацией;
- работающий API-сервис в облаке;
- Docker Compose-инфраструктура;
- Ansible deployment на VM;
- MLflow Tracking и Model Registry;
- Airflow DAG для ML lifecycle;
- Feast Feature Store;
- Redis Online Store;
- FastAPI inference service;
- Nginx canary gateway;
- Prometheus/Grafana monitoring;
- Node Exporter infrastructure monitoring;
- Evidently drift monitoring;
- документы: ML-манифест, архитектура, SLI/SLO, ADR по MDD и архитектурным решениям.

Ориентировочные этапы:

1. Проектирование архитектуры и документации.
2. Подготовка данных и baseline-модели.
3. Реализация Feature Store.
4. Реализация MLflow и training pipeline.
5. Реализация FastAPI inference service.
6. Реализация Airflow DAG.
7. Реализация мониторинга.
8. Реализация canary gateway и rollback scripts.
9. Подготовка ADR, SLI/SLO и MDD-анализа.
10. Облачное развёртывание через Ansible.
11. Подготовка отчёта и скриншотов для защиты.
