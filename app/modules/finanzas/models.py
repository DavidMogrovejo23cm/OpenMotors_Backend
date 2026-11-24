from datetime import date, datetime
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Boolean, ForeignKey

from app.core.database import Base


class CategoriaMovimiento(Base):
    """Catálogo formal de clasificación financiera (RF-33 / HU-43)."""
    __tablename__ = "categorias_movimiento"

    id_categoria = Column("id_categoria", Integer, primary_key=True, index=True, autoincrement=True)
    nombre = Column("nombre", String(100), nullable=False, unique=True, index=True)
    tipo = Column("tipo", String(20), nullable=False, default="EGRESO")  # INGRESO | EGRESO | AMBOS
    descripcion = Column("descripcion", String(255), nullable=True)
    es_personal = Column("es_personal", Boolean, nullable=False, default=False)
    activa = Column("activa", Boolean, nullable=False, default=True)

    def to_dict(self) -> dict:
        return {
            "id_categoria": self.id_categoria,
            "nombre": self.nombre,
            "tipo": self.tipo,
            "descripcion": self.descripcion,
            "es_personal": bool(self.es_personal),
            "activa": bool(self.activa),
        }


class PagoEmpleado(Base):
    __tablename__ = "pagos_empleado"

    id_pago = Column("id_pago", Integer, primary_key=True, index=True, autoincrement=True)
    id_empleado = Column("id_empleado", Integer, nullable=False, index=True)
    fecha = Column("fecha", Date, nullable=False, default=date.today)
    concepto = Column("concepto", String(255), nullable=False)
    categoria = Column("categoria", String(100), nullable=True)
    monto = Column("monto", Float, nullable=False, default=0.0)
    notas = Column("notas", String(500), nullable=True)

    def to_dict(self) -> dict:
        return {
            "id_pago": self.id_pago,
            "idPago": self.id_pago,
            "id_empleado": self.id_empleado,
            "idEmpleado": self.id_empleado,
            "fecha": self.fecha.isoformat() if self.fecha else date.today().isoformat(),
            "concepto": self.concepto,
            "categoria": self.categoria or self.concepto,
            "monto": round(float(self.monto or 0.0), 2),
            "notas": self.notas,
        }


class MovimientoCaja(Base):
    """Registro auditable de ingresos y retiros de caja física (RF-37 / HU-47)."""
    __tablename__ = "movimientos_caja"

    id_movimiento = Column("id_movimiento", Integer, primary_key=True, index=True, autoincrement=True)
    fecha = Column("fecha", DateTime, nullable=False, default=datetime.now, index=True)
    tipo = Column("tipo", String(20), nullable=False, index=True)  # APERTURA | INGRESO | RETIRO | CIERRE
    monto = Column("monto", Float, nullable=False, default=0.0)
    motivo = Column("motivo", String(255), nullable=False)
    referencia = Column("referencia", String(100), nullable=True)
    id_registro = Column(
        "id_registro",
        Integer,
        ForeignKey("registros.id_registro", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    id_usuario = Column(
        "id_usuario",
        Integer,
        ForeignKey("usuarios.id_usuario", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    saldo_anterior = Column("saldo_anterior", Float, nullable=False, default=0.0)
    saldo_resultante = Column("saldo_resultante", Float, nullable=False, default=0.0)
    observaciones = Column("observaciones", String(500), nullable=True)

    def to_dict(self) -> dict:
        return {
            "id_movimiento": self.id_movimiento,
            "fecha": self.fecha.isoformat() if self.fecha else datetime.now().isoformat(),
            "tipo": self.tipo,
            "monto": round(float(self.monto or 0.0), 2),
            "motivo": self.motivo,
            "referencia": self.referencia,
            "id_registro": self.id_registro,
            "id_usuario": self.id_usuario,
            "saldo_anterior": round(float(self.saldo_anterior or 0.0), 2),
            "saldo_resultante": round(float(self.saldo_resultante or 0.0), 2),
            "observaciones": self.observaciones,
        }


class CierreCaja(Base):
    """Sesiones de apertura y arqueo/cierre de caja (RF-37 / HU-47)."""
    __tablename__ = "cierres_caja"

    id_cierre = Column("id_cierre", Integer, primary_key=True, index=True, autoincrement=True)
    fecha_apertura = Column("fecha_apertura", DateTime, nullable=False, default=datetime.now)
    fecha_cierre = Column("fecha_cierre", DateTime, nullable=True)
    monto_inicial = Column("monto_inicial", Float, nullable=False, default=0.0)
    total_ingresos = Column("total_ingresos", Float, nullable=False, default=0.0)
    total_retiros = Column("total_retiros", Float, nullable=False, default=0.0)
    saldo_esperado = Column("saldo_esperado", Float, nullable=False, default=0.0)
    monto_fisico_contado = Column("monto_fisico_contado", Float, nullable=True)
    diferencia = Column("diferencia", Float, nullable=True)
    estado = Column("estado", String(20), nullable=False, default="ABIERTA", index=True)  # ABIERTA | CERRADA
    id_usuario_apertura = Column(
        "id_usuario_apertura",
        Integer,
        ForeignKey("usuarios.id_usuario", ondelete="SET NULL"),
        nullable=True,
    )
    id_usuario_cierre = Column(
        "id_usuario_cierre",
        Integer,
        ForeignKey("usuarios.id_usuario", ondelete="SET NULL"),
        nullable=True,
    )
    observaciones = Column("observaciones", String(500), nullable=True)

    def to_dict(self) -> dict:
        return {
            "id_cierre": self.id_cierre,
            "fecha_apertura": self.fecha_apertura.isoformat() if self.fecha_apertura else None,
            "fecha_cierre": self.fecha_cierre.isoformat() if self.fecha_cierre else None,
            "monto_inicial": round(float(self.monto_inicial or 0.0), 2),
            "total_ingresos": round(float(self.total_ingresos or 0.0), 2),
            "total_retiros": round(float(self.total_retiros or 0.0), 2),
            "saldo_esperado": round(float(self.saldo_esperado or 0.0), 2),
            "monto_fisico_contado": (
                round(float(self.monto_fisico_contado), 2)
                if self.monto_fisico_contado is not None
                else None
            ),
            "diferencia": round(float(self.diferencia), 2) if self.diferencia is not None else None,
            "estado": self.estado,
            "id_usuario_apertura": self.id_usuario_apertura,
            "id_usuario_cierre": self.id_usuario_cierre,
            "observaciones": self.observaciones,
        }
