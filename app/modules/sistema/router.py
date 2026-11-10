from datetime import datetime
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.modules.sistema.service import metrics_collector
from app.shared.email_service import email_service

health_router = APIRouter(tags=["Salud y Sistema"])
metrics_router = APIRouter(prefix="/api/metrics/reports", tags=["Métricas y Reportes"])


@health_router.get("/api/health")
def api_health():
    return {
        "status": "UP",
        "service": "OpenMotors Backend (Python FastAPI)",
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


@metrics_router.get("/gitlab/test")
def gitlab_test():
    return metrics_collector.test_gitlab_connection()


@metrics_router.get("/gitlab/list")
def gitlab_list():
    return {"files": metrics_collector.list_saved_reports()}

