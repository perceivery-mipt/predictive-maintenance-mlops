from pathlib import Path

import pandas as pd


RAW_DATA_PATH = Path("data/raw/ai4i2020.csv")
PROCESSED_DATA_PATH = Path("data/processed/ai4i2020_processed.csv")


COLUMN_MAPPING = {
    "UDI": "udi",
    "Product ID": "product_id",
    "Type": "machine_type",
    "Air temperature [K]": "air_temperature_k",
    "Process temperature [K]": "process_temperature_k",
    "Rotational speed [rpm]": "rotational_speed_rpm",
    "Torque [Nm]": "torque_nm",
    "Tool wear [min]": "tool_wear_min",
    "Machine failure": "machine_failure",
    "TWF": "tool_wear_failure",
    "HDF": "heat_dissipation_failure",
    "PWF": "power_failure",
    "OSF": "overstrain_failure",
    "RNF": "random_failure",
}


def load_raw_data(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"Raw dataset was not found: {path}. "
            "Run `python pipelines/download_data.py` first."
        )

    return pd.read_csv(path)


def prepare_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns=COLUMN_MAPPING).copy()

    required_columns = set(COLUMN_MAPPING.values())
    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise ValueError(f"Missing columns after renaming: {sorted(missing_columns)}")

    df["machine_id"] = df["udi"].astype(int)

    start_timestamp = pd.Timestamp("2026-01-01 00:00:00")
    df["event_timestamp"] = start_timestamp + pd.to_timedelta(df.index, unit="h")
    df["created_timestamp"] = pd.Timestamp.utcnow().floor("s")

    machine_type_dummies = pd.get_dummies(
        df["machine_type"],
        prefix="machine_type",
        dtype=int,
    )

    df = pd.concat([df, machine_type_dummies], axis=1)

    expected_dummy_columns = [
        "machine_type_H",
        "machine_type_L",
        "machine_type_M",
    ]

    for column in expected_dummy_columns:
        if column not in df.columns:
            df[column] = 0

    selected_columns = [
        "machine_id",
        "event_timestamp",
        "created_timestamp",
        "product_id",
        "machine_type",
        "air_temperature_k",
        "process_temperature_k",
        "rotational_speed_rpm",
        "torque_nm",
        "tool_wear_min",
        "machine_type_H",
        "machine_type_L",
        "machine_type_M",
        "machine_failure",
        "tool_wear_failure",
        "heat_dissipation_failure",
        "power_failure",
        "overstrain_failure",
        "random_failure",
    ]

    prepared = df[selected_columns].copy()

    prepared = prepared.sort_values(["event_timestamp", "machine_id"]).reset_index(drop=True)

    return prepared


def validate_processed_data(df: pd.DataFrame) -> None:
    if df.empty:
        raise ValueError("Processed dataset is empty.")

    if df["machine_id"].isna().any():
        raise ValueError("machine_id contains missing values.")

    if df["event_timestamp"].isna().any():
        raise ValueError("event_timestamp contains missing values.")

    if df["machine_failure"].nunique() < 2:
        raise ValueError("Target column machine_failure must contain both classes.")

    feature_columns = [
        "air_temperature_k",
        "process_temperature_k",
        "rotational_speed_rpm",
        "torque_nm",
        "tool_wear_min",
        "machine_type_H",
        "machine_type_L",
        "machine_type_M",
    ]

    if df[feature_columns].isna().any().any():
        raise ValueError("Feature columns contain missing values.")

    print("Processed dataset validation passed.")
    print(f"Shape: {df.shape}")
    print("Columns:")
    print(list(df.columns))
    print("Target distribution:")
    print(df["machine_failure"].value_counts().sort_index())


def save_processed_data(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def main() -> None:
    raw_df = load_raw_data(RAW_DATA_PATH)
    processed_df = prepare_features(raw_df)
    validate_processed_data(processed_df)
    save_processed_data(processed_df, PROCESSED_DATA_PATH)

    print(f"Processed dataset saved to: {PROCESSED_DATA_PATH}")


if __name__ == "__main__":
    main()
