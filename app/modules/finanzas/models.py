from datetime import date
from sqlalchemy import Column, Integer, String, Float, Date

from app.core.database import Base


class PagoEmpleado(Base):
    __tablename__ = "pagos_empleado"

    id_pago = Column("id_pago", Integer, primary_key=True, index=True, autoincrement=True)
    id_empleado = Column("id_empleado", Integer, nullable=False, index=True)
    fecha = Column("fecha", Date, nullable=False, default=date.today)
    concepto = Column("concepto", String(255), nullable=False)
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
            "monto": round(float(self.monto or 0.0), 2),
            "notas": self.notas,
        }

