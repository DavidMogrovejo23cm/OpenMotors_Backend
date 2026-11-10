from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session

from app.core.exceptions import EntityNotFoundError, BusinessValidationError, ConflictError
from app.modules.roles.models import Rol, UsuarioRol


class RolService:
    @staticmethod
    def listar_todos(db: Session) -> List[Rol]:
        return db.query(Rol).order_by(Rol.id_rol.asc()).all()

    @staticmethod
    def obtener_por_id(db: Session, id_rol: int) -> Rol:
        rol = db.query(Rol).filter(Rol.id_rol == id_rol).first()
        if not rol:
            raise EntityNotFoundError("Rol", id_rol)
        return rol

    @staticmethod
    def crear(db: Session, nombre: str, id_rol: Optional[int] = None) -> Rol:
        nombre_norm = nombre.strip().upper()
        existente = db.query(Rol).filter(Rol.nombre == nombre_norm).first()
        if existente:
            raise ConflictError(f"El rol '{nombre_norm}' ya existe")
        nuevo = Rol(nombre=nombre_norm)
        if id_rol is not None:
            nuevo.id_rol = id_rol
        db.add(nuevo)
        db.commit()
        db.refresh(nuevo)
        return nuevo

    @staticmethod
    def actualizar(db: Session, id_rol: int, nombre: str) -> Rol:
        rol = RolService.obtener_por_id(db, id_rol)
        rol.nombre = nombre.strip().upper()
        db.commit()
        db.refresh(rol)
        return rol

    @staticmethod
    def eliminar(db: Session, id_rol: int) -> None:
        rol = RolService.obtener_por_id(db, id_rol)
        db.delete(rol)
        db.commit()


class UsuarioRolService:
    @staticmethod
    def asignar_rol(db: Session, id_usuario: int, id_rol: int, estado: int = 1) -> UsuarioRol:
        from app.modules.usuarios.models import Usuario

        usuario = db.query(Usuario).filter(Usuario.id_usuario == id_usuario).first()
        if not usuario:
            raise BusinessValidationError(f"Usuario con ID {id_usuario} no encontrado")

        rol = db.query(Rol).filter(Rol.id_rol == id_rol).first()
        if not rol:
            raise BusinessValidationError(f"Rol con ID {id_rol} no encontrado")

        existente = (
            db.query(UsuarioRol)
            .filter(UsuarioRol.id_usuario == id_usuario, UsuarioRol.id_rol == id_rol)
            .first()
        )
        if existente:
            existente.estado = estado if estado is not None else 1
            existente.fecha_modificacion = datetime.now()
            db.commit()
            db.refresh(existente)
            return existente

        nuevo = UsuarioRol(
            id_usuario=id_usuario,
            id_rol=id_rol,
            estado=estado if estado is not None else 1,
            fecha_creacion=datetime.now(),
        )
        db.add(nuevo)
        db.commit()
        db.refresh(nuevo)
        return nuevo

    @staticmethod
    def revocar_rol(db: Session, id_usuario: int, id_rol: int) -> UsuarioRol:
        rel = (
            db.query(UsuarioRol)
            .filter(UsuarioRol.id_usuario == id_usuario, UsuarioRol.id_rol == id_rol)
            .first()
        )
        if not rel:
            raise BusinessValidationError("Relación usuario-rol no encontrada")
        rel.estado = 0
        rel.fecha_modificacion = datetime.now()
        db.commit()
        db.refresh(rel)
        return rel

    @staticmethod
    def cambiar_categoria(db: Session, id_usuario: int, id_rol_actual: int, id_rol_nuevo: int) -> UsuarioRol:
        rel_actual = (
            db.query(UsuarioRol)
            .filter(UsuarioRol.id_usuario == id_usuario, UsuarioRol.id_rol == id_rol_actual)
            .first()
        )
        if rel_actual:
            rel_actual.estado = 0
            rel_actual.fecha_modificacion = datetime.now()
            db.commit()
        return UsuarioRolService.asignar_rol(db, id_usuario, id_rol_nuevo, 1)

    @staticmethod
    def suspender_rol(db: Session, id_usuario: int, id_rol: int) -> UsuarioRol:
        rel = (
            db.query(UsuarioRol)
            .filter(UsuarioRol.id_usuario == id_usuario, UsuarioRol.id_rol == id_rol)
            .first()
        )
        if not rel:
            raise BusinessValidationError("Relación usuario-rol no encontrada")
        rel.estado = 2
        rel.fecha_modificacion = datetime.now()
        db.commit()
        db.refresh(rel)
        return rel

    @staticmethod
    def reactivar_rol(db: Session, id_usuario: int, id_rol: int) -> UsuarioRol:
        rel = (
            db.query(UsuarioRol)
            .filter(UsuarioRol.id_usuario == id_usuario, UsuarioRol.id_rol == id_rol)
            .first()
        )
        if not rel:
            raise BusinessValidationError("Relación usuario-rol no encontrada")
        rel.estado = 1
        rel.fecha_modificacion = datetime.now()
        db.commit()
        db.refresh(rel)
        return rel

    @staticmethod
    def eliminar_relacion(db: Session, id_usuario: int, id_rol: int) -> None:
        rel = (
            db.query(UsuarioRol)
            .filter(UsuarioRol.id_usuario == id_usuario, UsuarioRol.id_rol == id_rol)
            .first()
        )
        if not rel:
            raise BusinessValidationError("Relación usuario-rol no encontrada")
        db.delete(rel)
        db.commit()

    @staticmethod
    def obtener_todos(db: Session) -> List[UsuarioRol]:
        return db.query(UsuarioRol).all()

    @staticmethod
    def obtener_roles_de_usuario(db: Session, id_usuario: int) -> List[UsuarioRol]:
        return db.query(UsuarioRol).filter(UsuarioRol.id_usuario == id_usuario).all()

    @staticmethod
    def obtener_roles_activos_de_usuario(db: Session, id_usuario: int) -> List[UsuarioRol]:
        return (
            db.query(UsuarioRol)
            .filter(UsuarioRol.id_usuario == id_usuario, UsuarioRol.estado == 1)
            .all()
        )

    @staticmethod
    def obtener_usuarios_por_rol(db: Session, id_rol: int) -> List[UsuarioRol]:
        return db.query(UsuarioRol).filter(UsuarioRol.id_rol == id_rol).all()

    @staticmethod
    def obtener_usuarios_activos_por_rol(db: Session, id_rol: int) -> List[UsuarioRol]:
        return (
            db.query(UsuarioRol)
            .filter(UsuarioRol.id_rol == id_rol, UsuarioRol.estado == 1)
            .all()
        )

    @staticmethod
    def obtener_todos_activos(db: Session) -> List[UsuarioRol]:
        return db.query(UsuarioRol).filter(UsuarioRol.estado == 1).all()

    @staticmethod
    def obtener_detalles_completos(db: Session) -> List[Dict[str, Any]]:
        relaciones = db.query(UsuarioRol).all()
        resultado = []
        for rel in relaciones:
            resultado.append({
                "idUsuario": rel.id_usuario,
                "id_usuario": rel.id_usuario,
                "nombreUsuario": rel.usuario.nombre_completo if rel.usuario else "",
                "correoUsuario": rel.usuario.correo if rel.usuario else "",
                "idRol": rel.id_rol,
                "id_rol": rel.id_rol,
                "nombreRol": rel.rol.nombre if rel.rol else "",
                "estado": rel.estado,
                "fechaCreacion": rel.fecha_creacion.isoformat() if rel.fecha_creacion else None,
                "fechaModificacion": rel.fecha_modificacion.isoformat() if rel.fecha_modificacion else None,
            })
        return resultado

    @staticmethod
    def obtener_nombres_roles_usuario(db: Session, id_usuario: int) -> List[str]:
        activos = UsuarioRolService.obtener_roles_activos_de_usuario(db, id_usuario)
        return [r.rol.nombre for r in activos if r.rol]

    @staticmethod
    def obtener_rol_principal(db: Session, id_usuario: int) -> Optional[str]:
        nombres = UsuarioRolService.obtener_nombres_roles_usuario(db, id_usuario)
        if not nombres:
            return None
        prioridad = ["ADMIN", "ADMINISTRADOR", "MECANICO", "CLIENTE"]
        for p in prioridad:
            if p in nombres:
                return p
        return nombres[0]

