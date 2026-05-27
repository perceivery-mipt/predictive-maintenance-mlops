# ADR-0003: Принятие архитектурного решения на основе анализа latency

## Статус

Принято.

## Контекст

В проекте разрабатывается ML-система уровня зрелости 2 для прогнозирования отказов оборудования. Система должна обслуживать online-инференс через API и поддерживать мониторинг технических и модельных метрик.

Одним из критичных технических показателей является время отклика prediction service. Если latency слишком высокая, результат модели может поступать слишком поздно для оперативного принятия решения о профилактическом обслуживании.

В задании предоставлены два набора данных по времени отклика:

- существующая система со средним временем отклика около 3.5 секунды;
- улучшенная система со средним временем отклика около 2.0 секунды.

Необходимо принять архитектурное решение не на глаз, а на основе Metrics Driven Development.

## Decision

Для сравнения двух систем используется статистический анализ latency.

### Гипотезы

Нулевая гипотеза H0:

```text
H0: μ_improved >= μ_existing
```

Среднее время отклика улучшенной системы не меньше среднего времени отклика существующей системы.

Альтернативная гипотеза H1:

```text
H1: μ_improved < μ_existing
```

Среднее время отклика улучшенной системы меньше среднего времени отклика существующей системы.

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

Есть статистически значимые основания считать, что улучшенная система имеет меньшее среднее время отклика.

### Архитектурное решение

В production-контуре принимается улучшенная архитектура сервинга модели:

- модель обслуживается через отдельный FastAPI prediction service;
- endpoint `/predict` выполняет inference по признакам, переданным напрямую в request body;
- endpoint `/predict/from-feature-store` выполняет production-like inference: принимает `machine_id`, получает online-признаки из Feast Redis Online Store и затем применяет champion-модель из MLflow Model Registry;
- online-признаки хранятся в Redis через Feast Online Store;
- PostgreSQL используется как offline store и постоянное хранилище;
- Prometheus собирает latency, request count, error rate и метрики online feature retrieval;
- Grafana визуализирует технические SLI;
- p95 latency включается в SLO и quality gate;
- успешность online feature retrieval включается в SLO и Prometheus alert rules;
- модель-кандидат не может быть продвинута в production, если нарушает latency SLO.

## Последствия

Положительные последствия:

- решение о serving-архитектуре принято на основе статистики, а не визуальной оценки;
- latency становится контролируемой частью production ML-системы;
- quality gate учитывает не только ML-метрики, но и эксплуатационные требования;
- мониторинг latency позволяет обнаруживать деградацию сервиса после deployment;
- online retrieval из Feast Redis становится частью фактического inference path, а не только отдельной проверкой Feature Store.

Отрицательные и ограничивающие последствия:

- система становится сложнее из-за необходимости поддерживать Prometheus, Grafana, Redis и Feast Online Store;
- требуется следить за согласованностью offline- и online-признаков;
- необходимо поддерживать регулярную материализацию признаков в online store;
- inference endpoint `/predict/from-feature-store` зависит не только от MLflow Model Registry, но и от доступности Feast registry и Redis Online Store.

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

Если новая модель показывает хорошее качество, но нарушает latency SLO, она не продвигается в production. Это предотвращает ситуацию, когда формально качественная модель ухудшает эксплуатационные характеристики системы.

Если новая модель требует признаки, которые не могут быть корректно получены из Feast Redis Online Store, она также не должна продвигаться в production, потому что production-like endpoint `/predict/from-feature-store` зависит от успешного online feature retrieval.

Таким образом, вывод модели в production зависит одновременно от качества предсказаний, технических характеристик сервиса и корректности online feature retrieval.
