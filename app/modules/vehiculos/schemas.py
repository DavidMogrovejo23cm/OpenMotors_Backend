from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, AliasChoices


class VehiculoCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    placa: str
    anio: int = 2024
    marca: str
    modelo: str
    nombre_vehiculo: Optional[str] = Field(default=None, validation_alias=AliasChoices("nombre_vehiculo", "nombreVehiculo"))
    tipo_vehiculo: Optional[str] = Field(default=None, validation_alias=AliasChoices("tipo_vehiculo", "tipoVehiculo"))
    kilometraje: Optional[int] = 0
    cilindraje: Optional[int] = 1600
    id_usuario: int = Field(..., validation_alias=AliasChoices("id_usuario", "idUsuario"))
    ruta_imagen_vehiculo: Optional[str] = Field(
        default=None, validation_alias=AliasChoices("ruta_imagen_vehiculo", "rutaImagenVehiculo")
    )


class VehiculoUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    placa: Optional[str] = None
    anio: Optional[int] = None
    marca: Optional[str] = None
    modelo: Optional[str] = None
    nombre_vehiculo: Optional[str] = Field(default=None, validation_alias=AliasChoices("nombre_vehiculo", "nombreVehiculo"))
    tipo_vehiculo: Optional[str] = Field(default=None, validation_alias=AliasChoices("tipo_vehiculo", "tipoVehiculo"))
    kilometraje: Optional[int] = None
    cilindraje: Optional[int] = None
    id_usuario: Optional[int] = Field(default=None, validation_alias=AliasChoices("id_usuario", "idUsuario"))
    ruta_imagen_vehiculo: Optional[str] = Field(
        default=None, validation_alias=AliasChoices("ruta_imagen_vehiculo", "rutaImagenVehiculo")
    )

