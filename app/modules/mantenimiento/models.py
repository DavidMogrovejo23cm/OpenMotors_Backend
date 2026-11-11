from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship

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
    id_vehiculo = Column("id_vehiculo", Integer, nullable=False, index=True)
    tipo = Column("tipo", String(100), nullable=False)
    km_servicio = Column("km_servicio", Integer, nullable=False, default=0)
    fecha = Column("fecha", DateTime, nullable=False, default=datetime.now)

    def to_dict(self) -> dict:
        return {
            "idMantenimiento": self.id_mantenimiento,
            "id_mantenimiento": self.id_mantenimiento,
            "idVehiculo": self.id_vehiculo,
            "id_vehiculo": self.id_vehiculo,
            "tipo": self.tipo,
            "kmServicio": self.km_servicio,
            "km_servicio": self.km_servicio,
            "fecha": self.fecha.isoformat() if self.fecha else None,
        }


class AlertaEnviada(Base):
    __tablename__ = "alerta_enviada"

    id_alerta = Column("id_alerta", Integer, primary_key=True, index=True, autoincrement=True)
    id_vehiculo = Column("id_vehiculo", Integer, nullable=False, index=True)
    tipo_mantenimiento = Column("tipo_mantenimiento", String(100), nullable=False)
    km_enviado = Column("km_enviado", Integer, nullable=False)
    fecha_envio = Column("fecha_envio", DateTime, nullable=False, default=datetime.now)


class CitaMantenimiento(Base):
    """
    Cita de mantenimiento preventivo agendada a partir de los avisos de desgaste (Proceso 16).
    """
    __tablename__ = "citas_mantenimiento"

    id_cita = Column("id_cita", Integer, primary_key=True, index=True, autoincrement=True)
    id_vehiculo = Column("id_vehiculo", Integer, ForeignKey("vehiculos.id_vehiculo", ondelete="CASCADE"), nullable=False, index=True)
    id_usuario = Column("id_usuario", Integer, ForeignKey("usuarios.id_usuario", ondelete="CASCADE"), nullable=False, index=True)
    fecha_agendada = Column("fecha_agendada", DateTime, nullable=False)
    piezas_a_revisar = Column("piezas_a_revisar", String(500), nullable=True)
    estado = Column("estado", String(30), nullable=False, default="AGENDADA")  # AGENDADA, ATENDIDA, CANCELADA
    observaciones = Column("observaciones", String(500), nullable=True)
    fecha_registro = Column("fecha_registro", DateTime, nullable=False, default=datetime.now)

    vehiculo = relationship("Vehiculo", lazy="joined")
    usuario = relationship("Usuario", lazy="joined")

    def to_dict(self) -> dict:
        return {
            "id_cita": self.id_cita,
            "id_vehiculo": self.id_vehiculo,
            "placa": self.vehiculo.placa if self.vehiculo else None,
            "vehiculo": f"{self.vehiculo.marca} {self.vehiculo.modelo}" if self.vehiculo else None,
            "id_usuario": self.id_usuario,
            "cliente_nombre": self.usuario.nombre_completo if self.usuario else None,
            "cliente_telefono": self.usuario.telefono if self.usuario else None,
            "fecha_agendada": self.fecha_agendada.isoformat() if self.fecha_agendada else None,
            "piezas_a_revisar": self.piezas_a_revisar,
            "estado": self.estado,
            "observaciones": self.observaciones,
            "fecha_registro": self.fecha_registro.isoformat() if self.fecha_registro else datetime.now().isoformat(),
        }


