from pathlib import Path

import pandas as pd


PROCESSED_DATA_PATH = Path("data/processed/ai4i2020_processed.csv")
FEAST_FEATURES_PATH = Path("data/processed/ai4i2020_features.parquet")


FEATURE_COLUMNS = [
    "machine_id",
    "event_timestamp",
    "created_timestamp",
    "air_temperature_k",
    "process_temperature_k",
    "rotational_speed_rpm",
    "torque_nm",
    "tool_wear_min",
    "machine_type_H",
    "machine_type_L",
    "machine_type_M",
]


def main() -> None:
    if not PROCESSED_DATA_PATH.exists():
        raise FileNotFoundError(
            f"Processed dataset was not found: {PROCESSED_DATA_PATH}. "
            "Run `python pipelines/prepare_data.py` first."
        )

    df = pd.read_csv(PROCESSED_DATA_PATH)

    features = df[FEATURE_COLUMNS].copy()
    features["event_timestamp"] = pd.to_datetime(features["event_timestamp"], utc=True)
    features["created_timestamp"] = pd.to_datetime(features["created_timestamp"], utc=True)

    FEAST_FEATURES_PATH.parent.mkdir(parents=True, exist_ok=True)
    features.to_parquet(FEAST_FEATURES_PATH, index=False)

    print("Feast feature dataset was created.")
    print(f"Path: {FEAST_FEATURES_PATH}")
    print(f"Shape: {features.shape}")
    print(features.head())


if __name__ == "__main__":
    main()
