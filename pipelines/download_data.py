from pathlib import Path

import pandas as pd
import requests


DATA_URL = "https://archive.ics.uci.edu/ml/machine-learning-databases/00601/ai4i2020.csv"
RAW_DATA_PATH = Path("data/raw/ai4i2020.csv")


def download_file(url: str, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    response = requests.get(url, timeout=30)
    response.raise_for_status()

    output_path.write_bytes(response.content)


def validate_raw_dataset(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Raw dataset was not found: {path}")

    df = pd.read_csv(path)

    expected_columns = {
        "UDI",
        "Product ID",
        "Type",
        "Air temperature [K]",
        "Process temperature [K]",
        "Rotational speed [rpm]",
        "Torque [Nm]",
        "Tool wear [min]",
        "Machine failure",
        "TWF",
        "HDF",
        "PWF",
        "OSF",
        "RNF",
    }

    actual_columns = set(df.columns)
    missing_columns = expected_columns - actual_columns

    if missing_columns:
        raise ValueError(f"Missing expected columns: {sorted(missing_columns)}")

    if df.empty:
        raise ValueError("Raw dataset is empty.")

    if df["Machine failure"].nunique() < 2:
        raise ValueError("Target column must contain both classes.")

    print("Raw dataset validation passed.")
    print(f"Path: {path}")
    print(f"Shape: {df.shape}")
    print("Target distribution:")
    print(df["Machine failure"].value_counts().sort_index())


def main() -> None:
    print("Downloading AI4I 2020 Predictive Maintenance Dataset...")
    download_file(DATA_URL, RAW_DATA_PATH)
    validate_raw_dataset(RAW_DATA_PATH)


if __name__ == "__main__":
    main()