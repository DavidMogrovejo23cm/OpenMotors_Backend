from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Date, DateTime
from app.core.database import Base

class Herramienta(Base):
    __tablename__ = "herramientas"
    id_herramienta = Column(Integer, primary_key=True)
    codigo = Column(String(60), nullable=False, unique=True)
    nombre = Column(String(150), nullable=False)
    marca = Column(String(100), nullable=True)
    numero_serie = Column(String(100), nullable=True)
    estado = Column(String(30), nullable=False, default="DISPONIBLE")
    ubicacion = Column(String(150), nullable=True)
    fecha_adquisicion = Column(Date, nullable=True)
    observaciones = Column(String(1500), nullable=True)
    actualizado = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    def to_dict(self):
        return {c.name: (getattr(self, c.name).isoformat() if isinstance(getattr(self, c.name), (datetime, date)) else getattr(self, c.name)) for c in self.__table__.columns}
