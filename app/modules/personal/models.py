from datetime import date, datetime
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from app.core.database import Base


class PerfilLaboral(Base):
    """Ficha laboral formal del personal del taller (RF-40 / HU-50)."""
    __tablename__ = "perfiles_laborales"

    id_perfil = Column("id_perfil", Integer, primary_key=True, index=True, autoincrement=True)
    id_usuario = Column(
        "id_usuario",
        Integer,
        ForeignKey("usuarios.id_usuario", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    cargo = Column("cargo", String(100), nullable=False, default="Mecánico")
    especialidad = Column("especialidad", String(150), nullable=True)
    fecha_ingreso = Column("fecha_ingreso", Date, nullable=True)
    tipo_contrato = Column("tipo_contrato", String(60), nullable=True, default="TIEMPO_COMPLETO")
    modalidad_pago = Column("modalidad_pago", String(40), nullable=False, default="POR_TRABAJO")
    tarifa_hora = Column("tarifa_hora", Float, nullable=False, default=0.0)
    salario_base = Column("salario_base", Float, nullable=False, default=0.0)
    contacto_emergencia = Column("contacto_emergencia", String(150), nullable=True)
    observaciones = Column("observaciones", String(500), nullable=True)
    actualizado_en = Column("actualizado_en", DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    usuario = relationship("Usuario", lazy="joined")

    def to_dict(self) -> dict:
        return {
            "id_perfil": self.id_perfil,
            "id_usuario": self.id_usuario,
            "cargo": self.cargo,
            "especialidad": self.especialidad,
            "fecha_ingreso": self.fecha_ingreso.isoformat() if self.fecha_ingreso else None,
            "tipo_contrato": self.tipo_contrato,
            "modalidad_pago": self.modalidad_pago,
            "tarifa_hora": round(float(self.tarifa_hora or 0.0), 2),
            "salario_base": round(float(self.salario_base or 0.0), 2),
            "contacto_emergencia": self.contacto_emergencia,
            "observaciones": self.observaciones,
            "actualizado_en": self.actualizado_en.isoformat() if self.actualizado_en else None,
        }


class HorarioTrabajo(Base):
    """Horarios semanales por mecánico (RF-41 / HU-51)."""
    __tablename__ = "horarios_trabajo"
    __table_args__ = (UniqueConstraint("id_usuario", "dia_semana", name="uq_horario_usuario_dia"),)

    id_horario = Column("id_horario", Integer, primary_key=True, index=True, autoincrement=True)
    id_usuario = Column(
        "id_usuario",
        Integer,
        ForeignKey("usuarios.id_usuario", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    dia_semana = Column("dia_semana", Integer, nullable=False)  # 0=Lunes .. 6=Domingo
    es_laborable = Column("es_laborable", Boolean, nullable=False, default=True)
    hora_entrada = Column("hora_entrada", String(5), nullable=False, default="08:00")
    hora_salida = Column("hora_salida", String(5), nullable=False, default="17:00")
    minutos_descanso = Column("minutos_descanso", Integer, nullable=False, default=60)
    turno = Column("turno", String(40), nullable=False, default="DIURNO")

    usuario = relationship("Usuario", lazy="joined")

    def to_dict(self) -> dict:
        return {
            "id_horario": self.id_horario,
            "id_usuario": self.id_usuario,
            "nombre_empleado": self.usuario.nombre_completo if self.usuario else None,
            "dia_semana": self.dia_semana,
            "es_laborable": bool(self.es_laborable),
            "hora_entrada": self.hora_entrada,
            "hora_salida": self.hora_salida,
            "minutos_descanso": int(self.minutos_descanso or 0),
            "turno": self.turno,
        }


class AsistenciaPersonal(Base):
    """Control de asistencia diaria y horas trabajadas (RF-42 / HU-52)."""
    __tablename__ = "asistencia_personal"
    __table_args__ = (UniqueConstraint("id_usuario", "fecha", "turno", name="uq_asistencia_usuario_fecha_turno"),)

    id_asistencia = Column("id_asistencia", Integer, primary_key=True, index=True, autoincrement=True)
    id_usuario = Column(
        "id_usuario",
        Integer,
        ForeignKey("usuarios.id_usuario", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    fecha = Column("fecha", Date, nullable=False, default=date.today, index=True)
    turno = Column("turno", String(40), nullable=False, default="UNICO")
    estado = Column("estado", String(30), nullable=False, default="PRESENTE")
    hora_entrada = Column("hora_entrada", String(5), nullable=True)
    hora_salida = Column("hora_salida", String(5), nullable=True)
    minutos_descanso = Column("minutos_descanso", Integer, nullable=False, default=0)
    horas_trabajadas = Column("horas_trabajadas", Float, nullable=False, default=0.0)
    observaciones = Column("observaciones", String(500), nullable=True)
    registrado_por = Column(
        "registrado_por",
        Integer,
        ForeignKey("usuarios.id_usuario", ondelete="SET NULL"),
        nullable=True,
    )
    actualizado_en = Column("actualizado_en", DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    usuario = relationship("Usuario", foreign_keys=[id_usuario], lazy="joined")

    def to_dict(self) -> dict:
        return {
            "id_asistencia": self.id_asistencia,
            "id_usuario": self.id_usuario,
            "nombre_empleado": self.usuario.nombre_completo if self.usuario else None,
            "fecha": self.fecha.isoformat() if self.fecha else date.today().isoformat(),
            "turno": self.turno,
            "estado": self.estado,
            "hora_entrada": self.hora_entrada,
            "hora_salida": self.hora_salida,
            "minutos_descanso": int(self.minutos_descanso or 0),
            "horas_trabajadas": round(float(self.horas_trabajadas or 0.0), 2),
            "observaciones": self.observaciones,
            "registrado_por": self.registrado_por,
            "actualizado_en": self.actualizado_en.isoformat() if self.actualizado_en else None,
        }
