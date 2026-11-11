from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, AliasChoices


class CargaCombustibleCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id_vehiculo: int = Field(..., validation_alias=AliasChoices("id_vehiculo", "idVehiculo"))
    placa: Optional[str] = None
    fecha: Optional[str] = None
    litros: float
    costo_total: float = Field(..., validation_alias=AliasChoices("costo_total", "costoTotal"))
    km_actual: int = Field(..., validation_alias=AliasChoices("km_actual", "kmActual"))
    km_anterior: Optional[int] = Field(default=0, validation_alias=AliasChoices("km_anterior", "kmAnterior"))
    notas: Optional[str] = None


class PrecioCombustibleUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    precio: float

