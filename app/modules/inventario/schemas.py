from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field, AliasChoices


class CategoriaCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    nombre: str
    descripcion: Optional[str] = None


class ProductoCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    codigo_proveedor: str = Field(default="PROV-001", validation_alias=AliasChoices("codigo_proveedor", "codigoProveedor"))
    codigo_distribuidor: str = Field(default="DIST-001", validation_alias=AliasChoices("codigo_distribuidor", "codigoDistribuidor"))
    codigo_personal: str = Field(..., validation_alias=AliasChoices("codigo_personal", "codigoPersonal"))
    nombre: str
    descripcion: str = ""
    costo: float = 0.0
    pvp: float = 0.0
    stock: int = 0
    id_categoria: int = Field(..., validation_alias=AliasChoices("id_categoria", "idCategoria"))
    ruta_imagenproductos: Optional[str] = Field(
        default=None, validation_alias=AliasChoices("ruta_imagenproductos", "rutaImagenProductos")
    )


class ProductoUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    codigo_proveedor: Optional[str] = Field(default=None, validation_alias=AliasChoices("codigo_proveedor", "codigoProveedor"))
    codigo_distribuidor: Optional[str] = Field(default=None, validation_alias=AliasChoices("codigo_distribuidor", "codigoDistribuidor"))
    codigo_personal: Optional[str] = Field(default=None, validation_alias=AliasChoices("codigo_personal", "codigoPersonal"))
    nombre: Optional[str] = None
    descripcion: Optional[str] = None
    costo: Optional[float] = None
    pvp: Optional[float] = None
    stock: Optional[int] = None
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

