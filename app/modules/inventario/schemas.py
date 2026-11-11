from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field, AliasChoices


class CategoriaCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    nombre: str
    descripcion: Optional[str] = None


class ProductoCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    codigo_barras: Optional[str] = Field(default=None, validation_alias=AliasChoices("codigo_barras", "codigoBarras"))
    codigo_proveedor: str = Field(default="PROV-001", validation_alias=AliasChoices("codigo_proveedor", "codigoProveedor"))
    codigo_distribuidor: str = Field(default="DIST-001", validation_alias=AliasChoices("codigo_distribuidor", "codigoDistribuidor"))
    codigo_personal: str = Field(..., validation_alias=AliasChoices("codigo_personal", "codigoPersonal"))
    nombre: str
    marca: Optional[str] = "Genérico"
    proveedor: Optional[str] = None
    descripcion: str = ""
    costo: float = 0.0
    pvp: float = 0.0
    stock: int = 0
    stock_minimo: Optional[int] = Field(default=2, validation_alias=AliasChoices("stock_minimo", "stockMinimo"))
    duracion_estimada_km: Optional[int] = Field(default=None, validation_alias=AliasChoices("duracion_estimada_km", "duracionEstimadaKm"))
    ubicacion_bodega: Optional[str] = Field(default=None, validation_alias=AliasChoices("ubicacion_bodega", "ubicacionBodega"))
    id_categoria: int = Field(..., validation_alias=AliasChoices("id_categoria", "idCategoria"))
    ruta_imagenproductos: Optional[str] = Field(
        default=None, validation_alias=AliasChoices("ruta_imagenproductos", "rutaImagenProductos")
    )


class ProductoUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    codigo_barras: Optional[str] = Field(default=None, validation_alias=AliasChoices("codigo_barras", "codigoBarras"))
    codigo_proveedor: Optional[str] = Field(default=None, validation_alias=AliasChoices("codigo_proveedor", "codigoProveedor"))
    codigo_distribuidor: Optional[str] = Field(default=None, validation_alias=AliasChoices("codigo_distribuidor", "codigoDistribuidor"))
    codigo_personal: Optional[str] = Field(default=None, validation_alias=AliasChoices("codigo_personal", "codigoPersonal"))
    nombre: Optional[str] = None
    marca: Optional[str] = None
    proveedor: Optional[str] = None
    descripcion: Optional[str] = None
    costo: Optional[float] = None
    pvp: Optional[float] = None
    stock: Optional[int] = None
    stock_minimo: Optional[int] = Field(default=None, validation_alias=AliasChoices("stock_minimo", "stockMinimo"))
    duracion_estimada_km: Optional[int] = Field(default=None, validation_alias=AliasChoices("duracion_estimada_km", "duracionEstimadaKm"))
    ubicacion_bodega: Optional[str] = Field(default=None, validation_alias=AliasChoices("ubicacion_bodega", "ubicacionBodega"))
    id_categoria: Optional[int] = Field(default=None, validation_alias=AliasChoices("id_categoria", "idCategoria"))
    ruta_imagenproductos: Optional[str] = Field(
        default=None, validation_alias=AliasChoices("ruta_imagenproductos", "rutaImagenProductos")
    )


class VentaDirectaRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id_producto: int = Field(..., validation_alias=AliasChoices("id_producto", "idProducto"))
    cantidad: int = 1
    precio_unitario: Optional[float] = Field(default=None, validation_alias=AliasChoices("precio_unitario", "precioUnitario"))
    cliente_nombre: Optional[str] = Field(default=None, validation_alias=AliasChoices("cliente_nombre", "clienteNombre"))
    cliente_cedula: Optional[str] = Field(default=None, validation_alias=AliasChoices("cliente_cedula", "clienteCedula"))
    cliente_telefono: Optional[str] = Field(default=None, validation_alias=AliasChoices("cliente_telefono", "clienteTelefono"))
    cliente_correo: Optional[str] = Field(default=None, validation_alias=AliasChoices("cliente_correo", "clienteCorreo"))
    cliente_direccion: Optional[str] = Field(default=None, validation_alias=AliasChoices("cliente_direccion", "clienteDireccion"))
    cliente_tipo: Optional[str] = Field(default="EXTERNO", validation_alias=AliasChoices("cliente_tipo", "clienteTipo"))
    id_usuario: Optional[int] = Field(default=None, validation_alias=AliasChoices("id_usuario", "idUsuario"))


class ItemComprobanteVenta(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    nombre: str
    cantidad: int = 1
    precio_unitario: float = Field(default=0.0, validation_alias=AliasChoices("precio_unitario", "precioUnitario"))
    subtotal: float = 0.0


class ComprobanteVentaRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    correo: str
    nombre_cliente: Optional[str] = Field(default="Consumidor Final", validation_alias=AliasChoices("nombre_cliente", "nombreCliente"))
    cedula: Optional[str] = None
    telefono: Optional[str] = None
    direccion: Optional[str] = None
    id_factura: Optional[int] = Field(default=None, validation_alias=AliasChoices("id_factura", "idFactura"))
    items: List[ItemComprobanteVenta] = []
    total: float = 0.0


class ContactoProveedorRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    nombre: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None
    producto: Optional[str] = None


class EscaneoEntradaRequest(BaseModel):
    """Solicitud de ingreso a bodega escaneando con la cámara del celular."""
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    codigo_barras: str = Field(..., validation_alias=AliasChoices("codigo_barras", "codigoBarras", "codigo"))
    cantidad: int = Field(default=1, ge=1)
    costo_unitario: Optional[float] = Field(default=None, ge=0.0, validation_alias=AliasChoices("costo_unitario", "costoUnitario", "costo"))
    precio_venta: Optional[float] = Field(default=None, ge=0.0, validation_alias=AliasChoices("precio_venta", "precioVenta", "pvp"))
    numero_factura_proveedor: Optional[str] = Field(default=None, validation_alias=AliasChoices("numero_factura_proveedor", "numeroFacturaProveedor", "factura"))
    comprobante_url: Optional[str] = Field(default=None, validation_alias=AliasChoices("comprobante_url", "comprobanteUrl", "fotoFactura"))
    proveedor: Optional[str] = None
    origen: Optional[str] = "COMPRA_PROVEEDOR"
    id_usuario: Optional[int] = Field(default=None, validation_alias=AliasChoices("id_usuario", "idUsuario"))
    motivo: Optional[str] = None
    crear_si_no_existe: Optional[bool] = Field(default=False, validation_alias=AliasChoices("crear_si_no_existe", "crearSiNoExiste"))
    nombre: Optional[str] = None
    marca: Optional[str] = "Genérico"
    id_categoria: Optional[int] = Field(default=None, validation_alias=AliasChoices("id_categoria", "idCategoria"))
    stock_minimo: Optional[int] = Field(default=2, validation_alias=AliasChoices("stock_minimo", "stockMinimo"))
    duracion_estimada_km: Optional[int] = Field(default=None, validation_alias=AliasChoices("duracion_estimada_km", "duracionEstimadaKm"))


class EscaneoSalidaRequest(BaseModel):
    """Solicitud de salida/despacho de bodega escaneando con la cámara del celular."""
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    codigo_barras: str = Field(..., validation_alias=AliasChoices("codigo_barras", "codigoBarras", "codigo"))
    cantidad: int = Field(default=1, ge=1)
    id_registro: Optional[int] = Field(default=None, validation_alias=AliasChoices("id_registro", "idRegistro"))  # Orden de taller
    id_usuario: Optional[int] = Field(default=None, validation_alias=AliasChoices("id_usuario", "idUsuario"))
    origen: Optional[str] = "TALLER_ORDEN"  # TALLER_ORDEN, VENTA_MOSTRADOR, MERMA, etc.
    motivo: Optional[str] = None


class ReservaRepuestoCreate(BaseModel):
    """Reserva individual de un repuesto para una orden (Proceso 6 / Inv-4)."""
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id_registro: int = Field(..., validation_alias=AliasChoices("id_registro", "idRegistro"))
    id_producto: int = Field(..., validation_alias=AliasChoices("id_producto", "idProducto"))
    cantidad: int = Field(default=1, ge=1)
    id_presupuesto: Optional[int] = Field(default=None, validation_alias=AliasChoices("id_presupuesto", "idPresupuesto"))
    id_item_presupuesto: Optional[int] = Field(default=None, validation_alias=AliasChoices("id_item_presupuesto", "idItemPresupuesto"))
    id_usuario: Optional[int] = Field(default=None, validation_alias=AliasChoices("id_usuario", "idUsuario"))


class ReservaPresupuestoRequest(BaseModel):
    """Reserva todos los repuestos aprobados de un presupuesto para la orden (Proceso 6)."""
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id_presupuesto: int = Field(..., validation_alias=AliasChoices("id_presupuesto", "idPresupuesto"))
    id_registro: Optional[int] = Field(default=None, validation_alias=AliasChoices("id_registro", "idRegistro"))
    id_usuario: Optional[int] = Field(default=None, validation_alias=AliasChoices("id_usuario", "idUsuario"))


class AsignarMecanicoRequest(BaseModel):
    """Asignación de mecánico a la orden de trabajo (Proceso 6)."""
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id_mecanico: int = Field(..., validation_alias=AliasChoices("id_mecanico", "idMecanico", "id_encargado", "idEncargado"))
    observaciones: Optional[str] = None
    fecha_entrega_estimada: Optional[str] = Field(default=None, validation_alias=AliasChoices("fecha_entrega_estimada", "fechaEntregaEstimada"))


class LiberarReservaRequest(BaseModel):
    """Liberación de unidades reservadas (Proceso Inv-5.1)."""
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    motivo: Optional[str] = None
    id_usuario: Optional[int] = Field(default=None, validation_alias=AliasChoices("id_usuario", "idUsuario"))


