from datetime import date, datetime
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.core.database import Base


class Tipo(Base):
    __tablename__ = "tipo"

    id_tipo = Column("id_tipo", Integer, primary_key=True, index=True, autoincrement=True)
    nombre = Column("nombre", String(100), nullable=False)
    descripcion = Column("descripcion", String(500), nullable=True)
    id_producto = Column("id_producto", Integer, ForeignKey("productos.id_producto", ondelete="SET NULL"), nullable=True)
    concepto_manual = Column("concepto_manual", String(255), nullable=True)
    concepto_cantidad = Column("concepto_cantidad", Integer, nullable=True, default=1)
    concepto_precio_unitario = Column("concepto_precio_unitario", Float, nullable=True, default=0.0)

    producto = relationship("Producto", lazy="joined")

    def to_dict(self) -> dict:
        prod_dict = self.producto.to_dict() if self.producto else None
        return {
            "id_tipo": self.id_tipo,
            "nombre": self.nombre,
            "descripcion": self.descripcion,
            "id_producto": self.id_producto,
            "producto": prod_dict,
            "productoPvp": prod_dict["pvp"] if prod_dict else None,
            "concepto_manual": self.concepto_manual,
            "concepto_cantidad": self.concepto_cantidad if self.concepto_cantidad is not None else 1,
            "concepto_precio_unitario": (
                round(float(self.concepto_precio_unitario), 2)
                if self.concepto_precio_unitario is not None
                else 0.0
            ),
        }


class Registro(Base):
    __tablename__ = "registros"

    id_registro = Column("id_registro", Integer, primary_key=True, index=True, autoincrement=True)
    fecha = Column("fecha", Date, nullable=False, default=date.today)
    fecha_entrega_estimada = Column("fecha_entrega_estimada", DateTime, nullable=True)
    fecha_completado = Column("fecha_completado", DateTime, nullable=True)
    fecha_entregado = Column("fecha_entregado", DateTime, nullable=True)
    fecha_facturado = Column("fecha_facturado", DateTime, nullable=True)
    descripcion = Column("descripcion", String(1000), nullable=True)
    observaciones = Column("observaciones", String(1000), nullable=True)
    costo_total = Column("costo_total", Float, nullable=False, default=0.0)
    id_moto = Column("id_moto", Integer, ForeignKey("motos.id_moto", ondelete="CASCADE"), nullable=False, index=True)
    id_encargado = Column("id_encargado", Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True, index=True)
    id_tipo = Column("id_tipo", Integer, ForeignKey("tipo.id_tipo", ondelete="SET NULL"), nullable=True)
    id_factura = Column("id_factura", Integer, ForeignKey("facturas.id_factura", ondelete="SET NULL"), nullable=True, index=True)
    kilometraje = Column("kilometraje", Integer, nullable=True)
    estado = Column("estado", Integer, nullable=False, default=1)

    moto = relationship("Moto", lazy="joined")
    encargado = relationship("Usuario", foreign_keys=[id_encargado], lazy="joined")
    tipo = relationship("Tipo", lazy="joined")
    factura = relationship("Factura", lazy="joined")

    def to_raw_dict(self) -> dict:
        return {
            "id_registro": self.id_registro,
            "fecha": self.fecha.isoformat() if self.fecha else date.today().isoformat(),
            "fecha_entrega_estimada": self.fecha_entrega_estimada.isoformat() if self.fecha_entrega_estimada else None,
            "fecha_completado": self.fecha_completado.isoformat() if self.fecha_completado else None,
            "fecha_entregado": self.fecha_entregado.isoformat() if self.fecha_entregado else None,
            "fecha_facturado": self.fecha_facturado.isoformat() if self.fecha_facturado else None,
            "descripcion": self.descripcion,
            "observaciones": self.observaciones,
            "costo_total": round(float(self.costo_total or 0.0), 2),
            "id_moto": self.id_moto,
            "id_encargado": self.id_encargado,
            "id_tipo": self.id_tipo,
            "id_factura": self.id_factura,
            "kilometraje": self.kilometraje if self.kilometraje is not None else (self.moto.kilometraje if self.moto else 0),
            "estado": self.estado if self.estado is not None else 1,
        }


class DiagnosticoMoto(Base):
    __tablename__ = "diagnostico_moto"

    id_diagnostico = Column("id_diagnostico", Integer, primary_key=True, index=True, autoincrement=True)
    id_moto = Column("id_moto", Integer, ForeignKey("motos.id_moto", ondelete="CASCADE"), nullable=False, index=True)
    id_mecanico = Column("id_mecanico", Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=False, index=True)
    fecha = Column("fecha", DateTime, nullable=False, default=datetime.now)
    kilometraje_ingreso = Column("kilometraje_ingreso", Integer, nullable=True)
    observaciones_generales = Column("observaciones_generales", String(1000), nullable=True)

    detalles = relationship(
        "DetalleDiagnostico",
        back_populates="diagnostico",
        cascade="all, delete-orphan",
        lazy="joined",
    )

    def to_dict(self) -> dict:
        return {
            "id_diagnostico": self.id_diagnostico,
            "id_moto": self.id_moto,
            "id_mecanico": self.id_mecanico,
            "fecha": self.fecha.isoformat() if self.fecha else datetime.now().isoformat(),
            "kilometraje_ingreso": self.kilometraje_ingreso,
            "observaciones_generales": self.observaciones_generales,
            "detalles": [d.to_dict() for d in (self.detalles or [])],
        }


class DetalleDiagnostico(Base):
    __tablename__ = "detalle_diagnostico"

    id_detalle = Column("id_detalle", Integer, primary_key=True, index=True, autoincrement=True)
    id_diagnostico = Column("id_diagnostico", Integer, ForeignKey("diagnostico_moto.id_diagnostico", ondelete="CASCADE"), nullable=False)
    parte = Column("parte", String(100), nullable=False)
    estado = Column("estado", String(50), nullable=False)
    observacion = Column("observacion", String(500), nullable=True)

    diagnostico = relationship("DiagnosticoMoto", back_populates="detalles")

    def to_dict(self) -> dict:
        return {
            "id_detalle": self.id_detalle,
            "parte": self.parte,
            "estado": self.estado,
            "observacion": self.observacion,
        }

