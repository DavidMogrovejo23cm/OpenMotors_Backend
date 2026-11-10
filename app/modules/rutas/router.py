from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, AliasChoices
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import EntityNotFoundError
from app.modules.rutas.models import Ruta


class RutaCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id_usuario: int = Field(..., validation_alias=AliasChoices("id_usuario", "idUsuario"))
    nombre_ruta: str = Field(..., validation_alias=AliasChoices("nombre_ruta", "nombreRuta"))
    descripcion: Optional[str] = None
    origen_lat: float = Field(default=0.0, validation_alias=AliasChoices("origen_lat", "origenLat"))
    origen_lng: float = Field(default=0.0, validation_alias=AliasChoices("origen_lng", "origenLng"))
    destino_lat: float = Field(default=0.0, validation_alias=AliasChoices("destino_lat", "destinoLat"))
    destino_lng: float = Field(default=0.0, validation_alias=AliasChoices("destino_lng", "destinoLng"))
    distancia_km: float = Field(default=0.0, validation_alias=AliasChoices("distancia_km", "distanciaKm"))
    duracion_minutos: int = Field(default=0, validation_alias=AliasChoices("duracion_minutos", "duracionMinutos"))


class RutaUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id_usuario: Optional[int] = Field(default=None, validation_alias=AliasChoices("id_usuario", "idUsuario"))
    nombre_ruta: Optional[str] = Field(default=None, validation_alias=AliasChoices("nombre_ruta", "nombreRuta"))
    descripcion: Optional[str] = None
    origen_lat: Optional[float] = Field(default=None, validation_alias=AliasChoices("origen_lat", "origenLat"))
    origen_lng: Optional[float] = Field(default=None, validation_alias=AliasChoices("origen_lng", "origenLng"))
    destino_lat: Optional[float] = Field(default=None, validation_alias=AliasChoices("destino_lat", "destinoLat"))
    destino_lng: Optional[float] = Field(default=None, validation_alias=AliasChoices("destino_lng", "destinoLng"))
    distancia_km: Optional[float] = Field(default=None, validation_alias=AliasChoices("distancia_km", "distanciaKm"))
    duracion_minutos: Optional[int] = Field(default=None, validation_alias=AliasChoices("duracion_minutos", "duracionMinutos"))


rutas_router = APIRouter(prefix="/api/rutas", tags=["Rutas GPS"])


@rutas_router.get("")
@rutas_router.get("/", include_in_schema=False)
def listar_todas_rutas(db: Session = Depends(get_db)):
    rutas = db.query(Ruta).order_by(Ruta.id_ruta.desc()).all()
    return [r.to_dict() for r in rutas]


@rutas_router.post("", status_code=status.HTTP_201_CREATED)
@rutas_router.post("/", status_code=status.HTTP_201_CREATED, include_in_schema=False)
def crear_ruta(payload: RutaCreate, db: Session = Depends(get_db)):
    nueva = Ruta(
        id_usuario=payload.id_usuario,
        nombre_ruta=payload.nombre_ruta.strip(),
        descripcion=payload.descripcion,
        origen_lat=payload.origen_lat,
        origen_lng=payload.origen_lng,
        destino_lat=payload.destino_lat,
        destino_lng=payload.destino_lng,
        distancia_km=payload.distancia_km,
        duracion_minutos=payload.duracion_minutos,
    )
    db.add(nueva)
    db.commit()
    db.refresh(nueva)
    return nueva.to_dict()


@rutas_router.get("/usuario/{id_usuario}")
def listar_rutas_por_usuario(id_usuario: int, db: Session = Depends(get_db)):
    rutas = db.query(Ruta).filter(Ruta.id_usuario == id_usuario).order_by(Ruta.id_ruta.desc()).all()
    return [r.to_dict() for r in rutas]


@rutas_router.get("/{id_ruta}")
def obtener_ruta(id_ruta: int, db: Session = Depends(get_db)):
    r = db.query(Ruta).filter(Ruta.id_ruta == id_ruta).first()
    if not r:
        return Response(status_code=status.HTTP_404_NOT_FOUND)
    return r.to_dict()


@rutas_router.put("/{id_ruta}")
def actualizar_ruta(id_ruta: int, payload: RutaUpdate, db: Session = Depends(get_db)):
    r = db.query(Ruta).filter(Ruta.id_ruta == id_ruta).first()
    if not r:
        raise EntityNotFoundError("Ruta", id_ruta)
    if payload.nombre_ruta is not None:
        r.nombre_ruta = payload.nombre_ruta.strip()
    if payload.descripcion is not None:
        r.descripcion = payload.descripcion
    if payload.origen_lat is not None:
        r.origen_lat = payload.origen_lat
    if payload.origen_lng is not None:
        r.origen_lng = payload.origen_lng
    if payload.destino_lat is not None:
        r.destino_lat = payload.destino_lat
    if payload.destino_lng is not None:
        r.destino_lng = payload.destino_lng
    if payload.distancia_km is not None:
        r.distancia_km = payload.distancia_km
    if payload.duracion_minutos is not None:
        r.duracion_minutos = payload.duracion_minutos

    db.commit()
    db.refresh(r)
    return r.to_dict()


@rutas_router.delete("/{id_ruta}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_ruta(id_ruta: int, db: Session = Depends(get_db)):
    r = db.query(Ruta).filter(Ruta.id_ruta == id_ruta).first()
    if r:
        db.delete(r)
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

