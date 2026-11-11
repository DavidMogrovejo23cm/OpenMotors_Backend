from datetime import date, datetime
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.modules.usuarios.models import Usuario  # noqa: F401


class Categoria(Base):
    __tablename__ = "categorias"

    id_categoria = Column("id_categoria", Integer, primary_key=True, index=True, autoincrement=True)
    nombre = Column("nombre", String(100), nullable=False)
    descripcion = Column("descripcion", String(255), nullable=True)

    def to_dict(self) -> dict:
        return {
            "id_categoria": self.id_categoria,
            "nombre": self.nombre,
            "descripcion": self.descripcion,
        }


class Producto(Base):
    __tablename__ = "productos"

    id_producto = Column("id_producto", Integer, primary_key=True, index=True, autoincrement=True)
    codigo_barras = Column("codigo_barras", String(100), nullable=True, index=True)
    codigo_proveedor = Column("codigo_proveedor", String(50), nullable=False, default="PROV-001")
    codigo_distribuidor = Column("codigo_distribuidor", String(50), nullable=False, default="DIST-001")
    codigo_personal = Column("codigo_personal", String(50), nullable=False, unique=True, index=True)
    nombre = Column("nombre", String(150), nullable=False)
    marca = Column("marca", String(100), nullable=True, default="Genérico")
    proveedor = Column("proveedor", String(150), nullable=True)
    descripcion = Column("descripcion", String(500), nullable=False, default="")
    costo = Column("costo", Float, nullable=False, default=0.0)
    pvp = Column("pvp", Float, nullable=False, default=0.0)
    stock = Column("stock", Integer, nullable=False, default=0)
    stock_minimo = Column("stock_minimo", Integer, nullable=False, default=2)
    stock_reservado = Column("stock_reservado", Integer, nullable=False, default=0)
    duracion_estimada_km = Column("duracion_estimada_km", Integer, nullable=True)
    ubicacion_bodega = Column("ubicacion_bodega", String(100), nullable=True)
    fecha_registro = Column("fecha_registro", Date, nullable=False, default=date.today)
    fecha_modificacion = Column("fecha_modificacion", DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)
    id_categoria = Column("id_categoria", Integer, ForeignKey("categorias.id_categoria"), nullable=False)
    ruta_imagenproductos = Column("ruta_imagenproductos", String(500), nullable=True)

    categoria = relationship("Categoria", lazy="joined")

    @property
    def alerta_stock_minimo(self) -> bool:
        return int(self.stock or 0) <= int(self.stock_minimo or 2)

    @property
    def stock_disponible(self) -> int:
        return max(0, int(self.stock or 0) - int(self.stock_reservado or 0))

    def to_dict(self) -> dict:
        return {
            "id_producto": self.id_producto,
            "codigo_barras": self.codigo_barras or self.codigo_personal,
            "codigo_proveedor": self.codigo_proveedor,
            "codigo_distribuidor": self.codigo_distribuidor,
            "codigo_personal": self.codigo_personal,
            "nombre": self.nombre,
            "marca": self.marca or "Genérico",
            "proveedor": self.proveedor,
            "descripcion": self.descripcion,
            "costo": round(float(self.costo or 0.0), 2),
            "pvp": round(float(self.pvp or 0.0), 2),
            "stock": int(self.stock or 0),
            "stock_minimo": int(self.stock_minimo or 2),
            "stock_reservado": int(self.stock_reservado or 0),
            "stock_disponible": self.stock_disponible,
            "alerta_stock_minimo": self.alerta_stock_minimo,
            "duracion_estimada_km": self.duracion_estimada_km,
            "ubicacion_bodega": self.ubicacion_bodega,
            "fecha_registro": self.fecha_registro.isoformat() if self.fecha_registro else date.today().isoformat(),
            "fecha_modificacion": self.fecha_modificacion.isoformat() if self.fecha_modificacion else datetime.now().isoformat(),
            "id_categoria": self.id_categoria,
            "categoria_nombre": self.categoria.nombre if self.categoria else None,
            "ruta_imagenproductos": self.ruta_imagenproductos,
        }


class MovimientoKardex(Base):
    """
    Control de movimientos de Kardex para entradas y salidas de bodega.
    Soporta registro por escaneo de código de barras desde el móvil (Procesos Inv-1 a Inv-6).
    """
    __tablename__ = "movimientos_kardex"

    id_movimiento = Column("id_movimiento", Integer, primary_key=True, index=True, autoincrement=True)
    id_producto = Column("id_producto", Integer, ForeignKey("productos.id_producto", ondelete="CASCADE"), nullable=False, index=True)
    tipo_movimiento = Column("tipo_movimiento", String(20), nullable=False)  # ENTRADA | SALIDA | AJUSTE
    origen = Column("origen", String(50), nullable=False, default="ESCANEO_MANUAL")
    cantidad = Column("cantidad", Integer, nullable=False)
    stock_anterior = Column("stock_anterior", Integer, nullable=False)
    stock_nuevo = Column("stock_nuevo", Integer, nullable=False)
    costo_unitario = Column("costo_unitario", Float, nullable=False, default=0.0)
    precio_unitario = Column("precio_unitario", Float, nullable=False, default=0.0)
    codigo_escaneado = Column("codigo_escaneado", String(100), nullable=True)
    id_registro = Column("id_registro", Integer, ForeignKey("registros.id_registro", ondelete="SET NULL"), nullable=True, index=True)
    id_usuario = Column("id_usuario", Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True, index=True)
    numero_factura_proveedor = Column("numero_factura_proveedor", String(100), nullable=True)
    comprobante_url = Column("comprobante_url", String(500), nullable=True)
    motivo = Column("motivo", String(500), nullable=True)
    fecha = Column("fecha", DateTime, nullable=False, default=datetime.now)

    producto = relationship("Producto", lazy="joined")
    usuario = relationship("Usuario", lazy="joined")

    def to_dict(self) -> dict:
        return {
            "id_movimiento": self.id_movimiento,
            "id_producto": self.id_producto,
            "producto_nombre": self.producto.nombre if self.producto else None,
            "codigo_personal": self.producto.codigo_personal if self.producto else None,
            "tipo_movimiento": self.tipo_movimiento,
            "origen": self.origen,
            "cantidad": self.cantidad,
            "stock_anterior": self.stock_anterior,
            "stock_nuevo": self.stock_nuevo,
            "costo_unitario": round(float(self.costo_unitario or 0.0), 2),
            "precio_unitario": round(float(self.precio_unitario or 0.0), 2),
            "codigo_escaneado": self.codigo_escaneado,
            "id_registro": self.id_registro,
            "id_usuario": self.id_usuario,
            "nombre_usuario": self.usuario.nombre_completo if self.usuario else None,
            "numero_factura_proveedor": self.numero_factura_proveedor,
            "comprobante_url": self.comprobante_url,
            "motivo": self.motivo,
            "fecha": self.fecha.isoformat() if self.fecha else datetime.now().isoformat(),
        }


class ContactoProveedor(Base):
    __tablename__ = "contacto_proveedor"

    codigo = Column("codigo", String(100), primary_key=True, index=True)
    nombre = Column("nombre", String(150), nullable=True)
    telefono = Column("telefono", String(30), nullable=True)
    email = Column("email", String(150), nullable=True)
    producto = Column("producto", String(255), nullable=True)

    def to_dict(self) -> dict:
        return {
            "codigo": self.codigo,
            "nombre": self.nombre,
            "telefono": self.telefono,
            "email": self.email,
            "producto": self.producto,
        }


class ReservaRepuesto(Base):
    """
    Control de reserva de repuestos aprobados para una orden de trabajo (Proceso 6 / Inv-4).
    Evita la sobreventa o asignación a otro cliente antes de su instalación.
    """
    __tablename__ = "reservas_repuesto"

    id_reserva = Column("id_reserva", Integer, primary_key=True, index=True, autoincrement=True)
    id_registro = Column("id_registro", Integer, ForeignKey("registros.id_registro", ondelete="CASCADE"), nullable=False, index=True)
    id_presupuesto = Column("id_presupuesto", Integer, ForeignKey("presupuestos.id_presupuesto", ondelete="SET NULL"), nullable=True, index=True)
    id_item_presupuesto = Column("id_item_presupuesto", Integer, ForeignKey("items_presupuesto.id_item", ondelete="SET NULL"), nullable=True)
    id_producto = Column("id_producto", Integer, ForeignKey("productos.id_producto", ondelete="CASCADE"), nullable=False, index=True)
    cantidad = Column("cantidad", Integer, nullable=False, default=1)
    estado = Column("estado", String(30), nullable=False, default="RESERVADO")  # RESERVADO, RETIRADO, LIBERADO
    fecha_reserva = Column("fecha_reserva", DateTime, nullable=False, default=datetime.now)
    fecha_retiro = Column("fecha_retiro", DateTime, nullable=True)
    fecha_liberacion = Column("fecha_liberacion", DateTime, nullable=True)
    id_usuario = Column("id_usuario", Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True)
    motivo_liberacion = Column("motivo_liberacion", String(255), nullable=True)

    producto = relationship("Producto", lazy="joined")
    usuario = relationship("Usuario", lazy="joined")

    def to_dict(self) -> dict:
        return {
            "id_reserva": self.id_reserva,
            "id_registro": self.id_registro,
            "id_presupuesto": self.id_presupuesto,
            "id_item_presupuesto": self.id_item_presupuesto,
            "id_producto": self.id_producto,
            "producto_nombre": self.producto.nombre if self.producto else None,
            "codigo_personal": self.producto.codigo_personal if self.producto else None,
            "codigo_barras": self.producto.codigo_barras if self.producto else None,
            "ubicacion_bodega": self.producto.ubicacion_bodega if self.producto else None,
            "cantidad": self.cantidad,
            "estado": self.estado,
            "fecha_reserva": self.fecha_reserva.isoformat() if self.fecha_reserva else datetime.now().isoformat(),
            "fecha_retiro": self.fecha_retiro.isoformat() if self.fecha_retiro else None,
            "fecha_liberacion": self.fecha_liberacion.isoformat() if self.fecha_liberacion else None,
            "id_usuario": self.id_usuario,
            "nombre_usuario": self.usuario.nombre_completo if self.usuario else None,
            "motivo_liberacion": self.motivo_liberacion,
        }


