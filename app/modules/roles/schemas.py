from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, AliasChoices


class RolBase(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    nombre: str = Field(..., min_length=1, max_length=50)


class RolCreate(RolBase):
    id_rol: Optional[int] = Field(default=None, validation_alias=AliasChoices("id_rol", "idRol"))


class RolResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id_rol: int
    nombre: str


class AsignarRolRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id_usuario: int = Field(..., validation_alias=AliasChoices("id_usuario", "idUsuario"))
    id_rol: int = Field(..., validation_alias=AliasChoices("id_rol", "idRol"))
    estado: Optional[int] = 1


class CambiarCategoriaRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id_usuario: int = Field(..., validation_alias=AliasChoices("id_usuario", "idUsuario"))
    id_rol_actual: int = Field(..., validation_alias=AliasChoices("id_rol_actual", "idRolActual"))
    id_rol_nuevo: int = Field(..., validation_alias=AliasChoices("id_rol_nuevo", "idRolNuevo"))

