from datetime import timedelta

from feast import Entity, FeatureService, FeatureView, Field, FileSource, ValueType
from feast.types import Float32, Int64


machine = Entity(
    name="machine",
    join_keys=["machine_id"],
    value_type=ValueType.INT64,
    description="Industrial machine identifier",
)

machine_sensor_source = FileSource(
    name="machine_sensor_source",
    path="../data/processed/ai4i2020_features.parquet",
    timestamp_field="event_timestamp",
    created_timestamp_column="created_timestamp",
)

machine_sensor_features = FeatureView(
    name="machine_sensor_features",
    entities=[machine],
    ttl=timedelta(days=365),
    schema=[
        Field(name="air_temperature_k", dtype=Float32),
        Field(name="process_temperature_k", dtype=Float32),
        Field(name="rotational_speed_rpm", dtype=Int64),
        Field(name="torque_nm", dtype=Float32),
        Field(name="tool_wear_min", dtype=Int64),
        Field(name="machine_type_H", dtype=Int64),
        Field(name="machine_type_L", dtype=Int64),
        Field(name="machine_type_M", dtype=Int64),
    ],
    source=machine_sensor_source,
    online=True,
    tags={
        "domain": "predictive_maintenance",
        "team": "mlops",
    },
)

failure_prediction_service = FeatureService(
    name="failure_prediction_service",
    features=[machine_sensor_features],
)
