import uuid
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.modules.roles.models import UsuarioRol  # noqa: F401


class Usuario(Base):
    __tablename__ = "usuarios"

    id_usuario = Column("id_usuario", Integer, primary_key=True, index=True, autoincrement=True)
    nombre_completo = Column("nombre_completo", String(150), nullable=False)
    nombre_usuario = Column("nombre_usuario", String(100), nullable=False, unique=True, index=True)
    correo = Column("correo", String(150), nullable=False, unique=True, index=True)
    contrasena = Column("contrasena", String(255), nullable=False)
    pais = Column("pais", String(100), nullable=True)
    ciudad = Column("ciudad", String(100), nullable=True)
    descripcion = Column("descripcion", String(500), nullable=True)
    ruta_imagen = Column("ruta_imagen", String(500), nullable=True)
    telefono = Column("telefono", String(20), nullable=True)
    cedula = Column("cedula", String(20), nullable=True)
    direccion = Column("direccion", String(255), nullable=True)
    puntos_bonus = Column("puntos_bonus", Integer, nullable=False, default=0)
    codigo_referido = Column("codigo_referido", String(20), nullable=True, unique=True)
    referido_usado = Column("referido_usado", Boolean, nullable=False, default=False)

    roles = relationship(
        "UsuarioRol",
        back_populates="usuario",
        cascade="all, delete-orphan",
        lazy="joined",
    )

    def ensure_defaults(self) -> None:
        if self.puntos_bonus is None:
            self.puntos_bonus = 0
        if self.referido_usado is None:
            self.referido_usado = False
        if not self.codigo_referido or not self.codigo_referido.strip():
            self.codigo_referido = "GM-" + uuid.uuid4().hex[:6].upper()

    def to_dict(self, include_roles: bool = True) -> dict:
        data = {
            "id_usuario": self.id_usuario,
            "nombre_completo": self.nombre_completo,
            "nombre_usuario": self.nombre_usuario,
            "correo": self.correo,
            "pais": self.pais,
            "ciudad": self.ciudad,
            "descripcion": self.descripcion,
            "ruta_imagen": self.ruta_imagen,
            "telefono": self.telefono,
            "cedula": self.cedula,
            "direccion": self.direccion,
            "puntosBonus": self.puntos_bonus if self.puntos_bonus is not None else 0,
            "puntos_bonus": self.puntos_bonus if self.puntos_bonus is not None else 0,
            "codigoReferido": self.codigo_referido,
            "codigo_referido": self.codigo_referido,
            "referidoUsado": bool(self.referido_usado),
            "referido_usado": bool(self.referido_usado),
        }
        if include_roles:
            data["roles"] = [r.to_dict(include_usuario=False) for r in (self.roles or [])]
        return data


class RecuperacionContrasena(Base):
    __tablename__ = "recuperacion_contrasena"

    id = Column("id", Integer, primary_key=True, index=True, autoincrement=True)
    token = Column("token", String(255), nullable=False, unique=True, index=True)
    id_usuario = Column("id_usuario", Integer, ForeignKey("usuarios.id_usuario", ondelete="CASCADE"), nullable=False)
    fecha_creacion = Column("fecha_creacion", DateTime, nullable=False, default=datetime.now)
    fecha_expiracion = Column("fecha_expiracion", DateTime, nullable=False)
    usado = Column("usado", Boolean, nullable=False, default=False)

    usuario = relationship("Usuario", lazy="joined")

