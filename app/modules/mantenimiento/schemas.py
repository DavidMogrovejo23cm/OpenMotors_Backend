from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, AliasChoices


class ParametroUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    intervalo_km: int = Field(..., validation_alias=AliasChoices("intervalo_km", "intervaloKm"))
    descripcion: Optional[str] = None


class MantenimientoRegistrarRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id_moto: int = Field(..., validation_alias=AliasChoices("id_moto", "idMoto"))
    tipo: str
    km_servicio: int = Field(..., validation_alias=AliasChoices("km_servicio", "kmServicio"))

