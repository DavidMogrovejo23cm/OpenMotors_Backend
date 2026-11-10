from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

from app.core.database import Base


class Moto(Base):
    __tablename__ = "motos"

    id_moto = Column("id_moto", Integer, primary_key=True, index=True, autoincrement=True)
    placa = Column("placa", String(20), nullable=False, unique=True, index=True)
    anio = Column("anio", Integer, nullable=False, default=2024)
    marca = Column("marca", String(100), nullable=False)
    modelo = Column("modelo", String(100), nullable=False)
    nombre_moto = Column("nombre_moto", String(150), nullable=True)
    tipo_moto = Column("tipo_moto", String(100), nullable=True)
    kilometraje = Column("kilometraje", Integer, nullable=True, default=0)
    cilindraje = Column("cilindraje", Integer, nullable=True, default=150)
    id_usuario = Column("id_usuario", Integer, ForeignKey("usuarios.id_usuario", ondelete="CASCADE"), nullable=False, index=True)
    ruta_imagen_motos = Column("ruta_imagen_motos", String(500), nullable=True)

    usuario = relationship("Usuario", lazy="joined")

    def to_dict(self) -> dict:
        data = {
            "id_moto": self.id_moto,
            "placa": self.placa,
            "anio": self.anio,
            "marca": self.marca,
            "modelo": self.modelo,
            "nombre_moto": self.nombre_moto,
            "tipo_moto": self.tipo_moto,
            "kilometraje": self.kilometraje if self.kilometraje is not None else 0,
            "cilindraje": self.cilindraje if self.cilindraje is not None else 150,
            "id_usuario": self.id_usuario,
            "ruta_imagen_motos": self.ruta_imagen_motos,
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

