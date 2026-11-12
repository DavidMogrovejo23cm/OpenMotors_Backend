from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, AliasChoices


class ParametroUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    intervalo_km: int = Field(..., validation_alias=AliasChoices("intervalo_km", "intervaloKm"))
    descripcion: Optional[str] = None


class MantenimientoRegistrarRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id_vehiculo: int = Field(
        ...,
        validation_alias=AliasChoices("id_vehiculo", "idVehiculo", "id_moto", "idMoto"),
    )
    tipo: str
    km_servicio: int = Field(..., validation_alias=AliasChoices("km_servicio", "kmServicio"))


class CitaMantenimientoCreate(BaseModel):
    """Agendamiento de cita preventiva a partir del aviso de desgaste (Proceso 16)."""
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id_vehiculo: int = Field(
        ...,
        validation_alias=AliasChoices("id_vehiculo", "idVehiculo", "id_moto", "idMoto"),
    )
    id_usuario: Optional[int] = Field(default=None, validation_alias=AliasChoices("id_usuario", "idUsuario"))
    fecha_agendada: str = Field(..., validation_alias=AliasChoices("fecha_agendada", "fechaAgendada"))
    piezas_a_revisar: Optional[str] = Field(default=None, validation_alias=AliasChoices("piezas_a_revisar", "piezasARevisar"))
    observaciones: Optional[str] = None


