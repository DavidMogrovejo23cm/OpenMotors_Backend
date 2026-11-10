from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.core.database import Base


class Factura(Base):
    __tablename__ = "facturas"

    id_factura = Column("id_factura", Integer, primary_key=True, index=True, autoincrement=True)
    fecha_emision = Column("fecha_emision", DateTime, nullable=False, default=datetime.now)
    id_usuario = Column("id_usuario", Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True, index=True)
    costo_total = Column("costo_total", Float, nullable=False, default=0.0)
    cliente_nombre = Column("cliente_nombre", String(150), nullable=True)
    cliente_cedula = Column("cliente_cedula", String(30), nullable=True)
    cliente_telefono = Column("cliente_telefono", String(30), nullable=True)
    cliente_correo = Column("cliente_correo", String(150), nullable=True)
    cliente_direccion = Column("cliente_direccion", String(255), nullable=True)
    cliente_tipo = Column("cliente_tipo", String(30), nullable=True, default="SISTEMA")
    origen_venta = Column("origen_venta", String(30), nullable=True, default="TALLER")

    detalles = relationship("DetalleFactura", back_populates="factura", cascade="all, delete-orphan", lazy="select")

    def to_dict(self) -> dict:
        return {
            "id_factura": self.id_factura,
            "fecha_emision": self.fecha_emision.isoformat() if self.fecha_emision else datetime.now().isoformat(),
            "id_usuario": self.id_usuario,
            "costo_total": round(float(self.costo_total or 0.0), 2),
            "cliente_nombre": self.cliente_nombre,
            "cliente_cedula": self.cliente_cedula,
            "cliente_telefono": self.cliente_telefono,
            "cliente_correo": self.cliente_correo,
            "cliente_direccion": self.cliente_direccion,
            "cliente_tipo": self.cliente_tipo or "SISTEMA",
            "origen_venta": self.origen_venta or "TALLER",
        }


class DetalleFactura(Base):
    __tablename__ = "detalles_factura"

    id_detalle = Column("id_detalle", Integer, primary_key=True, index=True, autoincrement=True)
    id_factura = Column("id_factura", Integer, ForeignKey("facturas.id_factura", ondelete="CASCADE"), nullable=False, index=True)
    id_producto = Column("id_producto", Integer, ForeignKey("productos.id_producto", ondelete="SET NULL"), nullable=True)
    descripcion = Column("descripcion", String(255), nullable=False)
    cantidad = Column("cantidad", Integer, nullable=False, default=1)
    precio_unitario = Column("precio_unitario", Float, nullable=False, default=0.0)
    subtotal = Column("subtotal", Float, nullable=False, default=0.0)

    factura = relationship("Factura", back_populates="detalles")
    producto = relationship("Producto", lazy="joined")

    def to_dict(self) -> dict:
        return {
            "id_detalle": self.id_detalle,
            "idDetalleFactura": self.id_detalle,
            "id_factura": self.id_factura,
            "idFactura": self.id_factura,
            "id_producto": self.id_producto,
            "idProducto": self.id_producto,
            "descripcion": self.descripcion,
            "cantidad": int(self.cantidad or 1),
            "precio_unitario": round(float(self.precio_unitario or 0.0), 2),
            "precioUnitario": round(float(self.precio_unitario or 0.0), 2),
            "subtotal": round(float(self.subtotal or 0.0), 2),
        }

