from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.modules.usuarios.models import Usuario  # noqa: F401


class Vehiculo(Base):
    __tablename__ = "vehiculos"

    id_vehiculo = Column("id_vehiculo", Integer, primary_key=True, index=True, autoincrement=True)
    placa = Column("placa", String(20), nullable=False, unique=True, index=True)
    anio = Column("anio", Integer, nullable=False, default=2024)
    marca = Column("marca", String(100), nullable=False)
    modelo = Column("modelo", String(100), nullable=False)
    nombre_vehiculo = Column("nombre_vehiculo", String(150), nullable=True)
    tipo_vehiculo = Column("tipo_vehiculo", String(100), nullable=True)
    kilometraje = Column("kilometraje", Integer, nullable=True, default=0)
    cilindraje = Column("cilindraje", Integer, nullable=True, default=1600)
    id_usuario = Column("id_usuario", Integer, ForeignKey("usuarios.id_usuario", ondelete="CASCADE"), nullable=False, index=True)
    ruta_imagen_vehiculo = Column("ruta_imagen_vehiculo", String(500), nullable=True)

    usuario = relationship("Usuario", lazy="joined")

    def to_dict(self) -> dict:
        data = {
            "id_vehiculo": self.id_vehiculo,
            "placa": self.placa,
            "anio": self.anio,
            "marca": self.marca,
            "modelo": self.modelo,
            "nombre_vehiculo": self.nombre_vehiculo,
            "tipo_vehiculo": self.tipo_vehiculo,
            "kilometraje": self.kilometraje if self.kilometraje is not None else 0,
            "cilindraje": self.cilindraje if self.cilindraje is not None else 150,
            "id_usuario": self.id_usuario,
            "ruta_imagen_vehiculo": self.ruta_imagen_vehiculo,
        }
        if self.usuario:
            data["usuario"] = {
                "id_usuario": self.usuario.id_usuario,
                "nombre_completo": self.usuario.nombre_completo,
                "nombre_usuario": self.usuario.nombre_usuario,
                "correo": self.usuario.correo,
                "telefono": self.usuario.telefono,
                "cedula": self.usuario.cedula,
                "direccion": self.usuario.direccion,
                "ciudad": self.usuario.ciudad,
            }
        else:
            data["usuario"] = None
        return data

