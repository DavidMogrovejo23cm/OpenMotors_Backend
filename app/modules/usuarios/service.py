import re
import uuid
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.exceptions import EntityNotFoundError, BusinessValidationError, ConflictError
from app.core.security import hash_password, verify_password, is_bcrypt_hash, create_access_token
from app.modules.usuarios.models import Usuario, RecuperacionContrasena
from app.modules.roles.models import Rol, UsuarioRol
from app.shared.email_service import email_service
from app.shared.storage_service import storage_service

logger = logging.getLogger("gmotors.usuarios")


class UsuarioService:
    @staticmethod
    def listar_todos(db: Session) -> List[Usuario]:
        return db.query(Usuario).order_by(Usuario.id_usuario.asc()).all()

    @staticmethod
    def obtener_por_id(db: Session, id_usuario: int) -> Usuario:
        usuario = db.query(Usuario).filter(Usuario.id_usuario == id_usuario).first()
        if not usuario:
            raise EntityNotFoundError("Usuario", id_usuario)
        return usuario

    @staticmethod
    def registrar(db: Session, payload: Any, asignar_rol_cliente: bool = True) -> Usuario:
        correo_norm = (payload.correo or "").strip().lower()
        username_norm = (payload.nombre_usuario or "").strip()

        if not correo_norm or not username_norm:
            raise BusinessValidationError("El nombre de usuario y correo son obligatorios")

        if db.query(Usuario).filter(func.lower(Usuario.correo) == correo_norm).first():
            raise ConflictError("El correo electrónico ya está registrado")

        if db.query(Usuario).filter(func.lower(Usuario.nombre_usuario) == username_norm.lower()).first():
            raise ConflictError("El nombre de usuario ya está en uso")

        raw_pwd = payload.contrasena or "123456"
        pwd_hash = raw_pwd if is_bcrypt_hash(raw_pwd) else hash_password(raw_pwd)

        nuevo = Usuario(
            nombre_completo=(payload.nombre_completo or username_norm).strip(),
            nombre_usuario=username_norm,
            correo=correo_norm,
            contrasena=pwd_hash,
            pais=payload.pais or "Ecuador",
            ciudad=payload.ciudad,
            descripcion=payload.descripcion,
            ruta_imagen=payload.ruta_imagen,
            telefono=payload.telefono,
            cedula=payload.cedula,
            direccion=payload.direccion,
            puntos_bonus=payload.puntos_bonus if payload.puntos_bonus is not None else 0,
            codigo_referido=payload.codigo_referido,
            referido_usado=False,
        )
        nuevo.ensure_defaults()
        db.add(nuevo)
        db.commit()
        db.refresh(nuevo)

        # Mejora sobre el backend Java original: asignar automáticamente el rol CLIENTE (id_rol=2)
        if asignar_rol_cliente:
            rol_cliente = db.query(Rol).filter(Rol.id_rol == 2).first()
            if not rol_cliente:
                rol_cliente = db.query(Rol).filter(Rol.nombre == "CLIENTE").first()
            if rol_cliente:
                ya_tiene = (
                    db.query(UsuarioRol)
                    .filter(UsuarioRol.id_usuario == nuevo.id_usuario, UsuarioRol.id_rol == rol_cliente.id_rol)
                    .first()
                )
                if not ya_tiene:
                    rel = UsuarioRol(
                        id_usuario=nuevo.id_usuario,
                        id_rol=rol_cliente.id_rol,
                        estado=1,
                        fecha_creacion=datetime.now(),
                    )
                    db.add(rel)
                    db.commit()
                    db.refresh(nuevo)

        # Intentar enviar correo de bienvenida sin bloquear el registro
        try:
            email_service.enviar_correo_bienvenida(nuevo.correo, nuevo.nombre_completo, nuevo.nombre_usuario)
        except Exception as exc:
            logger.warning(f"No se pudo enviar correo de bienvenida a {nuevo.correo}: {exc}")

        return nuevo

    @staticmethod
    def actualizar(db: Session, id_usuario: int, payload: Any) -> Usuario:
        usuario = UsuarioService.obtener_por_id(db, id_usuario)

        if payload.nombre_completo is not None:
            usuario.nombre_completo = payload.nombre_completo.strip()
        if payload.nombre_usuario is not None and payload.nombre_usuario.strip() != usuario.nombre_usuario:
            nuevo_un = payload.nombre_usuario.strip()
            choque = (
                db.query(Usuario)
                .filter(func.lower(Usuario.nombre_usuario) == nuevo_un.lower(), Usuario.id_usuario != id_usuario)
                .first()
            )
            if choque:
                raise ConflictError("El nombre de usuario ya está en uso")
            usuario.nombre_usuario = nuevo_un

        if payload.correo is not None and payload.correo.strip().lower() != usuario.correo.lower():
            nuevo_correo = payload.correo.strip().lower()
            choque = (
                db.query(Usuario)
                .filter(func.lower(Usuario.correo) == nuevo_correo, Usuario.id_usuario != id_usuario)
                .first()
            )
            if choque:
                raise ConflictError("El correo electrónico ya está registrado")
            usuario.correo = nuevo_correo

        if payload.contrasena is not None and payload.contrasena.strip():
            raw_pwd = payload.contrasena.strip()
            usuario.contrasena = raw_pwd if is_bcrypt_hash(raw_pwd) else hash_password(raw_pwd)

        if payload.pais is not None:
            usuario.pais = payload.pais
        if payload.ciudad is not None:
            usuario.ciudad = payload.ciudad
        if payload.descripcion is not None:
            usuario.descripcion = payload.descripcion
        if payload.telefono is not None:
            usuario.telefono = payload.telefono
        if payload.cedula is not None:
            usuario.cedula = payload.cedula
        if payload.direccion is not None:
            usuario.direccion = payload.direccion
        if payload.puntos_bonus is not None:
            usuario.puntos_bonus = payload.puntos_bonus

        if payload.ruta_imagen is not None:
            if (
                usuario.ruta_imagen
                and usuario.ruta_imagen != payload.ruta_imagen
                and "supabase.co" in usuario.ruta_imagen
            ):
                storage_service.delete_file(usuario.ruta_imagen)
            usuario.ruta_imagen = payload.ruta_imagen

        usuario.ensure_defaults()
        db.commit()
        db.refresh(usuario)
        return usuario

    @staticmethod
    def eliminar(db: Session, id_usuario: int) -> None:
        usuario = UsuarioService.obtener_por_id(db, id_usuario)
        if usuario.ruta_imagen and "supabase.co" in usuario.ruta_imagen:
            storage_service.delete_file(usuario.ruta_imagen)
        db.delete(usuario)
        db.commit()

    @staticmethod
    def login(db: Session, identificador: str, contrasena: str) -> Dict[str, Any]:
        ident = (identificador or "").strip()
        if not ident:
            raise BusinessValidationError("Debe ingresar su usuario o correo")

        usuario = (
            db.query(Usuario)
            .filter(
                (func.lower(Usuario.nombre_usuario) == ident.lower())
                | (func.lower(Usuario.correo) == ident.lower())
            )
            .first()
        )
        if not usuario:
            raise PermissionError("Credenciales inválidas")

        # Soporte para login de Google OAuth determinístico (gm_google_...)
        es_login_google = contrasena.startswith("gm_google_")

        if es_login_google:
            # Si el usuario entra con Google, sincronizamos su hash o validamos correo
            if not verify_password(contrasena, usuario.contrasena):
                usuario.contrasena = hash_password(contrasena)
                db.commit()
        else:
            if not verify_password(contrasena, usuario.contrasena):
                raise PermissionError("Credenciales inválidas")
            # Si estaba en texto plano, migrar automáticamente a BCrypt
            if not is_bcrypt_hash(usuario.contrasena):
                usuario.contrasena = hash_password(contrasena)
                db.commit()

        usuario.ensure_defaults()
        db.commit()
        db.refresh(usuario)

        token = create_access_token(
            id_usuario=usuario.id_usuario,
            nombre_usuario=usuario.nombre_usuario,
            correo=usuario.correo,
        )
        data = usuario.to_dict(include_roles=True)
        data["token"] = token
        return data

    @staticmethod
    def usar_codigo_referido(db: Session, id_usuario: int, codigo: str) -> Dict[str, Any]:
        codigo_limpio = (codigo or "").strip().upper()
        if not codigo_limpio:
            raise BusinessValidationError("El código no puede estar vacío.")

        usuario_actual = UsuarioService.obtener_por_id(db, id_usuario)
        if usuario_actual.referido_usado:
            raise BusinessValidationError("Ya has utilizado un código de referido anteriormente.")

        if usuario_actual.codigo_referido and usuario_actual.codigo_referido.upper() == codigo_limpio:
            raise BusinessValidationError("No puedes usar tu propio código de referido.")

        referente = (
            db.query(Usuario)
            .filter(func.upper(Usuario.codigo_referido) == codigo_limpio)
            .first()
        )
        if not referente:
            raise BusinessValidationError("Código de referido inválido o no existe.")

        usuario_actual.puntos_bonus = (usuario_actual.puntos_bonus or 0) + 50
        usuario_actual.referido_usado = True
        referente.puntos_bonus = (referente.puntos_bonus or 0) + 50

        db.commit()
        db.refresh(usuario_actual)
        return {
            "mensaje": f"¡Código aplicado con éxito! Has ganado 50 puntos y tu amigo {referente.nombre_completo} también.",
            "nuevosPuntos": usuario_actual.puntos_bonus,
            "puntosBonus": usuario_actual.puntos_bonus,
        }


class RecuperacionContrasenaService:
    @staticmethod
    def solicitar_recuperacion(db: Session, correo: str) -> bool:
        correo_norm = (correo or "").strip().lower()
        usuario = db.query(Usuario).filter(func.lower(Usuario.correo) == correo_norm).first()
        if not usuario:
            return False

        # Invalidar tokens previos sin usar de este usuario
        tokens_previos = (
            db.query(RecuperacionContrasena)
            .filter(
                RecuperacionContrasena.id_usuario == usuario.id_usuario,
                RecuperacionContrasena.usado == False,  # noqa: E712
            )
            .all()
        )
        for t in tokens_previos:
            t.usado = True

        token_str = uuid.uuid4().hex + uuid.uuid4().hex[:16]
        ahora = datetime.now()
        expiracion = ahora + timedelta(minutes=30)

        nuevo_token = RecuperacionContrasena(
            token=token_str,
            id_usuario=usuario.id_usuario,
            fecha_creacion=ahora,
            fecha_expiracion=expiracion,
            usado=False,
        )
        db.add(nuevo_token)
        db.commit()

        email_service.enviar_correo_recuperacion(
            destinatario=usuario.correo,
            nombre_usuario=usuario.nombre_completo or usuario.nombre_usuario,
            token=token_str,
        )
        return True

    @staticmethod
    def validar_token(db: Session, token: str) -> Dict[str, Any]:
        token_limpio = (token or "").strip()
        reg = db.query(RecuperacionContrasena).filter(RecuperacionContrasena.token == token_limpio).first()
        if not reg:
            return {"valido": False, "mensaje": "El enlace de recuperación no existe o es inválido"}
        if reg.usado:
            return {"valido": False, "mensaje": "Este enlace de recuperación ya fue utilizado"}
        if datetime.now() > reg.fecha_expiracion:
            return {"valido": False, "mensaje": "El enlace de recuperación ha expirado"}

        return {
            "valido": True,
            "mensaje": "Token válido",
            "correo": reg.usuario.correo if reg.usuario else "",
            "nombreUsuario": reg.usuario.nombre_usuario if reg.usuario else "",
        }

    @staticmethod
    def validar_fortaleza_contrasena(pwd: str) -> None:
        if not pwd or len(pwd) < 8:
            raise BusinessValidationError("La contraseña debe tener al menos 8 caracteres")
        if not re.search(r"[A-Z]", pwd):
            raise BusinessValidationError("La contraseña debe incluir al menos una letra mayúscula")
        if not re.search(r"[a-z]", pwd):
            raise BusinessValidationError("La contraseña debe incluir al menos una letra minúscula")
        if not re.search(r"\d", pwd):
            raise BusinessValidationError("La contraseña debe incluir al menos un número")

    @staticmethod
    def restablecer_contrasena(db: Session, token: str, nueva_contrasena: str) -> bool:
        info = RecuperacionContrasenaService.validar_token(db, token)
        if not info.get("valido"):
            raise BusinessValidationError(info.get("mensaje", "Token inválido"))

        RecuperacionContrasenaService.validar_fortaleza_contrasena(nueva_contrasena)

        reg = db.query(RecuperacionContrasena).filter(RecuperacionContrasena.token == token.strip()).first()
        if not reg or not reg.usuario:
            raise BusinessValidationError("Usuario asociado al token no encontrado")

        reg.usuario.contrasena = hash_password(nueva_contrasena)
        reg.usado = True
        db.commit()
        return True

