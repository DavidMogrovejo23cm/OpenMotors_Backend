from typing import List
from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.roles.schemas import (
    RolCreate,
    RolBase,
    RolResponse,
    AsignarRolRequest,
    CambiarCategoriaRequest,
)
from app.modules.roles.service import RolService, UsuarioRolService

rol_router = APIRouter(prefix="/api/rol", tags=["Roles"])
usuario_rol_router = APIRouter(prefix="/api/usuario_rol", tags=["Usuario-Rol"])


# ==========================================
# ENDPOINTS DE ROLES (/api/rol)
# ==========================================

@rol_router.get("", response_model=List[RolResponse])
@rol_router.get("/", response_model=List[RolResponse], include_in_schema=False)
def listar_roles(db: Session = Depends(get_db)):
    return RolService.listar_todos(db)


@rol_router.get("/{id_rol}", response_model=RolResponse)
def obtener_rol(id_rol: int, db: Session = Depends(get_db)):
    return RolService.obtener_por_id(db, id_rol)


@rol_router.post("", response_model=RolResponse, status_code=status.HTTP_201_CREATED)
@rol_router.post("/", response_model=RolResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
def crear_rol(payload: RolCreate, db: Session = Depends(get_db)):
    return RolService.crear(db, payload.nombre, payload.id_rol)


@rol_router.put("/{id_rol}", response_model=RolResponse)
def actualizar_rol(id_rol: int, payload: RolBase, db: Session = Depends(get_db)):
    return RolService.actualizar(db, id_rol, payload.nombre)


@rol_router.delete("/{id_rol}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_rol(id_rol: int, db: Session = Depends(get_db)):
    RolService.eliminar(db, id_rol)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ==========================================
# ENDPOINTS DE USUARIO_ROL (/api/usuario_rol)
# ==========================================

@usuario_rol_router.post("/asignar", status_code=status.HTTP_201_CREATED)
def asignar_rol(payload: AsignarRolRequest, db: Session = Depends(get_db)):
    rel = UsuarioRolService.asignar_rol(db, payload.id_usuario, payload.id_rol, payload.estado or 1)
    return rel.to_dict(include_usuario=True)


@usuario_rol_router.put("/revocar")
def revocar_rol(payload: AsignarRolRequest, db: Session = Depends(get_db)):
    rel = UsuarioRolService.revocar_rol(db, payload.id_usuario, payload.id_rol)
    return rel.to_dict(include_usuario=True)


@usuario_rol_router.put("/cambiar-categoria")
def cambiar_categoria(payload: CambiarCategoriaRequest, db: Session = Depends(get_db)):
    rel = UsuarioRolService.cambiar_categoria(
        db, payload.id_usuario, payload.id_rol_actual, payload.id_rol_nuevo
    )
    return rel.to_dict(include_usuario=True)


@usuario_rol_router.put("/suspender")
def suspender_rol(payload: AsignarRolRequest, db: Session = Depends(get_db)):
    rel = UsuarioRolService.suspender_rol(db, payload.id_usuario, payload.id_rol)
    return rel.to_dict(include_usuario=True)


@usuario_rol_router.put("/reactivar")
def reactivar_rol(payload: AsignarRolRequest, db: Session = Depends(get_db)):
    rel = UsuarioRolService.reactivar_rol(db, payload.id_usuario, payload.id_rol)
    return rel.to_dict(include_usuario=True)


@usuario_rol_router.delete("/{id_usuario}/{id_rol}")
def eliminar_relacion(id_usuario: int, id_rol: int, db: Session = Depends(get_db)):
    UsuarioRolService.eliminar_relacion(db, id_usuario, id_rol)
    return {"mensaje": "Relación eliminada exitosamente"}


@usuario_rol_router.get("")
@usuario_rol_router.get("/", include_in_schema=False)
def obtener_todos(db: Session = Depends(get_db)):
    rels = UsuarioRolService.obtener_todos(db)
    return [r.to_dict(include_usuario=True) for r in rels]


@usuario_rol_router.get("/usuario/{id_usuario}")
def obtener_roles_usuario(id_usuario: int, db: Session = Depends(get_db)):
    rels = UsuarioRolService.obtener_roles_de_usuario(db, id_usuario)
    return [r.to_dict(include_usuario=True) for r in rels]


@usuario_rol_router.get("/usuario/{id_usuario}/activos")
def obtener_roles_activos_usuario(id_usuario: int, db: Session = Depends(get_db)):
    rels = UsuarioRolService.obtener_roles_activos_de_usuario(db, id_usuario)
    return [r.to_dict(include_usuario=True) for r in rels]


@usuario_rol_router.get("/rol/{id_rol}")
def obtener_usuarios_por_rol(id_rol: int, db: Session = Depends(get_db)):
    rels = UsuarioRolService.obtener_usuarios_por_rol(db, id_rol)
    return [r.to_dict(include_usuario=True) for r in rels]


@usuario_rol_router.get("/rol/{id_rol}/activos")
def obtener_usuarios_activos_por_rol(id_rol: int, db: Session = Depends(get_db)):
    rels = UsuarioRolService.obtener_usuarios_activos_por_rol(db, id_rol)
    return [r.to_dict(include_usuario=True) for r in rels]


@usuario_rol_router.get("/activos")
def obtener_todos_activos(db: Session = Depends(get_db)):
    rels = UsuarioRolService.obtener_todos_activos(db)
    return [r.to_dict(include_usuario=True) for r in rels]


@usuario_rol_router.get("/detalles")
def obtener_detalles_completos(db: Session = Depends(get_db)):
    return UsuarioRolService.obtener_detalles_completos(db)


@usuario_rol_router.get("/usuario/{id_usuario}/nombres")
def obtener_nombres_roles_usuario(id_usuario: int, db: Session = Depends(get_db)):
    return UsuarioRolService.obtener_nombres_roles_usuario(db, id_usuario)


@usuario_rol_router.get("/usuario/{id_usuario}/principal")
def obtener_rol_principal(id_usuario: int, db: Session = Depends(get_db)):
    rol = UsuarioRolService.obtener_rol_principal(db, id_usuario)
    if not rol:
        return JSONResponse(status_code=404, content={"error": "El usuario no tiene roles activos"})
    return {"rolPrincipal": rol}


@usuario_rol_router.get("/usuario/{id_usuario}/requiere-cambio/{rol_id}")
def requiere_cambio_categoria(id_usuario: int, rol_id: int, db: Session = Depends(get_db)):
    activos = UsuarioRolService.obtener_roles_activos_de_usuario(db, id_usuario)
    ya_tiene = any(r.id_rol == rol_id for r in activos)
    return {"requiereCambio": not ya_tiene}

