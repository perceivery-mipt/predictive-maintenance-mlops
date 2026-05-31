# MDD-анализ времени отклика системы

## 1. Контекст

В рамках проекта требуется принять архитектурное решение на основе Metrics Driven Development. Для этого сравниваются два набора данных по времени отклика prediction service:

- baseline-сценарий существующей системы;
- improved-сценарий улучшенной serving-архитектуры.

Цель анализа — проверить, действительно ли improved-сценарий снижает latency, а не демонстрирует случайное отличие на выборке.

Этот документ является кратким текстовым summary к ноутбуку:

```text
notebooks/mdd_ab_test_latency.ipynb
```

Ноутбук содержит полный расчёт A/B-теста, визуализацию распределений, статистический тест, p-value и итоговый вывод. Используемые latency-данные являются расчётным MDD-артефактом по условию задания, а не production-логами текущей VM.

## 2. Метрика

Основная метрика анализа — время отклика системы в секундах.

Дополнительно рассматриваются:

- среднее значение latency;
- медиана latency;
- p95 latency;
- p99 latency;
- распределение времени отклика;
- статистическая значимость различий между двумя выборками.

## 3. Данные

В ноутбуке используются два сгенерированных набора latency-измерений:

```python
import numpy as np

np.random.seed(42)
existing_system_responses = np.random.normal(loc=3.5, scale=0.4, size=500000)
improved_system_responses = np.random.normal(loc=2.0, scale=0.4, size=500000)
```

Baseline-сценарий имеет среднее время отклика около 3.5 секунды. Improved-сценарий имеет среднее время отклика около 2.0 секунды.

Такая постановка позволяет проверить не только визуальную разницу между двумя распределениями, но и статистическую значимость улучшения latency.

## 4. Гипотезы

Формулируем статистические гипотезы.

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

## 5. Уровень значимости

Выбран уровень значимости:

```text
alpha = 0.05
```

Если p-value меньше 0.05, нулевая гипотеза отклоняется.

## 6. Выбор статистического теста

Так как сравниваются две независимые выборки latency, применяется двухвыборочный Welch's t-test для независимых выборок.

Welch's t-test выбран потому, что он не требует предположения о равенстве дисперсий двух выборок. Тест применяется в односторонней постановке, потому что нас интересует не любое отличие, а именно уменьшение времени отклика improved-сценария относительно baseline-сценария.

## 7. Код анализа

Основной код анализа:

```python
import numpy as np
from scipy import stats

np.random.seed(42)
existing_system_responses = np.random.normal(loc=3.5, scale=0.4, size=500000)
improved_system_responses = np.random.normal(loc=2.0, scale=0.4, size=500000)

existing_mean = np.mean(existing_system_responses)
improved_mean = np.mean(improved_system_responses)

existing_median = np.median(existing_system_responses)
improved_median = np.median(improved_system_responses)

existing_p95 = np.percentile(existing_system_responses, 95)
improved_p95 = np.percentile(improved_system_responses, 95)

existing_p99 = np.percentile(existing_system_responses, 99)
improved_p99 = np.percentile(improved_system_responses, 99)

result = stats.ttest_ind(
    improved_system_responses,
    existing_system_responses,
    equal_var=False,
    alternative="less",
)

print("Existing mean:", existing_mean)
print("Improved mean:", improved_mean)
print("Existing median:", existing_median)
print("Improved median:", improved_median)
print("Existing p95:", existing_p95)
print("Improved p95:", improved_p95)
print("Existing p99:", existing_p99)
print("Improved p99:", improved_p99)
print("t-statistic:", result.statistic)
print("one-sided p-value:", result.pvalue)
```

В ноутбуке также строятся графики распределений latency и сравнение ключевых статистик baseline/improved сценариев.

## 8. Результат и интерпретация

Результаты анализа показывают:

- среднее время отклика baseline-сценария составляет около 3.5 секунды;
- среднее время отклика improved-сценария составляет около 2.0 секунды;
- p95 latency improved-сценария существенно ниже p95 latency baseline-сценария;
- p-value практически равно нулю и меньше выбранного уровня значимости 0.05.

Следовательно, нулевая гипотеза H0 отклоняется. Есть статистически значимые основания считать, что improved-сценарий имеет меньшее среднее время отклика.

Практический эффект также существенный: снижение среднего latency составляет примерно 1.5 секунды, что является значимым улучшением для online prediction service.

## 9. Архитектурный вывод

На основе MDD-анализа принимается решение использовать улучшенную serving-архитектуру, в которой prediction service является отдельным FastAPI-сервисом и поддерживает production-like inference path.

Для проекта это означает:

- использовать FastAPI как отдельный prediction service;
- оставить endpoint `/predict` для прямого inference по признакам из request body;
- использовать endpoint `/predict/from-feature-store` как production-like inference path;
- получать online-признаки из Redis через Feast Online Store;
- загружать активную champion-модель из MLflow Model Registry;
- отдавать Prometheus-метрики на endpoint `/metrics`;
- отслеживать request count, error rate, latency и feature retrieval metrics;
- визуализировать технические SLI через Grafana;
- фиксировать p95 latency как технический SLI/SLO production API;
- использовать Nginx canary gateway для безопасного rollout и rollback serving-сервиса.

Таким образом, MDD-анализ latency обосновывает не просто выбор FastAPI, а весь production-like serving path:

```text
Client request
    ↓
FastAPI /predict/from-feature-store
    ↓
Feast Redis Online Store
    ↓
MLflow champion model
    ↓
Prediction response
    ↓
Prometheus / Grafana monitoring
```

## 10. Связь с quality gate и SLO

Latency не входит напрямую в model quality gate, реализованный в коде проекта.

Фактический model quality gate проверяет модельные метрики:

```text
recall  >= 0.80
f1      >= 0.60
roc_auc >= 0.85
```

Latency, error rate и успешность online feature retrieval контролируются отдельно как технические SLI/SLO production-сервиса.

Это разделение важно:

- model quality gate отвечает за качество ML-модели;
- SLO/monitoring отвечают за эксплуатационные свойства serving-контура;
- MDD-анализ latency обосновывает архитектурное решение по serving path;
- canary gateway и rollback scripts позволяют безопасно переключать traffic при проблемах с эксплуатационными метриками.

При production rollout необходимо учитывать latency SLO. Если serving-контур нарушает SLO по latency или error rate, rollout должен быть остановлен или выполнен rollback на stable-версию. Однако в текущей реализации это является эксплуатационным правилом и архитектурным ограничением, а не автоматической проверкой внутри `promote_model.py`.

## 11. Связь с Prometheus/Grafana

Для контроля serving-архитектуры используются Prometheus-метрики FastAPI:

```text
predict_requests_total
predict_errors_total
predict_latency_seconds
prediction_risk_level_total
feature_retrieval_requests_total
feature_retrieval_errors_total
feature_retrieval_latency_seconds
```

Эти метрики позволяют контролировать:

- количество prediction requests;
- error rate prediction service;
- latency inference endpoint;
- распределение предсказаний по risk level;
- успешность online feature retrieval из Feast Redis;
- latency получения признаков из online store.

Grafana dashboard визуализирует эти метрики и используется для демонстрации технического мониторинга сервиса.

## 12. Итог

MDD-анализ показывает статистически значимое снижение latency в improved-сценарии. На основании этого принято архитектурное решение использовать production-like serving architecture: FastAPI prediction service, Feast Redis Online Store, MLflow champion model loading, Prometheus/Grafana monitoring и canary gateway для безопасного rollout/rollback.

Model quality gate остаётся ответственным за ML-метрики модели, а latency контролируется отдельно как технический SLO и production rollout constraint.
