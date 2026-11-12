import secrets
from fastapi import APIRouter, Depends, UploadFile, File, Form, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.authorization import CurrentUser, current_user, require_roles, require_self_or_roles
from app.core.exceptions import BusinessValidationError, EntityNotFoundError
from app.modules.usuarios.schemas import (
    UsuarioCreate,
    UsuarioUpdate,
    LoginRequest,
    UsarReferidoRequest,
    SolicitarRecuperacionRequest,
    ValidarTokenRequest,
    RestablecerContrasenaRequest,
    ClienteCreate,
)
from app.modules.usuarios.service import UsuarioService, RecuperacionContrasenaService
from app.shared.storage_service import storage_service

usuarios_router = APIRouter(prefix="/api/usuarios", tags=["Usuarios"])
recuperacion_router = APIRouter(prefix="/api/usuarios/recuperacion", tags=["Recuperación de Contraseña"])


# ==========================================
# ENDPOINTS DE USUARIOS (/api/usuarios)
# ==========================================

@usuarios_router.post("", status_code=status.HTTP_201_CREATED)
@usuarios_router.post("/", status_code=status.HTTP_201_CREATED, include_in_schema=False)
def registrar_usuario(payload: UsuarioCreate, db: Session = Depends(get_db)):
    """Registro público de nuevo usuario (asigna automáticamente el rol CLIENTE)."""
    nuevo = UsuarioService.registrar(db, payload, asignar_rol_cliente=True)
    return nuevo.to_dict(include_roles=True)


@usuarios_router.post("/clientes", status_code=status.HTTP_201_CREATED)
def crear_cliente(
    payload: ClienteCreate,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_roles("ADMIN", "MECANICO")),
):
    """Registra internamente a un cliente y entrega una clave temporal una sola vez."""
    contrasena_temporal = payload.contrasena_temporal or secrets.token_urlsafe(18)
    usuario_in = UsuarioCreate(
        nombre_completo=payload.nombre_completo,
        nombre_usuario=payload.nombre_usuario,
        correo=payload.correo,
        contrasena=contrasena_temporal,
        pais="Ecuador",
        ciudad=payload.ciudad,
        telefono=payload.telefono,
        cedula=payload.cedula,
        direccion=payload.direccion,
        descripcion="Cliente registrado por personal del taller",
    )
    nuevo = UsuarioService.registrar(db, usuario_in, asignar_rol_cliente=True)
    return {
        "usuario": nuevo.to_dict(include_roles=True),
        "credencialTemporal": {
            "nombreUsuario": nuevo.nombre_usuario,
            "contrasena": contrasena_temporal,
        },
    }


@usuarios_router.get("")
@usuarios_router.get("/", include_in_schema=False)
def listar_usuarios(
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_roles("ADMIN", "MECANICO")),
):
    usuarios = UsuarioService.listar_todos(db)
    return [u.to_dict(include_roles=True) for u in usuarios]


@usuarios_router.get("/{id_usuario}")
def obtener_usuario(
    id_usuario: int,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_self_or_roles("ADMIN", "MECANICO")),
):
    try:
        u = UsuarioService.obtener_por_id(db, id_usuario)
        return u.to_dict(include_roles=True)
    except EntityNotFoundError:
        return Response(status_code=status.HTTP_404_NOT_FOUND)


@usuarios_router.put("/{id_usuario}")
def actualizar_usuario(
    id_usuario: int,
    payload: UsuarioUpdate,
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_self_or_roles("ADMIN", "MECANICO")),
):
    puede_administrar = bool(actor.roles.intersection({"ADMIN", "MECANICO"}))
    u = UsuarioService.actualizar(
        db,
        id_usuario,
        payload,
        permitir_campos_administrativos=puede_administrar,
    )
    return u.to_dict(include_roles=True)


@usuarios_router.delete("/{id_usuario}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_usuario(
    id_usuario: int,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_roles("ADMIN")),
):
    UsuarioService.eliminar(db, id_usuario)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@usuarios_router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    identificador = payload.nombre_usuario or payload.correo or ""
    try:
        res = UsuarioService.login(db, identificador, payload.contrasena)
        return res
    except PermissionError:
        return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content="Credenciales inválidas")


@usuarios_router.get("/{id_usuario}/roles")
def obtener_roles_usuario(
    id_usuario: int,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_self_or_roles("ADMIN", "MECANICO")),
):
    u = UsuarioService.obtener_por_id(db, id_usuario)
    return [r.to_dict(include_usuario=False) for r in (u.roles or [])]


@usuarios_router.post("/upload")
def subir_imagen_perfil(
    archivo: UploadFile = File(...),
    _: CurrentUser = Depends(current_user),
):
    if not archivo or not archivo.filename:
        return JSONResponse(status_code=400, content={"error": "El archivo está vacío"})
    url = storage_service.upload_file(archivo, "perfiles", f"perfil_{_.id_usuario}")
    return {"url": url}


@usuarios_router.post("/{id_usuario}/usar-referido")
def usar_codigo_referido(
    id_usuario: int,
    payload: UsarReferidoRequest,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_self_or_roles("ADMIN", "MECANICO")),
):
    return UsuarioService.usar_codigo_referido(db, id_usuario, payload.codigo)


# ==========================================
# ENDPOINTS DE RECUPERACIÓN (/api/usuarios/recuperacion)
# ==========================================

@recuperacion_router.post("/solicitar")
def solicitar_recuperacion(payload: SolicitarRecuperacionRequest, db: Session = Depends(get_db)):
    correo = (payload.correo or "").strip()
    if not correo:
        return JSONResponse(status_code=400, content={"error": "El correo electrónico es obligatorio"})

    enviado = RecuperacionContrasenaService.solicitar_recuperacion(db, correo)
    if enviado:
        return {
            "mensaje": "Se ha enviado un correo con las instrucciones para restablecer tu contraseña",
            "exito": True,
        }
    return JSONResponse(
        status_code=404,
        content={
            "error": "No existe una cuenta asociada a este correo electrónico",
            "exito": False,
        },
    )


@recuperacion_router.post("/validar-token")
def validar_token(payload: ValidarTokenRequest, db: Session = Depends(get_db)):
    if not payload.token or not payload.token.strip():
        return JSONResponse(status_code=400, content={"valido": False, "error": "El token es obligatorio"})
    res = RecuperacionContrasenaService.validar_token(db, payload.token)
    if res.get("valido"):
        return res
    return JSONResponse(status_code=400, content=res)


@recuperacion_router.post("/restablecer")
def restablecer_contrasena(payload: RestablecerContrasenaRequest, db: Session = Depends(get_db)):
    try:
        exito = RecuperacionContrasenaService.restablecer_contrasena(
            db, payload.token, payload.nueva_contrasena
        )
        if exito:
            return {"mensaje": "Contraseña actualizada exitosamente", "exito": True}
        return JSONResponse(
            status_code=400,
            content={"error": "El enlace de recuperación es inválido o ha expirado", "exito": False},
        )
    except BusinessValidationError as exc:
        return JSONResponse(status_code=400, content={"error": exc.message, "exito": False})

