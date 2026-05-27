from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from feast import FeatureStore


FEATURE_REPO_PATH = Path("feature_repo")


def check_offline_features(store: FeatureStore) -> None:
    entity_df = pd.DataFrame(
        {
            "machine_id": [1, 2, 3],
            "event_timestamp": pd.to_datetime(
                [
                    "2026-01-01 00:00:00+00:00",
                    "2026-01-01 01:00:00+00:00",
                    "2026-01-01 02:00:00+00:00",
                ],
                utc=True,
            ),
        }
    )

    features = store.get_historical_features(
        entity_df=entity_df,
        features=[
            "machine_sensor_features:air_temperature_k",
            "machine_sensor_features:process_temperature_k",
            "machine_sensor_features:rotational_speed_rpm",
            "machine_sensor_features:torque_nm",
            "machine_sensor_features:tool_wear_min",
            "machine_sensor_features:machine_type_H",
            "machine_sensor_features:machine_type_L",
            "machine_sensor_features:machine_type_M",
        ],
    ).to_df()

    print("Offline feature retrieval passed.")
    print(features)


def materialize_online_features(store: FeatureStore) -> None:
    start_date = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    end_date = datetime(2027, 3, 1, 0, 0, 0, tzinfo=timezone.utc)

    store.materialize(start_date=start_date, end_date=end_date)

    print("Feature materialization to Redis passed.")


def check_online_features(store: FeatureStore) -> None:
    online_features = store.get_online_features(
        features=[
            "machine_sensor_features:air_temperature_k",
            "machine_sensor_features:process_temperature_k",
            "machine_sensor_features:rotational_speed_rpm",
            "machine_sensor_features:torque_nm",
            "machine_sensor_features:tool_wear_min",
            "machine_sensor_features:machine_type_H",
            "machine_sensor_features:machine_type_L",
            "machine_sensor_features:machine_type_M",
        ],
        entity_rows=[
            {"machine_id": 1},
            {"machine_id": 2},
            {"machine_id": 3},
        ],
    ).to_dict()

    print("Online feature retrieval from Redis passed.")
    print(online_features)


def main() -> None:
    store = FeatureStore(repo_path=str(FEATURE_REPO_PATH))

    check_offline_features(store)
    materialize_online_features(store)
    check_online_features(store)


if __name__ == "__main__":
    main()
