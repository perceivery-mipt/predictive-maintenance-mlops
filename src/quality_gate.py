from dataclasses import dataclass


@dataclass(frozen=True)
class QualityGateThresholds:
    min_recall: float = 0.80
    min_f1: float = 0.60
    min_roc_auc: float = 0.85
    max_p95_latency_ms: float = 300.0


@dataclass(frozen=True)
class QualityGateResult:
    passed: bool
    failed_checks: list[str]
    passed_checks: list[str]


def evaluate_quality_gate(
    metrics: dict,
    thresholds: QualityGateThresholds | None = None,
) -> QualityGateResult:
    if thresholds is None:
        thresholds = QualityGateThresholds()

    failed_checks: list[str] = []
    passed_checks: list[str] = []

    checks = [
        (
            "recall",
            metrics.get("recall"),
            ">=",
            thresholds.min_recall,
        ),
        (
            "f1",
            metrics.get("f1"),
            ">=",
            thresholds.min_f1,
        ),
        (
            "roc_auc",
            metrics.get("roc_auc"),
            ">=",
            thresholds.min_roc_auc,
        ),
    ]

    if "p95_latency_ms" in metrics:
        checks.append(
            (
                "p95_latency_ms",
                metrics.get("p95_latency_ms"),
                "<=",
                thresholds.max_p95_latency_ms,
            )
        )

    for metric_name, metric_value, operator, threshold_value in checks:
        if metric_value is None:
            failed_checks.append(f"{metric_name}: missing")
            continue

        if operator == ">=":
            is_passed = metric_value >= threshold_value
        elif operator == "<=":
            is_passed = metric_value <= threshold_value
        else:
            raise ValueError(f"Unsupported operator: {operator}")

        check_message = (
            f"{metric_name}: {metric_value:.6f} {operator} {threshold_value:.6f}"
        )

        if is_passed:
            passed_checks.append(check_message)
        else:
            failed_checks.append(check_message)

    return QualityGateResult(
        passed=len(failed_checks) == 0,
        failed_checks=failed_checks,
        passed_checks=passed_checks,
    )
