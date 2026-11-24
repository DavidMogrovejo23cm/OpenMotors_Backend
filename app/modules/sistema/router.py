from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Body, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.authorization import CurrentUser, require_roles
from app.core.config import settings
from app.core.database import get_db
from app.modules.sistema.auditoria import AuditoriaOperacion, registrar_auditoria
from app.modules.sistema.backup import BackupService
from app.modules.sistema.service import metrics_collector
from app.modules.usuarios.models import Usuario
from app.shared.email_service import email_service

health_router = APIRouter(tags=["Salud y Sistema"])
metrics_router = APIRouter(prefix="/api/metrics/reports", tags=["Métricas y Reportes"])
auditoria_router = APIRouter(prefix="/api/sistema/auditoria", tags=["Auditoría"])
respaldos_router = APIRouter(prefix="/api/sistema/respaldos", tags=["Respaldos"])


@health_router.get("/api/health")
def api_health():
    return {
        "status": "UP",
        "service": "OpenAuto Backend (Python FastAPI)",
        "version": settings.APP_VERSION,
        "timestamp": datetime.now().isoformat(),
    }


@health_router.get("/api/health/email-test")
def email_test(to: str = Query(..., description="Correo destinatario de prueba")):
    res = email_service.enviar_correo_prueba(to)
    if res.get("exito"):
        return res
    return JSONResponse(status_code=500, content=res)


@health_router.get("/actuator/health")
def actuator_health():
    return {"status": "UP"}


@health_router.get("/actuator/info")
def actuator_info():
    return {
        "app": {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "engine": "Python FastAPI + SQLAlchemy 2.0",
        }
    }


# ==========================================
# REPORTES DE MÉTRICAS (/api/metrics/reports)
# ==========================================

@metrics_router.post("/generate")
def generate_manual_report():
    return metrics_collector.save_report("MANUAL")


@metrics_router.post("/midday")
def generate_midday_report():
    return metrics_collector.save_report("MIDDAY")


@metrics_router.post("/afternoon")
def generate_afternoon_report():
    return metrics_collector.save_report("AFTERNOON")


@metrics_router.get("/preview")
def preview_metrics():
    return metrics_collector.build_report("PREVIEW")


@metrics_router.get("/list")
def list_reports():
    return {"reports": metrics_collector.list_saved_reports()}


@metrics_router.get("/load/{filename}")
def load_report(filename: str):
    return metrics_collector.load_report(filename)


@metrics_router.delete("/cleanup")
def cleanup_reports(daysToKeep: int = Query(30)):
    deleted = metrics_collector.cleanup_old_reports(daysToKeep)
    return {"deleted": deleted, "daysToKeep": daysToKeep}


@metrics_router.get("/info")
def metrics_info():
    return {
        "reportsDirectory": metrics_collector.reports_dir,
        "localStorageEnabled": settings.METRICS_STORAGE_LOCAL_ENABLED,
        "gitlabEnabled": settings.GITLAB_ENABLED,
        "totalSavedReports": len(metrics_collector.list_saved_reports()),
    }


@metrics_router.get("/health")
def metrics_health():
    return {"status": "UP", "totalRequestsRecorded": metrics_collector.total_requests}


@auditoria_router.get("")
@auditoria_router.get("/", include_in_schema=False)
def listar_auditoria(
    entidad: Optional[str] = Query(default=None),
    accion: Optional[str] = Query(default=None),
    id_usuario: Optional[int] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_roles("ADMIN")),
):
    query = db.query(AuditoriaOperacion)
    if entidad:
        query = query.filter(AuditoriaOperacion.entidad == entidad.strip())
    if accion:
        query = query.filter(AuditoriaOperacion.accion == accion.strip().upper())
    if id_usuario is not None:
        query = query.filter(AuditoriaOperacion.id_usuario == id_usuario)
    rows = query.order_by(AuditoriaOperacion.fecha.desc(), AuditoriaOperacion.id_auditoria.desc()).limit(limit).all()
    return [r.to_dict() for r in rows]


@metrics_router.get("/gitlab/test")
def gitlab_test():
    return metrics_collector.test_gitlab_connection()


@metrics_router.get("/gitlab/list")
def gitlab_list():
    return {"files": metrics_collector.list_saved_reports()}


# ==========================================
# RESPALDOS Y RECUPERACIÓN (RNF-16 / RNF-17)
# ==========================================

def _responsable_backup(db: Session, current: CurrentUser) -> str:
    usuario = db.query(Usuario).filter(Usuario.id_usuario == current.id_usuario).first()
    if usuario and usuario.nombre_usuario:
        return usuario.nombre_usuario
    return f"usuario#{current.id_usuario}"


@respaldos_router.get("")
@respaldos_router.get("/", include_in_schema=False)
def listar_respaldos(
    _: CurrentUser = Depends(require_roles("ADMIN")),
):
    return BackupService.listar_respaldos()


@respaldos_router.post("", status_code=201)
@respaldos_router.post("/", status_code=201, include_in_schema=False)
def generar_respaldo(
    body: Optional[dict] = Body(default=None),
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles("ADMIN")),
):
    nota = (body or {}).get("nota") if isinstance(body, dict) else None
    responsable = _responsable_backup(db, current)
    res = BackupService.crear_respaldo(
        db,
        responsable=responsable,
        nota=str(nota) if nota is not None else None,
    )
    registrar_auditoria(
        db,
        id_usuario=current.id_usuario,
        accion="CREATE",
        entidad="SistemaRespaldo",
        id_referencia=None,
        detalle=f"Respaldo generado {res['backupId']} ({res['totalRegistros']} registros, {res['totalTablas']} tablas)",
        datos={"backupId": res["backupId"], "tipo": res["tipo"]},
    )
    db.commit()
    return res


@respaldos_router.get("/{backup_id}/verificar")
def verificar_respaldo(
    backup_id: str,
    _: CurrentUser = Depends(require_roles("ADMIN")),
):
    return BackupService.verificar_integridad(backup_id)


@respaldos_router.post("/{backup_id}/restaurar")
def restaurar_respaldo(
    backup_id: str,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles("ADMIN")),
):
    res = BackupService.restaurar_respaldo(db, backup_id)
    registrar_auditoria(
        db,
        id_usuario=current.id_usuario,
        accion="RESTORE",
        entidad="SistemaRespaldo",
        id_referencia=None,
        detalle=f"Base restaurada desde {res['backupId']} ({res['registrosRestaurados']} registros)",
        datos={"backupId": res["backupId"], "tablas": res["tablasRestauradas"]},
    )
    db.commit()
    return res

