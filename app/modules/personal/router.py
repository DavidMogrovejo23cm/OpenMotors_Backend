from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.authorization import CurrentUser, current_user, require_roles, require_self_or_roles
from app.core.database import get_db
from app.modules.personal.schemas import (
    PerfilLaboralUpdate,
    HorariosUsuarioUpdate,
    AsistenciaCreate,
    AsistenciaUpdate,
)
from app.modules.personal.service import PersonalService

personal_router = APIRouter(prefix="/api/personal", tags=["Gestión de Personal"])


@personal_router.get("/perfiles")
def listar_perfiles_personal(
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_roles("ADMIN")),
):
    """RF-40 / HU-50: Lista todo el personal del taller con su ficha laboral."""
    return PersonalService.listar_personal_con_perfil(db)


@personal_router.get("/{id_usuario}/perfil-laboral")
def obtener_perfil_laboral(
    id_usuario: int,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_self_or_roles("ADMIN")),
):
    return PersonalService.obtener_perfil(db, id_usuario)


@personal_router.put("/{id_usuario}/perfil-laboral")
def actualizar_perfil_laboral(
    id_usuario: int,
    payload: PerfilLaboralUpdate,
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_roles("ADMIN")),
):
    return PersonalService.guardar_perfil(db, id_usuario, payload, actor.id_usuario)


@personal_router.get("/horarios")
def listar_horarios_personal(
    id_usuario: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(current_user),
):
    """RF-41 / HU-51: ADMIN consulta cualquier horario; MECANICO solo su propio horario."""
    if "ADMIN" not in actor.roles:
        if "MECANICO" not in actor.roles:
            raise HTTPException(status_code=403, detail="No tiene permisos para consultar horarios")
        if id_usuario is not None and id_usuario != actor.id_usuario:
            raise HTTPException(status_code=403, detail="Solo puede consultar su propio horario")
        id_usuario = actor.id_usuario
    return PersonalService.listar_horarios(db, id_usuario=id_usuario)


@personal_router.put("/horarios/{id_usuario}")
def guardar_horario_personal(
    id_usuario: int,
    payload: HorariosUsuarioUpdate,
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_roles("ADMIN")),
):
    return PersonalService.guardar_horarios(db, id_usuario, payload.horarios, actor.id_usuario)


@personal_router.get("/asistencia")
def listar_asistencia_personal(
    fecha_inicio: Optional[str] = Query(default=None),
    fecha_fin: Optional[str] = Query(default=None),
    id_usuario: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(current_user),
):
    """RF-42 / HU-52: ADMIN consulta todo el equipo; MECANICO solo su asistencia."""
    if "ADMIN" not in actor.roles:
        if "MECANICO" not in actor.roles:
            raise HTTPException(status_code=403, detail="No tiene permisos para consultar asistencia")
        if id_usuario is not None and id_usuario != actor.id_usuario:
            raise HTTPException(status_code=403, detail="Solo puede consultar su propia asistencia")
        id_usuario = actor.id_usuario
    return PersonalService.listar_asistencia(
        db, fecha_inicio=fecha_inicio, fecha_fin=fecha_fin, id_usuario=id_usuario
    )


@personal_router.post("/asistencia", status_code=status.HTTP_201_CREATED)
def registrar_asistencia_personal(
    payload: AsistenciaCreate,
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_roles("ADMIN")),
):
    return PersonalService.registrar_asistencia(db, payload, actor.id_usuario)


@personal_router.put("/asistencia/{id_asistencia}")
def actualizar_asistencia_personal(
    id_asistencia: int,
    payload: AsistenciaUpdate,
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_roles("ADMIN")),
):
    return PersonalService.actualizar_asistencia(db, id_asistencia, payload, actor.id_usuario)


@personal_router.get("/reportes/desempeno")
def reporte_desempeno_mecanicos(
    fecha_inicio: Optional[str] = Query(default=None),
    fecha_fin: Optional[str] = Query(default=None),
    id_mecanico: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_roles("ADMIN")),
):
    """RF-58 / HU-69: Reporte gerencial de actividades y rendimiento de mecánicos."""
    return PersonalService.reporte_desempeno(
        db, fecha_inicio=fecha_inicio, fecha_fin=fecha_fin, id_mecanico=id_mecanico
    )
