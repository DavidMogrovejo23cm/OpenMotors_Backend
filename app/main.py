import os
import time
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.security import decode_access_token
from app.core.seeder import init_db_and_seed
from app.shared.storage_service import storage_service
from app.shared.keepalive import keep_alive_loop
from app.modules.sistema.service import metrics_collector

# Routers de módulos de dominio
from app.modules.roles.router import rol_router, usuario_rol_router
from app.modules.usuarios.router import (
    usuarios_router,
    recuperacion_router,
)
from app.modules.usuarios.quick_router import quick_accounts_router
from app.modules.vehiculos.router import vehiculos_router, motos_router
from app.modules.mantenimiento.router import (
    parametros_router,
    mantenimientos_router,
    alertas_router,
    citas_mantenimiento_router,
)
from app.modules.inventario.router import (
    categorias_router,
    productos_router,
    proveedores_router,
    kardex_router,
    reservas_router,
)
from app.modules.facturacion.router import (
    facturas_router,
    detalles_factura_router,
    notas_venta_router,
)
from app.modules.taller.router import (
    tipos_router,
    registros_router,
    diagnosticos_router,
    recepciones_router,
    presupuestos_router,
    reparaciones_router,
    entregas_router,
)
from app.modules.combustible.router import combustible_router
from app.modules.finanzas.router import pagos_router
from app.modules.rutas.router import rutas_router
from app.modules.marketing.router import ofertas_router
from app.modules.sistema.router import health_router, metrics_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("openauto.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Iniciando OpenAuto Backend (Python FastAPI)...")
    init_db_and_seed()
    storage_service.ensure_bucket()
    keep_alive_task = asyncio.create_task(keep_alive_loop())
    yield
    keep_alive_task.cancel()
    logger.info("OpenAuto Backend detenido correctamente.")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="API Backend Modular de Open Auto — Taller Automotriz y Gestión de Autos (FastAPI + SQLAlchemy 2.0)",
    lifespan=lifespan,
)

# Registrar manejadores globales de excepciones
register_exception_handlers(app)

# Configurar CORS compatible con el frontend React/Vite y despliegues en Vercel/Render
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)


def _is_public_route(method: str, path: str) -> bool:
    """Verifica si una ruta es pública según las reglas de seguridad."""
    if method == "OPTIONS":
        return True
    public_exact = {
        "/",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/health",
        "/api/health",
        "/api/usuarios/login",
        "/actuator/health",
        "/actuator/info",
    }
    if path in public_exact:
        return True

    # Permitir autoregistro público de usuarios
    if method == "POST" and path in ("/api/usuarios", "/api/usuarios/"):
        return True

    # Permitir lectura pública de catálogo de roles
    if method == "GET" and path in ("/api/rol", "/api/rol/"):
        return True

    public_prefixes = (
        "/api/usuarios/recuperacion/",
        "/api/metrics/",
        "/images/",
        "/static/",
    )
    return any(path.startswith(pref) for pref in public_prefixes)


@app.middleware("http")
async def security_and_metrics_middleware(request: Request, call_next):
    start_time = time.perf_counter()
    path = request.url.path
    method = request.method

    # Validar JWT si hay cabecera Authorization o si la ruta es protegida
    auth_header = request.headers.get("Authorization") or request.headers.get("authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1].strip()
        payload = decode_access_token(token)
        if payload:
            request.state.user = payload
        elif not _is_public_route(method, path):
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            metrics_collector.record_request(method, path, 401, duration_ms)
            return JSONResponse(
                status_code=401,
                content={"error": "No autorizado. Token inválido o expirado."},
            )
    elif not _is_public_route(method, path):
        # Si no envía token en una ruta protegida, rechazamos con 401 igual que Spring Security
        duration_ms = (time.perf_counter() - start_time) * 1000.0
        metrics_collector.record_request(method, path, 401, duration_ms)
        return JSONResponse(
            status_code=401,
            content={"error": "No autorizado. Token inválido o ausente."},
        )

    response = await call_next(request)
    duration_ms = (time.perf_counter() - start_time) * 1000.0
    metrics_collector.record_request(method, path, response.status_code, duration_ms)
    return response


# Montar archivos estáticos (/images y /static)
static_dir = os.path.abspath("static")
images_dir = os.path.join(static_dir, "images")
uploads_dir = os.path.join(static_dir, "uploads")
os.makedirs(images_dir, exist_ok=True)
os.makedirs(uploads_dir, exist_ok=True)

# Si existe el logo en la ruta antigua de recursos Java, copiarlo automáticamente a static/images
legacy_logo = os.path.abspath("src/main/resources/static/images/gorila-logo.png")
target_logo = os.path.join(images_dir, "gorila-logo.png")
if os.path.exists(legacy_logo) and not os.path.exists(target_logo):
    import shutil
    shutil.copyfile(legacy_logo, target_logo)

app.mount("/images", StaticFiles(directory=images_dir), name="images")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Registrar todos los routers de dominio
app.include_router(rol_router)
app.include_router(usuario_rol_router)
app.include_router(usuarios_router)
app.include_router(quick_accounts_router)
app.include_router(recuperacion_router)
app.include_router(vehiculos_router)
app.include_router(motos_router)
app.include_router(parametros_router)
app.include_router(mantenimientos_router)
app.include_router(alertas_router)
app.include_router(citas_mantenimiento_router)
app.include_router(categorias_router)
app.include_router(productos_router)
app.include_router(proveedores_router)
app.include_router(kardex_router)
app.include_router(reservas_router)
app.include_router(facturas_router)
app.include_router(detalles_factura_router)
app.include_router(notas_venta_router)
app.include_router(tipos_router)
app.include_router(registros_router)
app.include_router(diagnosticos_router)
app.include_router(recepciones_router)
app.include_router(presupuestos_router)
app.include_router(reparaciones_router)
app.include_router(entregas_router)
app.include_router(combustible_router)
app.include_router(pagos_router)
app.include_router(rutas_router)
app.include_router(ofertas_router)
app.include_router(health_router)
app.include_router(metrics_router)


@app.get("/", include_in_schema=False)
def root():
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "UP",
        "docs": "/docs",
    }

