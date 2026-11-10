from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.core.database import Base


class Rol(Base):
    __tablename__ = "roles"

    id_rol = Column("id_rol", Integer, primary_key=True, index=True, autoincrement=True)
    nombre = Column("nombre", String(50), nullable=False, unique=True)


class UsuarioRol(Base):
    __tablename__ = "usuario_rol"

    id_usuario = Column("id_usuario", Integer, ForeignKey("usuarios.id_usuario", ondelete="CASCADE"), primary_key=True)
    id_rol = Column("id_rol", Integer, ForeignKey("roles.id_rol", ondelete="CASCADE"), primary_key=True)
    estado = Column("estado", Integer, nullable=False, default=1)
    fecha_creacion = Column("fecha_creacion", DateTime, default=datetime.now)
    fecha_modificacion = Column("fecha_modificacion", DateTime, nullable=True, onupdate=datetime.now)

    rol = relationship("Rol", lazy="joined")
    usuario = relationship("Usuario", back_populates="roles", lazy="select")

    def to_dict(self, include_usuario: bool = False) -> dict:
        data = {
            "id": {"idUsuario": self.id_usuario, "idRol": self.id_rol},
            "idUsuario": self.id_usuario,
            "id_usuario": self.id_usuario,
            "idRol": self.id_rol,
            "id_rol": self.id_rol,
            "estado": self.estado,
            "fechaCreacion": self.fecha_creacion.isoformat() if self.fecha_creacion else None,
            "fecha_creacion": self.fecha_creacion.isoformat() if self.fecha_creacion else None,
            "fechaModificacion": self.fecha_modificacion.isoformat() if self.fecha_modificacion else None,
            "fecha_modificacion": self.fecha_modificacion.isoformat() if self.fecha_modificacion else None,
            "rol": {
                "id_rol": self.rol.id_rol,
                "idRol": self.rol.id_rol,
                "nombre": self.rol.nombre,
            } if self.rol else None,
        }
        if include_usuario and self.usuario:
            data["usuario"] = {
                "id_usuario": self.usuario.id_usuario,
                "nombre_completo": self.usuario.nombre_completo,
                "nombre_usuario": self.usuario.nombre_usuario,
                "correo": self.usuario.correo,
            }
        return data

