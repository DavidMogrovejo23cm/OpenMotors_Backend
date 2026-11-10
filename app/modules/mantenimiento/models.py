from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime

from app.core.database import Base


class ParametroMantenimiento(Base):
    __tablename__ = "parametro_mantenimiento"

    id_parametro = Column("id_parametro", Integer, primary_key=True, index=True, autoincrement=True)
    cc_min = Column("cc_min", Integer, nullable=False)
    cc_max = Column("cc_max", Integer, nullable=False)
    tipo_mantenimiento = Column("tipo_mantenimiento", String(100), nullable=False)
    intervalo_km = Column("intervalo_km", Integer, nullable=False)
    descripcion = Column("descripcion", String(255), nullable=True)

    def to_dict(self) -> dict:
        return {
            "idParametro": self.id_parametro,
            "id_parametro": self.id_parametro,
            "ccMin": self.cc_min,
            "cc_min": self.cc_min,
            "ccMax": self.cc_max,
            "cc_max": self.cc_max,
            "tipoMantenimiento": self.tipo_mantenimiento,
            "tipo_mantenimiento": self.tipo_mantenimiento,
            "intervaloKm": self.intervalo_km,
            "intervalo_km": self.intervalo_km,
            "descripcion": self.descripcion,
        }


class MantenimientoRealizado(Base):
    __tablename__ = "mantenimiento_realizado"

    id_mantenimiento = Column("id_mantenimiento", Integer, primary_key=True, index=True, autoincrement=True)
    id_moto = Column("id_moto", Integer, nullable=False, index=True)
    tipo = Column("tipo", String(100), nullable=False)
    km_servicio = Column("km_servicio", Integer, nullable=False, default=0)
    fecha = Column("fecha", DateTime, nullable=False, default=datetime.now)

    def to_dict(self) -> dict:
        return {
            "idMantenimiento": self.id_mantenimiento,
            "id_mantenimiento": self.id_mantenimiento,
            "idMoto": self.id_moto,
            "id_moto": self.id_moto,
            "tipo": self.tipo,
            "kmServicio": self.km_servicio,
            "km_servicio": self.km_servicio,
            "fecha": self.fecha.isoformat() if self.fecha else None,
        }


class AlertaEnviada(Base):
    __tablename__ = "alerta_enviada"

    id_alerta = Column("id_alerta", Integer, primary_key=True, index=True, autoincrement=True)
    id_moto = Column("id_moto", Integer, nullable=False, index=True)
    tipo_mantenimiento = Column("tipo_mantenimiento", String(100), nullable=False)
    km_enviado = Column("km_enviado", Integer, nullable=False)
    fecha_envio = Column("fecha_envio", DateTime, nullable=False, default=datetime.now)

