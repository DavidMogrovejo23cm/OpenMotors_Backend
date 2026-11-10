from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field, AliasChoices


class TipoCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    nombre: str
    descripcion: Optional[str] = None
    id_producto: Optional[int] = Field(default=None, validation_alias=AliasChoices("id_producto", "idProducto"))
    concepto_manual: Optional[str] = Field(default=None, validation_alias=AliasChoices("concepto_manual", "conceptoManual"))
    concepto_cantidad: Optional[int] = Field(default=1, validation_alias=AliasChoices("concepto_cantidad", "conceptoCantidad"))
    concepto_precio_unitario: Optional[float] = Field(
        default=0.0, validation_alias=AliasChoices("concepto_precio_unitario", "conceptoPrecioUnitario")
    )


class RegistroCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    fecha: Optional[str] = None
    fecha_entrega_estimada: Optional[str] = Field(
        default=None, validation_alias=AliasChoices("fecha_entrega_estimada", "fechaEntregaEstimada")
    )
    descripcion: Optional[str] = None
    observaciones: Optional[str] = None
    costo_total: float = Field(default=0.0, validation_alias=AliasChoices("costo_total", "costoTotal"))
    id_moto: int = Field(..., validation_alias=AliasChoices("id_moto", "idMoto"))
    id_encargado: Optional[int] = Field(default=None, validation_alias=AliasChoices("id_encargado", "idEncargado"))
    id_tipo: Optional[int] = Field(default=None, validation_alias=AliasChoices("id_tipo", "idTipo"))
    id_factura: Optional[int] = Field(default=None, validation_alias=AliasChoices("id_factura", "idFactura"))
    kilometraje: Optional[int] = None
    estado: Optional[int] = 1


class DetalleDiagnosticoInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    parte: str
    estado: str
    observacion: Optional[str] = None


class DiagnosticoCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id_moto: int = Field(..., validation_alias=AliasChoices("id_moto", "idMoto"))
    id_mecanico: int = Field(..., validation_alias=AliasChoices("id_mecanico", "idMecanico"))
    kilometraje_ingreso: Optional[int] = Field(
        default=None, validation_alias=AliasChoices("kilometraje_ingreso", "kilometrajeIngreso")
    )
    observaciones_generales: Optional[str] = Field(
        default=None, validation_alias=AliasChoices("observaciones_generales", "observacionesGenerales")
    )
    detalles: List[DetalleDiagnosticoInput] = []
