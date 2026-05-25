# MDD-анализ времени отклика системы

## 1. Контекст

В рамках проекта требуется принять архитектурное решение на основе Metrics Driven Development. Для этого сравниваются два набора данных по времени отклика:

- существующая система;
- улучшенная система.

Цель анализа — проверить, действительно ли улучшенная архитектура снижает latency, а не демонстрирует случайное отличие на выборке.

## 2. Метрика

Основная метрика анализа — время отклика системы в секундах.

Дополнительно рассматриваются:

- среднее значение latency;
- медиана latency;
- p95 latency;
- распределение времени отклика;
- статистическая значимость различий между двумя выборками.

## 3. Данные

В задании предложена следующая генерация данных:

```python
import numpy as np

np.random.seed(42)
existing_system_responses = np.random.normal(loc=3.5, scale=0.4, size=500000)
improved_system_responses = np.random.normal(loc=2.0, scale=0.4, size=500000)
```

Существующая система имеет среднее время отклика около 3.5 секунды. Улучшенная система имеет среднее время отклика около 2.0 секунды.

## 4. Гипотезы

Формулируем статистические гипотезы.

Нулевая гипотеза H0:

> Среднее время отклика улучшенной системы не меньше среднего времени отклика существующей системы.

Альтернативная гипотеза H1:

> Среднее время отклика улучшенной системы меньше среднего времени отклика существующей системы.

В математической форме:

```text
H0: μ_improved >= μ_existing
H1: μ_improved <  μ_existing
```

## 5. Уровень значимости

Выбран уровень значимости:

```text
alpha = 0.05
```

Если p-value меньше 0.05, нулевая гипотеза отклоняется.

## 6. Выбор статистического теста

Так как сравниваются две независимые выборки latency, применяется двухвыборочный t-test для независимых выборок.

Несмотря на большой размер выборок, дополнительно используется вариант Welch's t-test, который не требует строгого равенства дисперсий.

Тест применяется в односторонней постановке, потому что нас интересует не любое отличие, а именно уменьшение времени отклика.

## 7. Код анализа

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

statistic, p_value_two_sided = stats.ttest_ind(
    improved_system_responses,
    existing_system_responses,
    equal_var=False
)

# Для односторонней гипотезы H1: improved < existing
if statistic < 0:
    p_value_one_sided = p_value_two_sided / 2
else:
    p_value_one_sided = 1 - p_value_two_sided / 2

print("Existing mean:", existing_mean)
print("Improved mean:", improved_mean)
print("Existing median:", existing_median)
print("Improved median:", improved_median)
print("Existing p95:", existing_p95)
print("Improved p95:", improved_p95)
print("t-statistic:", statistic)
print("one-sided p-value:", p_value_one_sided)
```

## 8. Интерпретация результата

Ожидаемый результат анализа:

- среднее время отклика существующей системы около 3.5 секунды;
- среднее время отклика улучшенной системы около 2.0 секунды;
- p95 latency улучшенной системы существенно ниже p95 latency существующей системы;
- p-value близко к нулю и меньше выбранного уровня значимости 0.05.

Следовательно, нулевая гипотеза H0 отклоняется. Есть статистически значимые основания считать, что улучшенная система имеет меньшее время отклика.

## 9. Архитектурный вывод

На основе MDD-анализа принимается решение использовать улучшенную архитектуру сервинга модели.

Для проекта это означает:

- использовать FastAPI как отдельный prediction service;
- вынести online-признаки в Redis через Feast Online Store;
- использовать healthcheck и Prometheus-метрики для контроля latency;
- отслеживать p95 latency как технический SLI;
- зафиксировать SLO по latency для production API;
- не продвигать новую модель в production, если её inference latency нарушает SLO.

## 10. Связь с quality gate

Latency включается в quality gate модели.

Модель-кандидат может быть продвинута в production только если одновременно выполняются условия:

- модельные метрики не хуже пороговых значений;
- recall по классу отказа соответствует требованиям;
- p95 inference latency не превышает заданный SLO;
- сервис не демонстрирует повышенный error rate.

Таким образом, решение о deployment принимается не только на основе качества модели, но и на основе эксплуатационных метрик системы.
