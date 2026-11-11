from typing import List, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.exceptions import EntityNotFoundError, BusinessValidationError, ConflictError
from app.modules.vehiculos.models import Vehiculo
from app.modules.mantenimiento.service import AlertaMantenimientoService
from app.shared.storage_service import storage_service


class VehiculoService:
    @staticmethod
    def listar_todas(db: Session) -> List[Vehiculo]:
        return db.query(Vehiculo).order_by(Vehiculo.id_vehiculo.asc()).all()

    @staticmethod
    def obtener_por_id(db: Session, id_vehiculo: int) -> Vehiculo:
        vehiculo = db.query(Vehiculo).filter(Vehiculo.id_vehiculo == id_vehiculo).first()
        if not vehiculo:
            raise EntityNotFoundError("Vehiculo", id_vehiculo)
        return vehiculo

    @staticmethod
    def obtener_por_placa(db: Session, placa: str) -> Optional[Vehiculo]:
        placa_norm = (placa or "").strip().upper()
        return db.query(Vehiculo).filter(func.upper(Vehiculo.placa) == placa_norm).first()

    @staticmethod
    def listar_por_usuario(db: Session, id_usuario: int) -> List[Vehiculo]:
        return db.query(Vehiculo).filter(Vehiculo.id_usuario == id_usuario).order_by(Vehiculo.id_vehiculo.asc()).all()

    @staticmethod
    def listar_por_cedula(db: Session, cedula: str) -> List[Vehiculo]:
        """Proceso 1: Búsqueda del vehículo por la cédula del cliente."""
        from app.modules.usuarios.models import Usuario
        ced_norm = (cedula or "").strip()
        return (
            db.query(Vehiculo)
            .join(Usuario, Vehiculo.id_usuario == Usuario.id_usuario)
            .filter(Usuario.cedula == ced_norm)
            .order_by(Vehiculo.id_vehiculo.asc())
            .all()
        )

    @staticmethod
    def crear(db: Session, payload: Any) -> Vehiculo:
        placa_norm = (payload.placa or "").strip().upper()
        if not placa_norm:
            raise BusinessValidationError("La placa es obligatoria")

        if db.query(Vehiculo).filter(func.upper(Vehiculo.placa) == placa_norm).first():
            raise ConflictError(f"La placa {placa_norm} ya está registrada")

        nueva = Vehiculo(
            placa=placa_norm,
            anio=payload.anio if payload.anio is not None else 2024,
            marca=(payload.marca or "").strip(),
            modelo=(payload.modelo or "").strip(),
            nombre_vehiculo=payload.nombre_vehiculo or f"{payload.marca} {payload.modelo}".strip(),
            tipo_vehiculo=payload.tipo_vehiculo or "Automóvil",
            kilometraje=payload.kilometraje if payload.kilometraje is not None else 0,
            cilindraje=payload.cilindraje if payload.cilindraje is not None else 1600,
            id_usuario=payload.id_usuario,
            ruta_imagen_vehiculo=payload.ruta_imagen_vehiculo,
        )
        db.add(nueva)
        db.commit()
        db.refresh(nueva)

        # Inicializar mantenimientos preventivos con el kilometraje actual de ingreso
        AlertaMantenimientoService.inicializar_mantenimientos_vehiculo(
            db, nueva.id_vehiculo, nueva.cilindraje or 1600, nueva.kilometraje or 0
        )
        return nueva

    @staticmethod
    def actualizar(db: Session, id_vehiculo: int, payload: Any) -> Vehiculo:
        vehiculo = VehiculoService.obtener_por_id(db, id_vehiculo)
        km_anterior = vehiculo.kilometraje

        if payload.placa is not None and payload.placa.strip().upper() != vehiculo.placa.upper():
            nueva_placa = payload.placa.strip().upper()
            choque = (
                db.query(Vehiculo)
                .filter(func.upper(Vehiculo.placa) == nueva_placa, Vehiculo.id_vehiculo != id_vehiculo)
                .first()
            )
            if choque:
                raise ConflictError(f"La placa {nueva_placa} ya está registrada en otro vehículo")
            vehiculo.placa = nueva_placa

        if payload.anio is not None:
            vehiculo.anio = payload.anio
        if payload.marca is not None:
            vehiculo.marca = payload.marca.strip()
        if payload.modelo is not None:
            vehiculo.modelo = payload.modelo.strip()
        if payload.nombre_vehiculo is not None:
            vehiculo.nombre_vehiculo = payload.nombre_vehiculo
        if payload.tipo_vehiculo is not None:
            vehiculo.tipo_vehiculo = payload.tipo_vehiculo
        if payload.kilometraje is not None:
            vehiculo.kilometraje = payload.kilometraje
        if payload.cilindraje is not None:
            vehiculo.cilindraje = payload.cilindraje
        if payload.id_usuario is not None:
            vehiculo.id_usuario = payload.id_usuario

        if payload.ruta_imagen_vehiculo is not None:
            if (
                vehiculo.ruta_imagen_vehiculo
                and vehiculo.ruta_imagen_vehiculo != payload.ruta_imagen_vehiculo
                and "supabase.co" in vehiculo.ruta_imagen_vehiculo
            ):
                storage_service.delete_file(vehiculo.ruta_imagen_vehiculo)
            vehiculo.ruta_imagen_vehiculo = payload.ruta_imagen_vehiculo

        db.commit()
        db.refresh(vehiculo)

        # Si cambió el kilometraje, verificar alertas de mantenimiento
        if payload.kilometraje is not None and payload.kilometraje != km_anterior:
            AlertaMantenimientoService.verificar_y_enviar_alertas(db, vehiculo)

        return vehiculo

    @staticmethod
    def eliminar(db: Session, id_vehiculo: int) -> None:
        vehiculo = VehiculoService.obtener_por_id(db, id_vehiculo)
        if vehiculo.ruta_imagen_vehiculo and "supabase.co" in vehiculo.ruta_imagen_vehiculo:
            storage_service.delete_file(vehiculo.ruta_imagen_vehiculo)
        db.delete(vehiculo)
        db.commit()

