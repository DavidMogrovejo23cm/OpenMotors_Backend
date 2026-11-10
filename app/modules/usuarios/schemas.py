from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, AliasChoices


class UsuarioCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    nombre_completo: str = Field(..., validation_alias=AliasChoices("nombre_completo", "nombreCompleto"))
    nombre_usuario: str = Field(..., validation_alias=AliasChoices("nombre_usuario", "nombreUsuario"))
    correo: str
    contrasena: Optional[str] = "123456"
    pais: Optional[str] = "Ecuador"
    ciudad: Optional[str] = None
    descripcion: Optional[str] = None
    ruta_imagen: Optional[str] = Field(default=None, validation_alias=AliasChoices("ruta_imagen", "rutaImagen"))
    telefono: Optional[str] = None
    cedula: Optional[str] = None
    direccion: Optional[str] = None
    puntos_bonus: Optional[int] = Field(default=0, validation_alias=AliasChoices("puntos_bonus", "puntosBonus"))
    codigo_referido: Optional[str] = Field(default=None, validation_alias=AliasChoices("codigo_referido", "codigoReferido"))


class UsuarioUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    nombre_completo: Optional[str] = Field(default=None, validation_alias=AliasChoices("nombre_completo", "nombreCompleto"))
    nombre_usuario: Optional[str] = Field(default=None, validation_alias=AliasChoices("nombre_usuario", "nombreUsuario"))
    correo: Optional[str] = None
    contrasena: Optional[str] = None
    pais: Optional[str] = None
    ciudad: Optional[str] = None
    descripcion: Optional[str] = None
    ruta_imagen: Optional[str] = Field(default=None, validation_alias=AliasChoices("ruta_imagen", "rutaImagen"))
    telefono: Optional[str] = None
    cedula: Optional[str] = None
    direccion: Optional[str] = None
    puntos_bonus: Optional[int] = Field(default=None, validation_alias=AliasChoices("puntos_bonus", "puntosBonus"))
    codigo_referido: Optional[str] = Field(default=None, validation_alias=AliasChoices("codigo_referido", "codigoReferido"))


class LoginRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    nombre_usuario: Optional[str] = Field(default=None, validation_alias=AliasChoices("nombre_usuario", "nombreUsuario"))
    correo: Optional[str] = None
    contrasena: str = ""


class UsarReferidoRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    codigo: str


class SolicitarRecuperacionRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    correo: str


class ValidarTokenRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    token: str


class RestablecerContrasenaRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    token: str
    nueva_contrasena: str = Field(..., validation_alias=AliasChoices("nueva_contrasena", "nuevaContrasena"))


class QuickAccountRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    nombreCompleto: str = Field(..., validation_alias=AliasChoices("nombreCompleto", "nombre_completo"))
    correo: str
    telefono: Optional[str] = None
    cedula: Optional[str] = None
    direccion: Optional[str] = None
    ciudad: Optional[str] = None
    placa: str
    marca: str
    modelo: str
    anio: Optional[int] = 2024
    kilometraje: Optional[int] = 0
    cilindraje: Optional[int] = 150
    nombreMoto: Optional[str] = Field(default=None, validation_alias=AliasChoices("nombreMoto", "nombre_moto"))
    tipoMoto: Optional[str] = Field(default=None, validation_alias=AliasChoices("tipoMoto", "tipo_moto"))
    rutaImagenMotos: Optional[str] = Field(default=None, validation_alias=AliasChoices("rutaImagenMotos", "ruta_imagen_motos"))

