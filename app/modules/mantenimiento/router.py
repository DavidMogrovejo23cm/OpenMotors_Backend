from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.mantenimiento.schemas import ParametroUpdate, MantenimientoRegistrarRequest
from app.modules.mantenimiento.service import MantenimientoService, AlertaMantenimientoService

parametros_router = APIRouter(prefix="/api/mantenimiento-parametros", tags=["Parámetros de Mantenimiento"])
mantenimientos_router = APIRouter(prefix="/api/mantenimientos", tags=["Mantenimientos Realizados"])
alertas_router = APIRouter(prefix="/api/alertas", tags=["Alertas de Mantenimiento"])


# ==========================================
# PARÁMETROS (/api/mantenimiento-parametros)
# ==========================================

@parametros_router.get("")
@parametros_router.get("/", include_in_schema=False)
def listar_parametros(db: Session = Depends(get_db)):
    params = MantenimientoService.listar_parametros(db)
    return [p.to_dict() for p in params]


@parametros_router.put("/{id_parametro}")
def actualizar_parametro(id_parametro: int, payload: ParametroUpdate, db: Session = Depends(get_db)):
    actualizado = MantenimientoService.actualizar_parametro(
        db, id_parametro, payload.intervalo_km, payload.descripcion
    )
    return actualizado.to_dict()


# ==========================================
# MANTENIMIENTOS REALIZADOS (/api/mantenimientos)
# ==========================================

@mantenimientos_router.get("/moto/{id_moto}")
def listar_mantenimientos_moto(id_moto: int, db: Session = Depends(get_db)):
    regs = MantenimientoService.listar_por_moto(db, id_moto)
    return [r.to_dict() for r in regs]


@mantenimientos_router.post("")
@mantenimientos_router.post("/", include_in_schema=False)
def registrar_mantenimiento(payload: MantenimientoRegistrarRequest, db: Session = Depends(get_db)):
    reg = MantenimientoService.registrar_o_actualizar(
        db, payload.id_moto, payload.tipo, payload.km_servicio
    )
    return reg.to_dict()


@mantenimientos_router.delete("/moto/{id_moto}/{tipo}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_mantenimiento(id_moto: int, tipo: str, db: Session = Depends(get_db)):
    MantenimientoService.eliminar_por_moto_y_tipo(db, id_moto, tipo)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ==========================================
# ALERTAS DE MANTENIMIENTO (/api/alertas)
# ==========================================

@alertas_router.get("/moto/{id_moto}")
def obtener_estado_mantenimiento(id_moto: int, db: Session = Depends(get_db)):
    from app.modules.motos.models import Moto

    moto = db.query(Moto).filter(Moto.id_moto == id_moto).first()
    if not moto:
        return Response(status_code=status.HTTP_404_NOT_FOUND)
    return AlertaMantenimientoService.calcular_estado(db, moto)


@alertas_router.post("/verificar/{id_moto}")
def verificar_y_alertar(id_moto: int, db: Session = Depends(get_db)):
    from app.modules.motos.models import Moto

    moto = db.query(Moto).filter(Moto.id_moto == id_moto).first()
    if not moto:
        return JSONResponse(status_code=404, content={"error": "Moto no encontrada"})
    estados = AlertaMantenimientoService.verificar_y_enviar_alertas(db, moto)
    return {
        "mensaje": "Verificación completada",
        "moto": f"{moto.marca} {moto.modelo} ({moto.placa})",
        "estados": estados,
    }

