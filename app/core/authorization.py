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
    permisos: frozenset[str] = frozenset()


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

    from app.modules.usuarios.models import PermisoUsuario, Usuario, TokenRevocado

    usuario = db.query(Usuario).filter(Usuario.id_usuario == id_usuario).first()
    if not usuario:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no válido")
    if usuario.activo is False:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tu cuenta está suspendida. Contacta al dueño del taller.",
        )
    token_version = payload.get("tv")
    if (
        token_version is not None
        and usuario.token_version is not None
        and int(token_version) != int(usuario.token_version)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión invalidada. Inicia sesión nuevamente.",
        )
    jti = payload.get("jti")
    if jti and db.query(TokenRevocado).filter(TokenRevocado.jti == str(jti)).first():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="La sesión fue cerrada. Inicia sesión nuevamente.",
        )

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
    permisos = frozenset(p.clave for p in db.query(PermisoUsuario).filter(PermisoUsuario.id_usuario == id_usuario).all())
    actor = CurrentUser(id_usuario=id_usuario, roles=roles, permisos=permisos)
    db.info["actor"] = actor
    return actor


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
