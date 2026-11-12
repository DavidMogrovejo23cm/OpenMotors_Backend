from datetime import date
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.combustible.models import CargaCombustible, AppConfig
from app.modules.combustible.schemas import CargaCombustibleCreate, PrecioCombustibleUpdate
from app.modules.vehiculos.models import Vehiculo
from app.modules.mantenimiento.service import AlertaMantenimientoService

combustible_router = APIRouter(prefix="/api/combustible", tags=["Combustible"])


def _obtener_precio(db: Session, clave: str, defecto: float) -> float:
    cfg = db.query(AppConfig).filter(AppConfig.clave == clave).first()
    if not cfg:
        return defecto
    try:
        return float(cfg.valor)
    except ValueError:
        return defecto


def _guardar_precio(db: Session, clave: str, precio: float) -> None:
    cfg = db.query(AppConfig).filter(AppConfig.clave == clave).first()
    if not cfg:
        cfg = AppConfig(clave=clave, valor=str(precio))
        db.add(cfg)
    else:
        cfg.valor = str(precio)
    db.commit()


@combustible_router.get("")
@combustible_router.get("/", include_in_schema=False)
def listar_cargas(db: Session = Depends(get_db)):
    cargas = db.query(CargaCombustible).order_by(CargaCombustible.fecha.desc(), CargaCombustible.id.desc()).all()
    return [c.to_dict() for c in cargas]


@combustible_router.get("/vehiculo/{id_vehiculo}")
@combustible_router.get("/moto/{id_vehiculo}", include_in_schema=False)
def listar_cargas_por_vehiculo(id_vehiculo: int, db: Session = Depends(get_db)):
    cargas = (
        db.query(CargaCombustible)
        .filter(CargaCombustible.id_vehiculo == id_vehiculo)
        .order_by(CargaCombustible.fecha.desc(), CargaCombustible.id.desc())
        .all()
    )
    return [c.to_dict() for c in cargas]


@combustible_router.get("/precios")
def obtener_precios_combustible(db: Session = Depends(get_db)) -> Dict[str, float]:
    return {
        "extra": _obtener_precio(db, "precio_extra", 2.46),
        "super": _obtener_precio(db, "precio_super", 3.99),
    }


@combustible_router.put("/precios/{tipo}")
def actualizar_precio_combustible(
    tipo: str, payload: PrecioCombustibleUpdate, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    tipo_norm = tipo.strip().lower()
    clave = "precio_super" if tipo_norm == "super" else "precio_extra"
    _guardar_precio(db, clave, payload.precio)
    return {"tipo": tipo_norm, "precio": payload.precio}


@combustible_router.post("", status_code=status.HTTP_201_CREATED)
@combustible_router.post("/", status_code=status.HTTP_201_CREATED, include_in_schema=False)
def registrar_carga_combustible(payload: CargaCombustibleCreate, db: Session = Depends(get_db)):
    fecha_parsed = date.today()
    if payload.fecha:
        try:
            fecha_parsed = date.fromisoformat(payload.fecha[:10])
        except Exception:
            fecha_parsed = date.today()

    vehiculo = db.query(Vehiculo).filter(Vehiculo.id_vehiculo == payload.id_vehiculo).first()
    placa_final = payload.placa or (vehiculo.placa if vehiculo else "")

    nueva = CargaCombustible(
        id_vehiculo=payload.id_vehiculo,
        placa=placa_final,
        fecha=fecha_parsed,
        litros=float(payload.litros),
        costo_total=float(payload.costo_total),
        km_actual=int(payload.km_actual),
        km_anterior=int(payload.km_anterior or (vehiculo.kilometraje if vehiculo and vehiculo.kilometraje else 0)),
        notas=payload.notas,
    )
    db.add(nueva)

    if vehiculo and (vehiculo.kilometraje is None or payload.km_actual > vehiculo.kilometraje):
        vehiculo.kilometraje = payload.km_actual
        db.flush()
        AlertaMantenimientoService.verificar_y_enviar_alertas(db, vehiculo)

    db.commit()
    db.refresh(nueva)
    return nueva.to_dict()


@combustible_router.delete("/{id_carga}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_carga_combustible(id_carga: int, db: Session = Depends(get_db)):
    carga = db.query(CargaCombustible).filter(CargaCombustible.id == id_carga).first()
    if carga:
        db.delete(carga)
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

