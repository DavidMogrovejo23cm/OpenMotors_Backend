from typing import List, Optional, Literal
from pydantic import BaseModel, ConfigDict, Field, AliasChoices


class PerfilLaboralUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore", str_strip_whitespace=True)

    cargo: str = Field(default="Mecánico", min_length=2, max_length=100)
    especialidad: Optional[str] = Field(default=None, max_length=150)
    fecha_ingreso: Optional[str] = Field(default=None, validation_alias=AliasChoices("fecha_ingreso", "fechaIngreso"))
    tipo_contrato: Optional[str] = Field(default="TIEMPO_COMPLETO", validation_alias=AliasChoices("tipo_contrato", "tipoContrato"))
    modalidad_pago: Literal["HORA", "DIA", "SUELDO", "POR_TRABAJO", "COMISION"] = Field(
        default="POR_TRABAJO", validation_alias=AliasChoices("modalidad_pago", "modalidadPago")
    )
    tarifa_hora: float = Field(default=0.0, ge=0.0, allow_inf_nan=False, validation_alias=AliasChoices("tarifa_hora", "tarifaHora"))
    salario_base: float = Field(default=0.0, ge=0.0, allow_inf_nan=False, validation_alias=AliasChoices("salario_base", "salarioBase"))
    contacto_emergencia: Optional[str] = Field(default=None, max_length=150, validation_alias=AliasChoices("contacto_emergencia", "contactoEmergencia"))
    observaciones: Optional[str] = Field(default=None, max_length=500)


class HorarioDiaInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore", str_strip_whitespace=True)

    dia_semana: int = Field(..., ge=0, le=6, validation_alias=AliasChoices("dia_semana", "diaSemana"))
    es_laborable: bool = Field(default=True, validation_alias=AliasChoices("es_laborable", "esLaborable"))
    hora_entrada: str = Field(default="08:00", validation_alias=AliasChoices("hora_entrada", "horaEntrada"))
    hora_salida: str = Field(default="17:00", validation_alias=AliasChoices("hora_salida", "horaSalida"))
    minutos_descanso: int = Field(default=60, ge=0, le=480, validation_alias=AliasChoices("minutos_descanso", "minutosDescanso"))
    turno: str = Field(default="DIURNO", max_length=40)


class HorariosUsuarioUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    horarios: List[HorarioDiaInput] = Field(..., min_length=1)


class AsistenciaCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore", str_strip_whitespace=True)

    id_usuario: int = Field(..., ge=1, validation_alias=AliasChoices("id_usuario", "idUsuario"))
    fecha: Optional[str] = None
    turno: str = Field(default="UNICO", min_length=1, max_length=40)
    estado: Literal["PRESENTE", "TARDANZA", "FALTA", "PERMISO", "DESCANSO"] = "PRESENTE"
    hora_entrada: Optional[str] = Field(default=None, validation_alias=AliasChoices("hora_entrada", "horaEntrada"))
    hora_salida: Optional[str] = Field(default=None, validation_alias=AliasChoices("hora_salida", "horaSalida"))
    minutos_descanso: int = Field(default=0, ge=0, le=480, validation_alias=AliasChoices("minutos_descanso", "minutosDescanso"))
    horas_trabajadas: Optional[float] = Field(default=None, ge=0.0, le=24.0, allow_inf_nan=False, validation_alias=AliasChoices("horas_trabajadas", "horasTrabajadas"))
    observaciones: Optional[str] = Field(default=None, max_length=500)


class AsistenciaUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore", str_strip_whitespace=True)

    estado: Optional[Literal["PRESENTE", "TARDANZA", "FALTA", "PERMISO", "DESCANSO"]] = None
    hora_entrada: Optional[str] = Field(default=None, validation_alias=AliasChoices("hora_entrada", "horaEntrada"))
    hora_salida: Optional[str] = Field(default=None, validation_alias=AliasChoices("hora_salida", "horaSalida"))
    minutos_descanso: Optional[int] = Field(default=None, ge=0, le=480, validation_alias=AliasChoices("minutos_descanso", "minutosDescanso"))
    horas_trabajadas: Optional[float] = Field(default=None, ge=0.0, le=24.0, allow_inf_nan=False, validation_alias=AliasChoices("horas_trabajadas", "horasTrabajadas"))
    observaciones: Optional[str] = Field(default=None, max_length=500)
