from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, AliasChoices


class FacturaCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id_usuario: Optional[int] = Field(default=None, validation_alias=AliasChoices("id_usuario", "idUsuario"))
    costo_total: float = Field(default=0.0, validation_alias=AliasChoices("costo_total", "costoTotal"))
    cliente_nombre: Optional[str] = Field(default=None, validation_alias=AliasChoices("cliente_nombre", "clienteNombre"))
    cliente_cedula: Optional[str] = Field(default=None, validation_alias=AliasChoices("cliente_cedula", "clienteCedula"))
    cliente_telefono: Optional[str] = Field(default=None, validation_alias=AliasChoices("cliente_telefono", "clienteTelefono"))
    cliente_correo: Optional[str] = Field(default=None, validation_alias=AliasChoices("cliente_correo", "clienteCorreo"))
    cliente_direccion: Optional[str] = Field(default=None, validation_alias=AliasChoices("cliente_direccion", "clienteDireccion"))
    cliente_tipo: Optional[str] = Field(default="SISTEMA", validation_alias=AliasChoices("cliente_tipo", "clienteTipo"))
    origen_venta: Optional[str] = Field(default="TALLER", validation_alias=AliasChoices("origen_venta", "origenVenta"))


class FacturaUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id_usuario: Optional[int] = Field(default=None, validation_alias=AliasChoices("id_usuario", "idUsuario"))
    costo_total: Optional[float] = Field(default=None, validation_alias=AliasChoices("costo_total", "costoTotal"))
    cliente_nombre: Optional[str] = Field(default=None, validation_alias=AliasChoices("cliente_nombre", "clienteNombre"))
    cliente_cedula: Optional[str] = Field(default=None, validation_alias=AliasChoices("cliente_cedula", "clienteCedula"))
    cliente_telefono: Optional[str] = Field(default=None, validation_alias=AliasChoices("cliente_telefono", "clienteTelefono"))
    cliente_correo: Optional[str] = Field(default=None, validation_alias=AliasChoices("cliente_correo", "clienteCorreo"))
    cliente_direccion: Optional[str] = Field(default=None, validation_alias=AliasChoices("cliente_direccion", "clienteDireccion"))
    cliente_tipo: Optional[str] = Field(default=None, validation_alias=AliasChoices("cliente_tipo", "clienteTipo"))
    origen_venta: Optional[str] = Field(default=None, validation_alias=AliasChoices("origen_venta", "origenVenta"))


class DetalleFacturaCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id_factura: int = Field(..., validation_alias=AliasChoices("id_factura", "idFactura"))
    id_producto: Optional[int] = Field(default=None, validation_alias=AliasChoices("id_producto", "idProducto"))
    descripcion: Optional[str] = None
    cantidad: int = 1
    precio_unitario: Optional[float] = Field(default=None, validation_alias=AliasChoices("precio_unitario", "precioUnitario"))
    subtotal: Optional[float] = None


class PrepararCobroRequest(BaseModel):
    """Preparar la liquidación previa al cobro (Proceso 10 / Fin-1)."""
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id_registro: int = Field(..., validation_alias=AliasChoices("id_registro", "idRegistro"))
    descuento: Optional[float] = 0.0
    tarifa_hora_mecanico: Optional[float] = Field(default=10.0, validation_alias=AliasChoices("tarifa_hora_mecanico", "tarifaHoraMecanico"))
    observaciones: Optional[str] = None


class ConfirmarPagoRequest(BaseModel):
    """Registro y confirmación del pago para emisión de Nota de Venta (Procesos 11, 11.1 y 12)."""
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    metodo_pago: str = Field(default="EFECTIVO", validation_alias=AliasChoices("metodo_pago", "metodoPago"))  # EFECTIVO, TRANSFERENCIA, TARJETA
    monto_recibido: float = Field(..., ge=0.0, validation_alias=AliasChoices("monto_recibido", "montoRecibido", "monto"))
    numero_referencia: Optional[str] = Field(default=None, validation_alias=AliasChoices("numero_referencia", "numeroReferencia"))
    comprobante_url: Optional[str] = Field(default=None, validation_alias=AliasChoices("comprobante_url", "comprobanteUrl"))
    id_usuario_cajero: Optional[int] = Field(default=None, validation_alias=AliasChoices("id_usuario_cajero", "idUsuarioCajero"))


