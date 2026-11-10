import random
from fastapi import APIRouter, Depends, UploadFile, File, Form, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import get_db
from app.core.exceptions import BusinessValidationError, ConflictError, EntityNotFoundError
from app.modules.usuarios.schemas import (
    UsuarioCreate,
    UsuarioUpdate,
    LoginRequest,
    UsarReferidoRequest,
    SolicitarRecuperacionRequest,
    ValidarTokenRequest,
    RestablecerContrasenaRequest,
    QuickAccountRequest,
)
from app.modules.usuarios.service import UsuarioService, RecuperacionContrasenaService
from app.modules.usuarios.models import Usuario
from app.shared.storage_service import storage_service

usuarios_router = APIRouter(prefix="/api/usuarios", tags=["Usuarios"])
recuperacion_router = APIRouter(prefix="/api/usuarios/recuperacion", tags=["Recuperación de Contraseña"])
quick_account_router = APIRouter(prefix="/api/quick-accounts", tags=["Creación Rápida"])


# ==========================================
# ENDPOINTS DE USUARIOS (/api/usuarios)
# ==========================================

@usuarios_router.post("", status_code=status.HTTP_201_CREATED)
@usuarios_router.post("/", status_code=status.HTTP_201_CREATED, include_in_schema=False)
def registrar_usuario(payload: UsuarioCreate, db: Session = Depends(get_db)):
    nuevo = UsuarioService.registrar(db, payload, asignar_rol_cliente=True)
    return nuevo.to_dict(include_roles=True)


@usuarios_router.get("")
@usuarios_router.get("/", include_in_schema=False)
def listar_usuarios(db: Session = Depends(get_db)):
    usuarios = UsuarioService.listar_todos(db)
    return [u.to_dict(include_roles=True) for u in usuarios]


@usuarios_router.get("/{id_usuario}")
def obtener_usuario(id_usuario: int, db: Session = Depends(get_db)):
    try:
        u = UsuarioService.obtener_por_id(db, id_usuario)
        return u.to_dict(include_roles=True)
    except EntityNotFoundError:
        return Response(status_code=status.HTTP_404_NOT_FOUND)


@usuarios_router.put("/{id_usuario}")
def actualizar_usuario(id_usuario: int, payload: UsuarioUpdate, db: Session = Depends(get_db)):
    u = UsuarioService.actualizar(db, id_usuario, payload)
    return u.to_dict(include_roles=True)


@usuarios_router.delete("/{id_usuario}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_usuario(id_usuario: int, db: Session = Depends(get_db)):
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
def obtener_roles_usuario(id_usuario: int, db: Session = Depends(get_db)):
    u = UsuarioService.obtener_por_id(db, id_usuario)
    return [r.to_dict(include_usuario=False) for r in (u.roles or [])]


@usuarios_router.post("/upload")
def subir_imagen_perfil(
    archivo: UploadFile = File(...),
    nombreUsuario: str = Form("user"),
):
    if not archivo or not archivo.filename:
        return JSONResponse(status_code=400, content={"error": "El archivo está vacío"})
    url = storage_service.upload_file(archivo, "perfiles", f"perfil_{nombreUsuario}")
    return {"url": url}


@usuarios_router.post("/{id_usuario}/usar-referido")
def usar_codigo_referido(id_usuario: int, payload: UsarReferidoRequest, db: Session = Depends(get_db)):
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


# ==========================================
# ENDPOINTS DE CUENTA RÁPIDA (/api/quick-accounts)
# ==========================================

@quick_account_router.post("/create", status_code=status.HTTP_201_CREATED)
def crear_cuenta_rapida(payload: QuickAccountRequest, db: Session = Depends(get_db)):
    from app.modules.motos.schemas import MotoCreate
    from app.modules.motos.service import MotoService
    from app.modules.motos.models import Moto

    correo_norm = payload.correo.strip().lower()
    if db.query(Usuario).filter(func.lower(Usuario.correo) == correo_norm).first():
        raise ConflictError("El correo ya está registrado")

    placa_norm = payload.placa.strip().upper()
    if db.query(Moto).filter(func.upper(Moto.placa) == placa_norm).first():
        raise ConflictError("La placa ya está registrada")

    base_username = correo_norm.split("@")[0] if "@" in correo_norm else correo_norm
    username = base_username
    while db.query(Usuario).filter(func.lower(Usuario.nombre_usuario) == username.lower()).first():
        username = f"{base_username}{random.randint(100, 999)}"

    usuario_in = UsuarioCreate(
        nombre_completo=payload.nombreCompleto,
        nombre_usuario=username,
        correo=correo_norm,
        contrasena="root111",
        pais="Ecuador",
        ciudad=payload.ciudad or "Quito",
        telefono=payload.telefono,
        cedula=payload.cedula,
        direccion=payload.direccion,
        descripcion="Cuenta creada rápidamente desde recepción",
    )
    usuario_guardado = UsuarioService.registrar(db, usuario_in, asignar_rol_cliente=True)

    moto_in = MotoCreate(
        placa=placa_norm,
        marca=payload.marca,
        modelo=payload.modelo,
        anio=payload.anio or 2024,
        kilometraje=payload.kilometraje or 0,
        cilindraje=payload.cilindraje or 150,
        id_usuario=usuario_guardado.id_usuario,
        nombre_moto=payload.nombreMoto or f"{payload.marca} {payload.modelo}",
        tipo_moto=payload.tipoMoto or "Urbana",
        ruta_imagen_motos=payload.rutaImagenMotos,
    )
    moto_guardada = MotoService.crear(db, moto_in)

    return {
        "usuario": usuario_guardado.to_dict(include_roles=True),
        "moto": moto_guardada.to_dict(),
        "mensaje": "Cuenta y moto creadas exitosamente. Contraseña temporal: root111",
    }

