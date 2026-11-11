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


class NotaDeVenta(Base):
    """
    Nota de Venta numerada interna para el cliente (Procesos 10, 11, 12, 13 y 14).
    No emite factura electrónica ni SRI.
    Incluye desglose de cobro, estado de pago y cierre financiero de margen del taller.
    """
    __tablename__ = "notas_de_venta"

    id_nota_venta = Column("id_nota_venta", Integer, primary_key=True, index=True, autoincrement=True)
    numero_nota_venta = Column("numero_nota_venta", String(50), unique=True, index=True, nullable=False)
    id_registro = Column("id_registro", Integer, ForeignKey("registros.id_registro", ondelete="CASCADE"), nullable=False, index=True)
    id_usuario_cajero = Column("id_usuario_cajero", Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True)
    cliente_nombre = Column("cliente_nombre", String(150), nullable=False)
    cliente_cedula = Column("cliente_cedula", String(30), nullable=True)
    cliente_telefono = Column("cliente_telefono", String(30), nullable=True)
    cliente_correo = Column("cliente_correo", String(150), nullable=True)
    vehiculo_placa = Column("vehiculo_placa", String(30), nullable=True)
    vehiculo_descripcion = Column("vehiculo_descripcion", String(150), nullable=True)
    fecha_emision = Column("fecha_emision", DateTime, nullable=False, default=datetime.now)
    fecha_pago = Column("fecha_pago", DateTime, nullable=True)
    subtotal_repuestos = Column("subtotal_repuestos", Float, nullable=False, default=0.0)
    subtotal_mano_obra = Column("subtotal_mano_obra", Float, nullable=False, default=0.0)
    descuento = Column("descuento", Float, nullable=False, default=0.0)
    total = Column("total", Float, nullable=False, default=0.0)
    metodo_pago = Column("metodo_pago", String(30), nullable=False, default="EFECTIVO")  # EFECTIVO, TRANSFERENCIA, TARJETA
    numero_referencia_pago = Column("numero_referencia_pago", String(100), nullable=True)
    comprobante_url = Column("comprobante_url", String(500), nullable=True)
    estado_pago = Column("estado_pago", String(30), nullable=False, default="PENDIENTE_PAGO")  # PENDIENTE_PAGO | PAGADO
    costo_repuestos_taller = Column("costo_repuestos_taller", Float, nullable=False, default=0.0)
    horas_mecanico = Column("horas_mecanico", Float, nullable=False, default=0.0)
    tarifa_hora_mecanico = Column("tarifa_hora_mecanico", Float, nullable=False, default=0.0)
    pago_mecanico = Column("pago_mecanico", Float, nullable=False, default=0.0)
    ganancia_neta_taller = Column("ganancia_neta_taller", Float, nullable=False, default=0.0)
    observaciones = Column("observaciones", String(500), nullable=True)

    items = relationship("ItemNotaDeVenta", back_populates="nota_venta", cascade="all, delete-orphan", lazy="selectin")

    def to_dict(self) -> dict:
        return {
            "id_nota_venta": self.id_nota_venta,
            "numero_nota_venta": self.numero_nota_venta,
            "id_registro": self.id_registro,
            "id_usuario_cajero": self.id_usuario_cajero,
            "cliente_nombre": self.cliente_nombre,
            "cliente_cedula": self.cliente_cedula,
            "cliente_telefono": self.cliente_telefono,
            "cliente_correo": self.cliente_correo,
            "vehiculo_placa": self.vehiculo_placa,
            "vehiculo_descripcion": self.vehiculo_descripcion,
            "fecha_emision": self.fecha_emision.isoformat() if self.fecha_emision else datetime.now().isoformat(),
            "fecha_pago": self.fecha_pago.isoformat() if self.fecha_pago else None,
            "subtotal_repuestos": round(float(self.subtotal_repuestos or 0.0), 2),
            "subtotal_mano_obra": round(float(self.subtotal_mano_obra or 0.0), 2),
            "descuento": round(float(self.descuento or 0.0), 2),
            "total": round(float(self.total or 0.0), 2),
            "metodo_pago": self.metodo_pago,
            "numero_referencia_pago": self.numero_referencia_pago,
            "comprobante_url": self.comprobante_url,
            "estado_pago": self.estado_pago,
            "costo_repuestos_taller": round(float(self.costo_repuestos_taller or 0.0), 2),
            "horas_mecanico": round(float(self.horas_mecanico or 0.0), 2),
            "tarifa_hora_mecanico": round(float(self.tarifa_hora_mecanico or 0.0), 2),
            "pago_mecanico": round(float(self.pago_mecanico or 0.0), 2),
            "ganancia_neta_taller": round(float(self.ganancia_neta_taller or 0.0), 2),
            "observaciones": self.observaciones,
            "items": [it.to_dict() for it in self.items] if self.items else [],
        }


class ItemNotaDeVenta(Base):
    __tablename__ = "items_nota_de_venta"

    id_item = Column("id_item", Integer, primary_key=True, index=True, autoincrement=True)
    id_nota_venta = Column("id_nota_venta", Integer, ForeignKey("notas_de_venta.id_nota_venta", ondelete="CASCADE"), nullable=False, index=True)
    tipo_item = Column("tipo_item", String(20), nullable=False, default="REPUESTO")  # REPUESTO | MANO_OBRA
    id_producto = Column("id_producto", Integer, ForeignKey("productos.id_producto", ondelete="SET NULL"), nullable=True)
    descripcion = Column("descripcion", String(255), nullable=False)
    cantidad = Column("cantidad", Float, nullable=False, default=1.0)
    precio_unitario = Column("precio_unitario", Float, nullable=False, default=0.0)
    subtotal = Column("subtotal", Float, nullable=False, default=0.0)
    costo_unitario = Column("costo_unitario", Float, nullable=False, default=0.0)

    nota_venta = relationship("NotaDeVenta", back_populates="items")
    producto = relationship("Producto", lazy="joined")

    def to_dict(self) -> dict:
        return {
            "id_item": self.id_item,
            "id_nota_venta": self.id_nota_venta,
            "tipo_item": self.tipo_item,
            "id_producto": self.id_producto,
            "producto_nombre": self.producto.nombre if self.producto else None,
            "descripcion": self.descripcion,
            "cantidad": round(float(self.cantidad or 0.0), 2),
            "precio_unitario": round(float(self.precio_unitario or 0.0), 2),
            "subtotal": round(float(self.subtotal or 0.0), 2),
            "costo_unitario": round(float(self.costo_unitario or 0.0), 2),
        }


