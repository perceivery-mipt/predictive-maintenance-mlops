from pydantic import BaseModel, Field


class PredictionRequest(BaseModel):
    air_temperature_k: float = Field(..., description="Air temperature in Kelvin")
    process_temperature_k: float = Field(..., description="Process temperature in Kelvin")
    rotational_speed_rpm: float = Field(..., description="Rotational speed in rpm")
    torque_nm: float = Field(..., description="Torque in Nm")
    tool_wear_min: float = Field(..., description="Tool wear in minutes")
    machine_type_H: int = Field(..., ge=0, le=1, description="High-quality machine type flag")
    machine_type_L: int = Field(..., ge=0, le=1, description="Low-quality machine type flag")
    machine_type_M: int = Field(..., ge=0, le=1, description="Medium-quality machine type flag")


class PredictionResponse(BaseModel):
    failure_probability: float
    prediction: int
    risk_level: str
    recommended_action: str
    model_name: str
    model_alias: str


class ModelInfoResponse(BaseModel):
    model_name: str
    model_alias: str
    model_uri: str
    status: str
