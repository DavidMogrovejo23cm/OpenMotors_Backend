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
    id_vehiculo: int = Field(
        ...,
        validation_alias=AliasChoices("id_vehiculo", "idVehiculo", "id_moto", "idMoto"),
    )
    id_encargado: Optional[int] = Field(default=None, validation_alias=AliasChoices("id_encargado", "idEncargado"))
    id_tipo: Optional[int] = Field(default=None, validation_alias=AliasChoices("id_tipo", "idTipo"))
    id_factura: Optional[int] = Field(default=None, validation_alias=AliasChoices("id_factura", "idFactura"))
    kilometraje: Optional[int] = None
    estado: Optional[int] = 1


class DetalleDiagnosticoInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    sistema: Optional[str] = "GENERAL"
    parte: str
    estado: str
    observacion: Optional[str] = None
    foto_evidencia: Optional[str] = Field(default=None, validation_alias=AliasChoices("foto_evidencia", "fotoEvidencia"))
    requiere_repuesto: Optional[bool] = Field(default=False, validation_alias=AliasChoices("requiere_repuesto", "requiereRepuesto"))


class DiagnosticoCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id_vehiculo: int = Field(
        ...,
        validation_alias=AliasChoices("id_vehiculo", "idVehiculo", "id_moto", "idMoto"),
    )
    id_mecanico: int = Field(..., validation_alias=AliasChoices("id_mecanico", "idMecanico"))
    id_registro: Optional[int] = Field(default=None, validation_alias=AliasChoices("id_registro", "idRegistro"))
    id_recepcion: Optional[int] = Field(default=None, validation_alias=AliasChoices("id_recepcion", "idRecepcion"))
    kilometraje_ingreso: Optional[int] = Field(
        default=None, validation_alias=AliasChoices("kilometraje_ingreso", "kilometrajeIngreso")
    )
    escaner_utilizado: Optional[str] = Field(
        default=None, validation_alias=AliasChoices("escaner_utilizado", "escanerUtilizado")
    )
    codigos_dtc: Optional[str] = Field(
        default=None, validation_alias=AliasChoices("codigos_dtc", "codigosDtc", "codigosError")
    )
    descripcion_escaner: Optional[str] = Field(
        default=None, validation_alias=AliasChoices("descripcion_escaner", "descripcionEscaner")
    )
    observaciones_generales: Optional[str] = Field(
        default=None, validation_alias=AliasChoices("observaciones_generales", "observacionesGenerales")
    )
    problemas_adicionales: Optional[str] = Field(
        default=None, validation_alias=AliasChoices("problemas_adicionales", "problemasAdicionales")
    )
    fotos_problemas: Optional[str] = Field(
        default=None, validation_alias=AliasChoices("fotos_problemas", "fotosProblemas")
    )
    detalles: List[DetalleDiagnosticoInput] = []


class RecepcionCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id_vehiculo: int = Field(
        ...,
        validation_alias=AliasChoices("id_vehiculo", "idVehiculo", "id_moto", "idMoto"),
    )
    id_encargado: Optional[int] = Field(default=None, validation_alias=AliasChoices("id_encargado", "idEncargado"))
    id_registro: Optional[int] = Field(default=None, validation_alias=AliasChoices("id_registro", "idRegistro"))
    kilometraje: int = Field(..., ge=0)
    nivel_combustible: str = Field(default="1/2", validation_alias=AliasChoices("nivel_combustible", "nivelCombustible"))
    luces_tablero: Optional[str] = Field(default=None, validation_alias=AliasChoices("luces_tablero", "lucesTablero"))
    danos_previos: Optional[str] = Field(default=None, validation_alias=AliasChoices("danos_previos", "danosPrevios"))
    foto_frente: Optional[str] = Field(default=None, validation_alias=AliasChoices("foto_frente", "fotoFrente"))
    foto_posterior: Optional[str] = Field(default=None, validation_alias=AliasChoices("foto_posterior", "fotoPosterior"))
    foto_lateral_izq: Optional[str] = Field(default=None, validation_alias=AliasChoices("foto_lateral_izq", "fotoLateralIzq"))
    foto_lateral_der: Optional[str] = Field(default=None, validation_alias=AliasChoices("foto_lateral_der", "fotoLateralDer"))
    firma_cliente: Optional[str] = Field(default=None, validation_alias=AliasChoices("firma_cliente", "firmaCliente"))
    observaciones: Optional[str] = None
    crear_orden_automatica: Optional[bool] = Field(
        default=True, validation_alias=AliasChoices("crear_orden_automatica", "crearOrdenAutomatica")
    )


class RecepcionUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    kilometraje: Optional[int] = Field(default=None, ge=0)
    nivel_combustible: Optional[str] = Field(default=None, validation_alias=AliasChoices("nivel_combustible", "nivelCombustible"))
    luces_tablero: Optional[str] = Field(default=None, validation_alias=AliasChoices("luces_tablero", "lucesTablero"))
    danos_previos: Optional[str] = Field(default=None, validation_alias=AliasChoices("danos_previos", "danosPrevios"))
    foto_frente: Optional[str] = Field(default=None, validation_alias=AliasChoices("foto_frente", "fotoFrente"))
    foto_posterior: Optional[str] = Field(default=None, validation_alias=AliasChoices("foto_posterior", "fotoPosterior"))
    foto_lateral_izq: Optional[str] = Field(default=None, validation_alias=AliasChoices("foto_lateral_izq", "fotoLateralIzq"))
    foto_lateral_der: Optional[str] = Field(default=None, validation_alias=AliasChoices("foto_lateral_der", "fotoLateralDer"))
    firma_cliente: Optional[str] = Field(default=None, validation_alias=AliasChoices("firma_cliente", "firmaCliente"))
    observaciones: Optional[str] = None
    id_registro: Optional[int] = Field(default=None, validation_alias=AliasChoices("id_registro", "idRegistro"))
    id_encargado: Optional[int] = Field(default=None, validation_alias=AliasChoices("id_encargado", "idEncargado"))


class ItemPresupuestoInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    tipo_item: str = Field(default="REPUESTO", validation_alias=AliasChoices("tipo_item", "tipoItem"))  # "REPUESTO" o "MANO_OBRA"
    id_producto: Optional[int] = Field(default=None, validation_alias=AliasChoices("id_producto", "idProducto"))
    descripcion: str
    cantidad: float = Field(default=1.0, ge=0.01)
    precio_unitario: float = Field(default=0.0, ge=0.0, validation_alias=AliasChoices("precio_unitario", "precioUnitario"))
    es_adicional: Optional[bool] = Field(default=False, validation_alias=AliasChoices("es_adicional", "esAdicional"))


class PresupuestoCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id_registro: int = Field(..., validation_alias=AliasChoices("id_registro", "idRegistro"))
    id_vehiculo: int = Field(
        ...,
        validation_alias=AliasChoices("id_vehiculo", "idVehiculo", "id_moto", "idMoto"),
    )
    id_diagnostico: Optional[int] = Field(default=None, validation_alias=AliasChoices("id_diagnostico", "idDiagnostico"))
    id_usuario: Optional[int] = Field(default=None, validation_alias=AliasChoices("id_usuario", "idUsuario"))
    descuento: Optional[float] = 0.0
    costo_diagnostico: Optional[float] = Field(default=0.0, validation_alias=AliasChoices("costo_diagnostico", "costoDiagnostico"))
    observaciones: Optional[str] = None
    items: List[ItemPresupuestoInput] = []


class PresupuestoUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    descuento: Optional[float] = None
    costo_diagnostico: Optional[float] = Field(default=None, validation_alias=AliasChoices("costo_diagnostico", "costoDiagnostico"))
    observaciones: Optional[str] = None
    items: Optional[List[ItemPresupuestoInput]] = None


class PresupuestoDecisionRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    decision: str  # "APROBADO_TOTAL", "APROBADO_PARCIAL", "RECHAZADO"
    items_aprobados_ids: Optional[List[int]] = Field(
        default=None, validation_alias=AliasChoices("items_aprobados_ids", "itemsAprobadosIds")
    )
    motivo: Optional[str] = None
    cobrar_solo_diagnostico: Optional[bool] = Field(
        default=False, validation_alias=AliasChoices("cobrar_solo_diagnostico", "cobrarSoloDiagnostico")
    )


class BitacoraReparacionCreate(BaseModel):
    """Registro de horas trabajadas y fotos de la reparación (Proceso 7)."""
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id_registro: int = Field(..., validation_alias=AliasChoices("id_registro", "idRegistro"))
    id_mecanico: Optional[int] = Field(default=None, validation_alias=AliasChoices("id_mecanico", "idMecanico"))
    horas_trabajadas: float = Field(default=0.0, ge=0.0, validation_alias=AliasChoices("horas_trabajadas", "horasTrabajadas"))
    descripcion_trabajo: str = Field(..., validation_alias=AliasChoices("descripcion_trabajo", "descripcionTrabajo"))
    fotos_evidencia: Optional[str] = Field(default=None, validation_alias=AliasChoices("fotos_evidencia", "fotosEvidencia"))
    repuestos_instalados: Optional[str] = Field(default=None, validation_alias=AliasChoices("repuestos_instalados", "repuestosInstalados"))


class DanoAdicionalCreate(BaseModel):
    """Reporte de nuevo daño detectado durante la reparación (Proceso 7.1)."""
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id_registro: int = Field(..., validation_alias=AliasChoices("id_registro", "idRegistro"))
    id_mecanico: Optional[int] = Field(default=None, validation_alias=AliasChoices("id_mecanico", "idMecanico"))
    descripcion: str
    fotos_evidencia: Optional[str] = Field(default=None, validation_alias=AliasChoices("fotos_evidencia", "fotosEvidencia"))
    repuesto_sugerido: Optional[str] = Field(default=None, validation_alias=AliasChoices("repuesto_sugerido", "repuestoSugerido"))
    id_producto: Optional[int] = Field(default=None, validation_alias=AliasChoices("id_producto", "idProducto"))
    costo_estimado: Optional[float] = Field(default=0.0, ge=0.0, validation_alias=AliasChoices("costo_estimado", "costoEstimado"))


class DanoAdicionalDecisionRequest(BaseModel):
    """Respuesta del cliente a daño adicional (Proceso 7.1)."""
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    aprobado: bool
    observaciones_cliente: Optional[str] = Field(default=None, validation_alias=AliasChoices("observaciones_cliente", "observacionesCliente"))


class ControlCalidadCreate(BaseModel):
    """Inspección post-reparación y escaneo OBD2 (Procesos 8, 8.1 y 9)."""
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id_registro: int = Field(..., validation_alias=AliasChoices("id_registro", "idRegistro"))
    id_revisor: Optional[int] = Field(default=None, validation_alias=AliasChoices("id_revisor", "idRevisor"))
    paso_inspeccion: bool = Field(..., validation_alias=AliasChoices("paso_inspeccion", "pasoInspeccion"))
    escaner_utilizado: Optional[str] = Field(default=None, validation_alias=AliasChoices("escaner_utilizado", "escanerUtilizado"))
    codigos_dtc_detectados: Optional[str] = Field(default="Sin códigos de falla", validation_alias=AliasChoices("codigos_dtc_detectados", "codigosDtcDetectados"))
    observaciones: Optional[str] = None
    motivo_devolucion: Optional[str] = Field(default=None, validation_alias=AliasChoices("motivo_devolucion", "motivoDevolucion"))


class EntregaVehiculoCreate(BaseModel):
    """Entrega formal del vehículo al cliente con validación de pago y firma (Proceso 15)."""
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id_registro: int = Field(..., validation_alias=AliasChoices("id_registro", "idRegistro"))
    persona_recibe: str = Field(..., validation_alias=AliasChoices("persona_recibe", "personaRecibe"))
    cedula_recibe: Optional[str] = Field(default=None, validation_alias=AliasChoices("cedula_recibe", "cedulaRecibe"))
    firma_cliente_entrega: Optional[str] = Field(default=None, validation_alias=AliasChoices("firma_cliente_entrega", "firmaClienteEntrega", "firma"))
    kilometraje_salida: Optional[int] = Field(default=None, validation_alias=AliasChoices("kilometraje_salida", "kilometrajeSalida"))
    observaciones: Optional[str] = None
    id_usuario_entrega: Optional[int] = Field(default=None, validation_alias=AliasChoices("id_usuario_entrega", "idUsuarioEntrega"))



