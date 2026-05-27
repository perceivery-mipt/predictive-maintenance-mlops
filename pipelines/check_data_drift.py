from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from evidently.metric_preset import DataDriftPreset
from evidently.report import Report


PROCESSED_DATA_PATH = Path("data/processed/ai4i2020_processed.csv")
REPORT_DIR = Path("reports/evidently")
HTML_REPORT_PATH = REPORT_DIR / "data_drift_report.html"
JSON_SUMMARY_PATH = REPORT_DIR / "data_drift_summary.json"


FEATURE_COLUMNS = [
    "air_temperature_k",
    "process_temperature_k",
    "rotational_speed_rpm",
    "torque_nm",
    "tool_wear_min",
    "machine_type_H",
    "machine_type_L",
    "machine_type_M",
]


def build_reference_current_split(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = df.sort_values("event_timestamp").reset_index(drop=True)

    split_idx = int(len(df) * 0.7)

    reference = df.iloc[:split_idx][FEATURE_COLUMNS].copy()
    current = df.iloc[split_idx:][FEATURE_COLUMNS].copy()

    return reference, current


def main() -> None:
    if not PROCESSED_DATA_PATH.exists():
        raise FileNotFoundError(
            f"Processed dataset was not found: {PROCESSED_DATA_PATH}. "
            "Run `python pipelines/prepare_data.py` first."
        )

    df = pd.read_csv(PROCESSED_DATA_PATH)

    reference, current = build_reference_current_split(df)

    report = Report(metrics=[DataDriftPreset()])
    report.run(reference_data=reference, current_data=current)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report.save_html(str(HTML_REPORT_PATH))

    result = report.as_dict()

    dataset_drift = result["metrics"][0]["result"].get("dataset_drift")
    drift_share = result["metrics"][0]["result"].get("share_of_drifted_columns")
    number_of_drifted_columns = result["metrics"][0]["result"].get("number_of_drifted_columns")

    summary = {
        "reference_rows": len(reference),
        "current_rows": len(current),
        "features": FEATURE_COLUMNS,
        "dataset_drift": dataset_drift,
        "share_of_drifted_columns": drift_share,
        "number_of_drifted_columns": number_of_drifted_columns,
        "html_report_path": str(HTML_REPORT_PATH),
    }

    JSON_SUMMARY_PATH.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("Evidently data drift report was created.")
    print(f"HTML report: {HTML_REPORT_PATH}")
    print(f"JSON summary: {JSON_SUMMARY_PATH}")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
