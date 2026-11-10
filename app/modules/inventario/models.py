from datetime import date, datetime
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey

from app.core.database import Base


class Categoria(Base):
    __tablename__ = "categorias"

    id_categoria = Column("id_categoria", Integer, primary_key=True, index=True, autoincrement=True)
    nombre = Column("nombre", String(100), nullable=False)
    descripcion = Column("descripcion", String(255), nullable=True)

    def to_dict(self) -> dict:
        return {
            "id_categoria": self.id_categoria,
            "nombre": self.nombre,
            "descripcion": self.descripcion,
        }


class Producto(Base):
    __tablename__ = "productos"

    id_producto = Column("id_producto", Integer, primary_key=True, index=True, autoincrement=True)
    codigo_proveedor = Column("codigo_proveedor", String(50), nullable=False)
    codigo_distribuidor = Column("codigo_distribuidor", String(50), nullable=False)
    codigo_personal = Column("codigo_personal", String(50), nullable=False, unique=True, index=True)
    nombre = Column("nombre", String(150), nullable=False)
    descripcion = Column("descripcion", String(500), nullable=False)
    costo = Column("costo", Float, nullable=False, default=0.0)
    pvp = Column("pvp", Float, nullable=False, default=0.0)
    stock = Column("stock", Integer, nullable=False, default=0)
    fecha_registro = Column("fecha_registro", Date, nullable=False, default=date.today)
    fecha_modificacion = Column("fecha_modificacion", DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)
    id_categoria = Column("id_categoria", Integer, ForeignKey("categorias.id_categoria"), nullable=False)
    ruta_imagenproductos = Column("ruta_imagenproductos", String(500), nullable=True)

    def to_dict(self) -> dict:
        return {
            "id_producto": self.id_producto,
            "codigo_proveedor": self.codigo_proveedor,
            "codigo_distribuidor": self.codigo_distribuidor,
            "codigo_personal": self.codigo_personal,
            "nombre": self.nombre,
            "descripcion": self.descripcion,
            "costo": round(float(self.costo or 0.0), 2),
            "pvp": round(float(self.pvp or 0.0), 2),
            "stock": int(self.stock or 0),
            "fecha_registro": self.fecha_registro.isoformat() if self.fecha_registro else date.today().isoformat(),
            "fecha_modificacion": self.fecha_modificacion.isoformat() if self.fecha_modificacion else datetime.now().isoformat(),
            "id_categoria": self.id_categoria,
            "ruta_imagenproductos": self.ruta_imagenproductos,
        }


class ContactoProveedor(Base):
    __tablename__ = "contacto_proveedor"

    codigo = Column("codigo", String(100), primary_key=True, index=True)
    nombre = Column("nombre", String(150), nullable=True)
    telefono = Column("telefono", String(30), nullable=True)
    email = Column("email", String(150), nullable=True)
    producto = Column("producto", String(255), nullable=True)

    def to_dict(self) -> dict:
        return {
            "codigo": self.codigo,
            "nombre": self.nombre,
            "telefono": self.telefono,
            "email": self.email,
            "producto": self.producto,
        }

