from datetime import date
from sqlalchemy import Column, Integer, String, Float, Date

from app.core.database import Base


class CargaCombustible(Base):
    __tablename__ = "carga_combustible"

    id = Column("id", Integer, primary_key=True, index=True, autoincrement=True)
    id_moto = Column("id_moto", Integer, nullable=False, index=True)
    placa = Column("placa", String(20), nullable=True)
    fecha = Column("fecha", Date, nullable=False, default=date.today)
    litros = Column("litros", Float, nullable=False, default=0.0)
    costo_total = Column("costo_total", Float, nullable=False, default=0.0)
    km_actual = Column("km_actual", Integer, nullable=False, default=0)
    km_anterior = Column("km_anterior", Integer, nullable=True, default=0)
    notas = Column("notas", String(255), nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "id_moto": self.id_moto,
            "idMoto": self.id_moto,
            "placa": self.placa or "",
            "fecha": self.fecha.isoformat() if self.fecha else date.today().isoformat(),
            "litros": round(float(self.litros or 0.0), 3),
            "costo_total": round(float(self.costo_total or 0.0), 2),
            "costoTotal": round(float(self.costo_total or 0.0), 2),
            "km_actual": int(self.km_actual or 0),
            "kmActual": int(self.km_actual or 0),
            "km_anterior": int(self.km_anterior or 0),
            "kmAnterior": int(self.km_anterior or 0),
            "notas": self.notas,
        }


class AppConfig(Base):
    __tablename__ = "app_config"

    clave = Column("clave", String(100), primary_key=True, index=True)
    valor = Column("valor", String(255), nullable=False)

