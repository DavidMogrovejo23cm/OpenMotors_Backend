from typing import Optional
from fastapi import APIRouter, Depends, Response, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.mantenimiento.schemas import (
    ParametroUpdate,
    MantenimientoRegistrarRequest,
    CitaMantenimientoCreate,
)
from app.modules.mantenimiento.service import (
    MantenimientoService,
    AlertaMantenimientoService,
    CitaMantenimientoService,
)

parametros_router = APIRouter(prefix="/api/mantenimiento-parametros", tags=["Parámetros de Mantenimiento"])
mantenimientos_router = APIRouter(prefix="/api/mantenimientos", tags=["Mantenimientos Realizados"])
alertas_router = APIRouter(prefix="/api/alertas", tags=["Alertas de Mantenimiento"])
citas_mantenimiento_router = APIRouter(prefix="/api/citas-mantenimiento", tags=["Fase E: Citas de Mantenimiento - Proceso 16"])


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

@mantenimientos_router.get("/vehiculo/{id_vehiculo}")
def listar_mantenimientos_vehiculo(id_vehiculo: int, db: Session = Depends(get_db)):
    regs = MantenimientoService.listar_por_vehiculo(db, id_vehiculo)
    return [r.to_dict() for r in regs]


@mantenimientos_router.post("")
@mantenimientos_router.post("/", include_in_schema=False)
def registrar_mantenimiento(payload: MantenimientoRegistrarRequest, db: Session = Depends(get_db)):
    reg = MantenimientoService.registrar_o_actualizar(
        db, payload.id_vehiculo, payload.tipo, payload.km_servicio
    )
    return reg.to_dict()


@mantenimientos_router.delete("/vehiculo/{id_vehiculo}/{tipo}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_mantenimiento(id_vehiculo: int, tipo: str, db: Session = Depends(get_db)):
    MantenimientoService.eliminar_por_vehiculo_y_tipo(db, id_vehiculo, tipo)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ==========================================
# ALERTAS DE MANTENIMIENTO (/api/alertas)
# ==========================================

@alertas_router.get("/vehiculo/{id_vehiculo}")
def obtener_estado_mantenimiento(id_vehiculo: int, db: Session = Depends(get_db)):
    from app.modules.vehiculos.models import Vehiculo

    vehiculo = db.query(Vehiculo).filter(Vehiculo.id_vehiculo == id_vehiculo).first()
    if not vehiculo:
        return Response(status_code=status.HTTP_404_NOT_FOUND)
    return AlertaMantenimientoService.calcular_estado(db, vehiculo)


@alertas_router.post("/verificar/{id_vehiculo}")
def verificar_y_alertar(id_vehiculo: int, db: Session = Depends(get_db)):
    from app.modules.vehiculos.models import Vehiculo

    vehiculo = db.query(Vehiculo).filter(Vehiculo.id_vehiculo == id_vehiculo).first()
    if not vehiculo:
        return JSONResponse(status_code=404, content={"error": "Vehículo no encontrado"})
    estados = AlertaMantenimientoService.verificar_y_enviar_alertas(db, vehiculo)
    return {
        "mensaje": "Verificación completada",
        "vehiculo": f"{vehiculo.marca} {vehiculo.modelo} ({vehiculo.placa})",
        "estados": estados,
    }


@alertas_router.get("/vehiculo/{id_vehiculo}/semaforo")
def obtener_semaforo_desgaste_proceso_15_1_y_16(id_vehiculo: int, db: Session = Depends(get_db)):
    """
    Proceso 15.1 y Proceso 16:
    Monitoreo de desgaste predictivo:
    - VERDE (<70%): Desgaste normal (Proceso 15.1: Mantener en verde y seguir revisando).
    - AMARILLO (70% a 89%): Alerta preventiva alcanzada (Proceso 16: Avisar al cliente).
    - ROJO (>=90% o vencido): Alerta urgente de reemplazo.
    """
    from app.modules.vehiculos.models import Vehiculo

    vehiculo = db.query(Vehiculo).filter(Vehiculo.id_vehiculo == id_vehiculo).first()
    if not vehiculo:
        return Response(status_code=status.HTTP_404_NOT_FOUND)
    estados = AlertaMantenimientoService.calcular_estado(db, vehiculo)
    piezas_alerta = [e for e in estados if e["porcentajeDesgaste"] >= 70]
    piezas_ok = [e for e in estados if e["porcentajeDesgaste"] < 70]

    return {
        "vehiculo": f"{vehiculo.marca} {vehiculo.modelo} ({vehiculo.placa})",
        "kilometraje_actual": vehiculo.kilometraje or 0,
        "total_piezas_monitoreadas": len(estados),
        "piezas_en_alerta": len(piezas_alerta),
        "estado_general_semaforo": "ROJO" if any(e["semaforo"] == "ROJO" for e in estados) else ("AMARILLO" if piezas_alerta else "VERDE"),
        "piezas_alerta_o_reemplazo": piezas_alerta,
        "piezas_en_rango_verde": piezas_ok,
    }


# ==========================================
# CITAS DE MANTENIMIENTO PREVENTIVO (/api/citas-mantenimiento) - PROCESO 16
# ==========================================

@citas_mantenimiento_router.post("", status_code=status.HTTP_201_CREATED)
@citas_mantenimiento_router.post("/", status_code=status.HTTP_201_CREATED, include_in_schema=False)
def agendar_cita_preventiva(payload: CitaMantenimientoCreate, db: Session = Depends(get_db)):
    """
    Proceso 16: Permite al cliente agendar una cita de mantenimiento preventivo a partir de los avisos de desgaste.
    """
    return CitaMantenimientoService.agendar_cita(db, payload)


@citas_mantenimiento_router.get("")
@citas_mantenimiento_router.get("/", include_in_schema=False)
def listar_citas_preventivas(
    id_vehiculo: Optional[int] = Query(default=None),
    id_usuario: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
):
    return CitaMantenimientoService.listar_citas(db, id_vehiculo=id_vehiculo, id_usuario=id_usuario)


