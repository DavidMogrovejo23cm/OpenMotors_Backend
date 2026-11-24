from datetime import date
from typing import Literal
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.database import get_db
from app.core.exceptions import ConflictError, EntityNotFoundError
from app.modules.herramientas.models import Herramienta

class HerramientaInput(BaseModel):
    codigo: str = Field(min_length=1, max_length=60)
    nombre: str = Field(min_length=1, max_length=150)
    marca: str | None = Field(default=None, max_length=100)
    numero_serie: str | None = Field(default=None, max_length=100)
    estado: Literal["DISPONIBLE", "MANTENIMIENTO", "FUERA_SERVICIO"] = "DISPONIBLE"
    ubicacion: str | None = Field(default=None, max_length=150)
    fecha_adquisicion: date | None = None
    observaciones: str | None = Field(default=None, max_length=1500)

herramientas_router = APIRouter(prefix="/api/herramientas", tags=["Herramientas"])

@herramientas_router.get("")
def listar_herramientas(db: Session = Depends(get_db)):
    return [h.to_dict() for h in db.query(Herramienta).order_by(Herramienta.nombre).all()]

@herramientas_router.get("/{id_herramienta}")
def obtener_herramienta(id_herramienta: int, db: Session = Depends(get_db)):
    h = db.get(Herramienta, id_herramienta)
    if not h: raise EntityNotFoundError("Herramienta", id_herramienta)
    return h.to_dict()

def guardar(db, payload, herramienta=None):
    from app.core.exceptions import BusinessValidationError
    data = payload.model_dump()
    data["codigo"] = data["codigo"].strip().upper()
    data["nombre"] = data["nombre"].strip()
    if not data["codigo"] or not data["nombre"]: raise BusinessValidationError("Código y nombre son obligatorios")
    query = db.query(Herramienta).filter(func.upper(Herramienta.codigo) == data["codigo"])
    if herramienta: query = query.filter(Herramienta.id_herramienta != herramienta.id_herramienta)
    if query.first(): raise ConflictError("El código de herramienta ya está registrado")
    h = herramienta or Herramienta()
    for key, value in data.items(): setattr(h, key, value)
    db.add(h); db.commit(); db.refresh(h)
    return h.to_dict()

@herramientas_router.post("", status_code=201)
def crear_herramienta(payload: HerramientaInput, db: Session = Depends(get_db)):
    return guardar(db, payload)

@herramientas_router.put("/{id_herramienta}")
def actualizar_herramienta(id_herramienta: int, payload: HerramientaInput, db: Session = Depends(get_db)):
    h = db.get(Herramienta, id_herramienta)
    if not h: raise EntityNotFoundError("Herramienta", id_herramienta)
    return guardar(db, payload, h)
