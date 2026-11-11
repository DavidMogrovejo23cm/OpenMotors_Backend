"""Dependencias de autorización basadas en el usuario y sus roles activos."""

from dataclasses import dataclass
from typing import Callable

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.roles.models import UsuarioRol


@dataclass(frozen=True)
class CurrentUser:
    id_usuario: int
    roles: frozenset[str]


def current_user(request: Request, db: Session = Depends(get_db)) -> CurrentUser:
    """Obtiene el usuario autenticado y consulta sus roles activos en la base.

    Los roles no se toman del JWT: al suspender o revocar un rol, el permiso deja
    de existir de inmediato aunque el token aún no haya caducado.
    """
    payload = getattr(request.state, "user", None)
    if not isinstance(payload, dict):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Autenticación requerida")

    try:
        id_usuario = int(payload["id_usuario"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")

    relaciones = (
        db.query(UsuarioRol)
        .filter(UsuarioRol.id_usuario == id_usuario, UsuarioRol.estado == 1)
        .all()
    )
    roles = frozenset(
        relacion.rol.nombre.strip().upper()
        for relacion in relaciones
        if relacion.rol and relacion.rol.nombre
    )
    if not roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La cuenta no tiene un rol activo",
        )
    return CurrentUser(id_usuario=id_usuario, roles=roles)


def require_roles(*allowed_roles: str) -> Callable:
    allowed = frozenset(role.strip().upper() for role in allowed_roles)

    def dependency(user: CurrentUser = Depends(current_user)) -> CurrentUser:
        if not user.roles.intersection(allowed):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tiene permisos para esta acción")
        return user

    return dependency


def require_self_or_roles(*allowed_roles: str) -> Callable:
    """Permite acceder al propio recurso o a los roles internos indicados."""
    allowed = frozenset(role.strip().upper() for role in allowed_roles)

    def dependency(
        id_usuario: int,
        user: CurrentUser = Depends(current_user),
    ) -> CurrentUser:
        if user.id_usuario == id_usuario or user.roles.intersection(allowed):
            return user
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tiene permisos para este usuario")

    return dependency
