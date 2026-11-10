from typing import List, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.exceptions import EntityNotFoundError, BusinessValidationError, ConflictError
from app.modules.motos.models import Moto
from app.modules.mantenimiento.service import AlertaMantenimientoService
from app.shared.storage_service import storage_service


class MotoService:
    @staticmethod
    def listar_todas(db: Session) -> List[Moto]:
        return db.query(Moto).order_by(Moto.id_moto.asc()).all()

    @staticmethod
    def obtener_por_id(db: Session, id_moto: int) -> Moto:
        moto = db.query(Moto).filter(Moto.id_moto == id_moto).first()
        if not moto:
            raise EntityNotFoundError("Moto", id_moto)
        return moto

    @staticmethod
    def obtener_por_placa(db: Session, placa: str) -> Optional[Moto]:
        placa_norm = (placa or "").strip().upper()
        return db.query(Moto).filter(func.upper(Moto.placa) == placa_norm).first()

    @staticmethod
    def listar_por_usuario(db: Session, id_usuario: int) -> List[Moto]:
        return db.query(Moto).filter(Moto.id_usuario == id_usuario).order_by(Moto.id_moto.asc()).all()

    @staticmethod
    def crear(db: Session, payload: Any) -> Moto:
        placa_norm = (payload.placa or "").strip().upper()
        if not placa_norm:
            raise BusinessValidationError("La placa es obligatoria")

        if db.query(Moto).filter(func.upper(Moto.placa) == placa_norm).first():
            raise ConflictError(f"La placa {placa_norm} ya está registrada")

        nueva = Moto(
            placa=placa_norm,
            anio=payload.anio if payload.anio is not None else 2024,
            marca=(payload.marca or "").strip(),
            modelo=(payload.modelo or "").strip(),
            nombre_moto=payload.nombre_moto or f"{payload.marca} {payload.modelo}".strip(),
            tipo_moto=payload.tipo_moto or "Urbana",
            kilometraje=payload.kilometraje if payload.kilometraje is not None else 0,
            cilindraje=payload.cilindraje if payload.cilindraje is not None else 150,
            id_usuario=payload.id_usuario,
            ruta_imagen_motos=payload.ruta_imagen_motos,
        )
        db.add(nueva)
        db.commit()
        db.refresh(nueva)

        # Inicializar mantenimientos preventivos con el kilometraje actual de ingreso
        AlertaMantenimientoService.inicializar_mantenimientos_moto(
            db, nueva.id_moto, nueva.cilindraje or 150, nueva.kilometraje or 0
        )
        return nueva

    @staticmethod
    def actualizar(db: Session, id_moto: int, payload: Any) -> Moto:
        moto = MotoService.obtener_por_id(db, id_moto)
        km_anterior = moto.kilometraje

        if payload.placa is not None and payload.placa.strip().upper() != moto.placa.upper():
            nueva_placa = payload.placa.strip().upper()
            choque = (
                db.query(Moto)
                .filter(func.upper(Moto.placa) == nueva_placa, Moto.id_moto != id_moto)
                .first()
            )
            if choque:
                raise ConflictError(f"La placa {nueva_placa} ya está registrada en otra motocicleta")
            moto.placa = nueva_placa

        if payload.anio is not None:
            moto.anio = payload.anio
        if payload.marca is not None:
            moto.marca = payload.marca.strip()
        if payload.modelo is not None:
            moto.modelo = payload.modelo.strip()
        if payload.nombre_moto is not None:
            moto.nombre_moto = payload.nombre_moto
        if payload.tipo_moto is not None:
            moto.tipo_moto = payload.tipo_moto
        if payload.kilometraje is not None:
            moto.kilometraje = payload.kilometraje
        if payload.cilindraje is not None:
            moto.cilindraje = payload.cilindraje
        if payload.id_usuario is not None:
            moto.id_usuario = payload.id_usuario

        if payload.ruta_imagen_motos is not None:
            if (
                moto.ruta_imagen_motos
                and moto.ruta_imagen_motos != payload.ruta_imagen_motos
                and "supabase.co" in moto.ruta_imagen_motos
            ):
                storage_service.delete_file(moto.ruta_imagen_motos)
            moto.ruta_imagen_motos = payload.ruta_imagen_motos

        db.commit()
        db.refresh(moto)

        # Si cambió el kilometraje, verificar alertas de mantenimiento
        if payload.kilometraje is not None and payload.kilometraje != km_anterior:
            AlertaMantenimientoService.verificar_y_enviar_alertas(db, moto)

        return moto

    @staticmethod
    def eliminar(db: Session, id_moto: int) -> None:
        moto = MotoService.obtener_por_id(db, id_moto)
        if moto.ruta_imagen_motos and "supabase.co" in moto.ruta_imagen_motos:
            storage_service.delete_file(moto.ruta_imagen_motos)
        db.delete(moto)
        db.commit()

