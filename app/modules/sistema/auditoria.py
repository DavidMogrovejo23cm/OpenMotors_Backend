"""Auditoría centralizada de operaciones críticas (RNF-22)."""
import json
from datetime import datetime
from typing import Any, Optional
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import Session

from app.core.database import Base


class AuditoriaOperacion(Base):
    __tablename__ = "auditoria_operaciones"

    id_auditoria = Column("id_auditoria", Integer, primary_key=True, index=True, autoincrement=True)
    fecha = Column("fecha", DateTime, nullable=False, default=datetime.now, index=True)
    id_usuario = Column(
        "id_usuario",
        Integer,
        ForeignKey("usuarios.id_usuario", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    accion = Column("accion", String(80), nullable=False, index=True)
    entidad = Column("entidad", String(80), nullable=False, index=True)
    id_referencia = Column("id_referencia", Integer, nullable=True)
    detalle = Column("detalle", String(500), nullable=False)
    datos_json = Column("datos_json", String(2000), nullable=True)

    def to_dict(self) -> dict:
        return {
            "id_auditoria": self.id_auditoria,
            "fecha": self.fecha.isoformat() if self.fecha else datetime.now().isoformat(),
            "id_usuario": self.id_usuario,
            "accion": self.accion,
            "entidad": self.entidad,
            "id_referencia": self.id_referencia,
            "detalle": self.detalle,
            "datos": json.loads(self.datos_json) if self.datos_json else None,
        }


def registrar_auditoria(
    db: Session,
    id_usuario: Optional[int],
    accion: str,
    entidad: str,
    id_referencia: Optional[int],
    detalle: str,
    datos: Optional[dict[str, Any]] = None,
) -> AuditoriaOperacion:
    """Agrega un registro auditable dentro de la transacción activa."""
    payload_str = None
    if datos is not None:
        payload_str = json.dumps(datos, ensure_ascii=False, default=str)[:2000]
    registro = AuditoriaOperacion(
        fecha=datetime.now(),
        id_usuario=id_usuario,
        accion=accion.strip().upper()[:80],
        entidad=entidad.strip()[:80],
        id_referencia=id_referencia,
        detalle=detalle.strip()[:500],
        datos_json=payload_str,
    )
    db.add(registro)
    return registro
