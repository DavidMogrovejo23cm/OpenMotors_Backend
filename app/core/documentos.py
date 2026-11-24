"""Numeración interna atómica para SQLite y PostgreSQL."""
from datetime import datetime
from sqlalchemy import Column, Integer, String
from app.core.database import Base

class SecuenciaDocumento(Base):
    __tablename__ = "secuencias_documento"
    clave = Column(String(50), primary_key=True)
    valor = Column(Integer, nullable=False)

def siguiente_numero(db, model, field, tipo):
    prefix = f"{tipo}-{datetime.now().year}-"
    column = getattr(model, field)
    previous = [value[len(prefix):] for (value,) in db.query(column).filter(column.like(prefix+'%')).all()]
    initial = max([int(value) for value in previous if value.isdigit()] or [0]) + 1
    if db.bind.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    stmt = insert(SecuenciaDocumento).values(clave=prefix, valor=initial).on_conflict_do_update(index_elements=["clave"], set_={"valor":SecuenciaDocumento.valor+1}).returning(SecuenciaDocumento.valor)
    return prefix + f"{db.execute(stmt).scalar_one():04d}"
