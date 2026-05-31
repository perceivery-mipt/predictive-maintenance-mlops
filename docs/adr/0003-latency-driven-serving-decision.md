# ADR-0003: Принятие архитектурного решения на основе анализа latency

## Статус

Принято.

## Контекст

В проекте разрабатывается ML-система уровня зрелости 2 для прогнозирования отказов промышленного оборудования. Система должна поддерживать online-инференс через API, воспроизводимый deployment на виртуальной машине, мониторинг технических метрик, контроль drift входных данных и управляемое продвижение модели через MLflow Model Registry.

Одним из критичных технических показателей является время отклика prediction service. Если latency слишком высокая, результат модели может поступать слишком поздно для оперативного принятия решения о профилактическом обслуживании. Поэтому serving-архитектура должна оцениваться не только по качеству модели, но и по эксплуатационным характеристикам.

В рамках Metrics Driven Development для задания используется два набора latency-измерений:

- baseline-сценарий со средним временем отклика около 3.5 секунды;
- improved-сценарий со средним временем отклика около 2.0 секунды.

Необходимо принять архитектурное решение на основе статистического сравнения двух наборов latency-метрик.

### Расчёт A/B-теста

Подробный расчёт A/B-теста, визуализация распределений latency, p-value и вывод по MDD приведены в ноутбуке:

```text
notebooks/mdd_ab_test_latency.ipynb
```

## Решение

Для сравнения baseline- и improved-сценариев используется статистический анализ latency.

### Гипотезы

Нулевая гипотеза H0:

```text
H0: μ_improved >= μ_existing
```

Среднее время отклика improved-сценария не меньше среднего времени отклика baseline-сценария.

Альтернативная гипотеза H1:

```text
H1: μ_improved < μ_existing
```

Среднее время отклика improved-сценария меньше среднего времени отклика baseline-сценария.

### Уровень значимости

Выбран уровень значимости:

```text
alpha = 0.05
```

### Статистический тест

Используется двухвыборочный Welch's t-test для независимых выборок в односторонней постановке.

Выбор теста обоснован тем, что сравниваются две независимые выборки latency, а Welch's t-test не требует предположения о равенстве дисперсий.

### Результат

Статистический тест показывает p-value меньше 0.05. Следовательно, нулевая гипотеза H0 отклоняется.

Есть статистически значимые основания считать, что improved-сценарий имеет меньшее среднее время отклика, чем baseline-сценарий.

### Архитектурное решение

В production-like контуре принимается serving-архитектура, в которой online-инференс выделен в отдельный FastAPI prediction service и явно наблюдается через Prometheus/Grafana.

Фактическое решение в проекте:

- модель обслуживается через отдельный FastAPI prediction service;
- endpoint `/predict` выполняет прямой inference по признакам, переданным в request body, и используется как baseline/debug endpoint;
- endpoint `/predict/from-feature-store` выполняет production-like inference: принимает `machine_id`, получает online-признаки из Feast Redis Online Store и применяет champion-модель из MLflow Model Registry;
- online-признаки хранятся в Redis через Feast Online Store;
- parquet-файл используется как Feast offline source для исторических признаков;
- PostgreSQL используется как backend store для MLflow и metadata database для Airflow;
- Prometheus собирает request count, error rate, latency prediction service и метрики online feature retrieval;
- Grafana визуализирует технические SLI и инфраструктурные метрики;
- p95 latency включается в SLO и учитывается как эксплуатационное ограничение serving-архитектуры;
- успешность online feature retrieval включается в SLO и Prometheus alert rules;
- для безопасного rollout inference service используется canary gateway на базе Nginx weighted upstream с возможностью rollback на stable.

Model quality gate в проекте контролирует ML-метрики модели: recall, F1-score и ROC-AUC. Latency не является прямым условием в кодовом model quality gate, но контролируется отдельно как технический SLO production-сервиса и используется при эксплуатационном решении о готовности serving-контура к production-rollout.

## Последствия

Положительные последствия:

- решение о serving-архитектуре принято на основе статистического анализа latency, а не визуальной оценки;
- latency становится наблюдаемой и контролируемой частью production-like ML-системы;
- model quality gate отвечает за качество модели, а технические SLO отвечают за эксплуатационные свойства сервиса;
- мониторинг latency позволяет обнаруживать деградацию сервиса после deployment;
- online retrieval из Feast Redis становится частью фактического inference path, а не только отдельной проверкой Feature Store;
- canary gateway позволяет безопасно проверять новую версию inference service и выполнять rollback.

Ограничения и эксплуатационные последствия:

- система становится сложнее из-за необходимости поддерживать Prometheus, Grafana, Redis, Feast Online Store и Nginx canary gateway;
- требуется следить за согласованностью offline source и online store признаков;
- необходимо поддерживать актуальность online-признаков в Redis;
- endpoint `/predict/from-feature-store` зависит не только от MLflow Model Registry, но и от доступности Feast registry и Redis Online Store;
- нарушение latency SLO само по себе не блокирует MLflow promotion автоматически, но должно учитываться при решении о production-rollout.

## Связь с SLI/SLO

Принятое решение связано со следующими SLI/SLO:

- SLI: p95 latency endpoints `/predict` и `/predict/from-feature-store`;
- SLO: p95 latency не выше установленного порога;
- SLI: error rate prediction service;
- SLO: доля ошибочных ответов ниже допустимого уровня;
- SLI: успешность получения online-признаков из Feast Redis Online Store;
- SLO: не менее 99% успешных feature retrieval requests;
- SLI: latency получения online-признаков;
- SLO: feature retrieval latency контролируется как часть общей inference latency.

Фактические Prometheus-метрики для online feature retrieval:

```text
feature_retrieval_requests_total
feature_retrieval_errors_total
feature_retrieval_latency_seconds
```

Prometheus alert rule `PredictiveMaintenanceFeatureRetrievalErrors` срабатывает, если error rate online feature retrieval превышает допустимый уровень.

## Связь с жизненным циклом модели

Если новая модель показывает хорошее качество по ML-метрикам, но её serving-контур нарушает latency SLO, модель не должна считаться готовой к production-rollout без дополнительной оптимизации. В текущей реализации это является эксплуатационным ограничением, а не автоматическим условием внутри скрипта promotion.

Если production-like endpoint `/predict/from-feature-store` не может корректно получить признаки из Feast Redis Online Store, serving-контур также не должен считаться готовым к production. Для текущего проекта это означает, что фиксированный набор признаков для модели должен успешно извлекаться из Redis через Feast.

Таким образом, вывод модели в production-like эксплуатацию зависит от трёх групп факторов:

- ML-качества модели: recall, F1-score и ROC-AUC;
- технических характеристик сервиса: latency, error rate и доступность API;
- корректности online feature retrieval из Feast Redis.

## Итог

На основе MDD-анализа latency принято решение использовать отдельный FastAPI prediction service с production-like endpoint `/predict/from-feature-store`, Redis Online Store через Feast, MLflow champion model loading, Prometheus/Grafana monitoring и Nginx canary gateway для безопасного rollout/rollback.

Model quality gate остаётся ответственным за ML-метрики, а latency и feature retrieval reliability фиксируются как технические SLO, которые должны учитываться при эксплуатационном решении о готовности serving-контура к production.
