from sqlalchemy import Column, Integer, String, Float, ForeignKey

from app.core.database import Base


class Ruta(Base):
    __tablename__ = "rutas"

    id_ruta = Column("id_ruta", Integer, primary_key=True, index=True, autoincrement=True)
    id_usuario = Column("id_usuario", Integer, ForeignKey("usuarios.id_usuario", ondelete="CASCADE"), nullable=False, index=True)
    nombre_ruta = Column("nombre_ruta", String(150), nullable=False)
    descripcion = Column("descripcion", String(500), nullable=True)
    origen_lat = Column("origen_lat", Float, nullable=False, default=0.0)
    origen_lng = Column("origen_lng", Float, nullable=False, default=0.0)
    destino_lat = Column("destino_lat", Float, nullable=False, default=0.0)
    destino_lng = Column("destino_lng", Float, nullable=False, default=0.0)
    distancia_km = Column("distancia_km", Float, nullable=False, default=0.0)
    duracion_minutos = Column("duracion_minutos", Integer, nullable=False, default=0)

    def to_dict(self) -> dict:
        return {
            "id_ruta": self.id_ruta,
            "idRuta": self.id_ruta,
            "id_usuario": self.id_usuario,
            "idUsuario": self.id_usuario,
            "nombre_ruta": self.nombre_ruta,
            "nombreRuta": self.nombre_ruta,
            "descripcion": self.descripcion,
            "origen_lat": self.origen_lat,
            "origenLat": self.origen_lat,
            "origen_lng": self.origen_lng,
            "origenLng": self.origen_lng,
            "destino_lat": self.destino_lat,
            "destinoLat": self.destino_lat,
            "destino_lng": self.destino_lng,
            "destinoLng": self.destino_lng,
            "distancia_km": self.distancia_km,
            "distanciaKm": self.distancia_km,
            "duracion_minutos": self.duracion_minutos,
            "duracionMinutos": self.duracion_minutos,
        }

