import logging
from datetime import date, datetime
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.exceptions import EntityNotFoundError, BusinessValidationError
from app.modules.taller.models import Tipo, Registro, DiagnosticoMoto, DetalleDiagnostico
from app.modules.motos.models import Moto
from app.modules.usuarios.models import Usuario
from app.modules.facturacion.models import Factura, DetalleFactura
from app.modules.mantenimiento.service import AlertaMantenimientoService
from app.shared.email_service import email_service

logger = logging.getLogger("gmotors.taller")


class TipoService:
    @staticmethod
    def listar_todos(db: Session) -> List[Tipo]:
        return db.query(Tipo).order_by(Tipo.id_tipo.asc()).all()

    @staticmethod
    def obtener_por_id(db: Session, id_tipo: int) -> Tipo:
        t = db.query(Tipo).filter(Tipo.id_tipo == id_tipo).first()
        if not t:
            raise EntityNotFoundError("Tipo de servicio", id_tipo)
        return t

    @staticmethod
    def crear(db: Session, payload: Any) -> Tipo:
        nuevo = Tipo(
            nombre=(payload.nombre or "").strip(),
            descripcion=payload.descripcion,
            id_producto=payload.id_producto,
            concepto_manual=payload.concepto_manual,
            concepto_cantidad=payload.concepto_cantidad if payload.concepto_cantidad is not None else 1,
            concepto_precio_unitario=float(payload.concepto_precio_unitario or 0.0),
        )
        db.add(nuevo)
        db.commit()
        db.refresh(nuevo)
        return nuevo

    @staticmethod
    def actualizar(db: Session, id_tipo: int, payload: Any) -> Tipo:
        t = TipoService.obtener_por_id(db, id_tipo)
        t.nombre = (payload.nombre or t.nombre).strip()
        t.descripcion = payload.descripcion
        t.id_producto = payload.id_producto
        t.concepto_manual = payload.concepto_manual
        t.concepto_cantidad = payload.concepto_cantidad if payload.concepto_cantidad is not None else 1
        t.concepto_precio_unitario = float(payload.concepto_precio_unitario or 0.0)
        db.commit()
        db.refresh(t)
        return t

    @staticmethod
    def eliminar(db: Session, id_tipo: int) -> None:
        t = TipoService.obtener_por_id(db, id_tipo)
        db.delete(t)
        db.commit()


class RegistroService:
    @staticmethod
    def _parse_date(val: Optional[str]) -> date:
        if not val:
            return date.today()
        try:
            return date.fromisoformat(val[:10])
        except Exception:
            return date.today()

    @staticmethod
    def _parse_datetime(val: Optional[str]) -> Optional[datetime]:
        if not val:
            return None
        try:
            return datetime.fromisoformat(val.replace("Z", "+00:00"))
        except Exception:
            return None

    @staticmethod
    def construir_listado_dto(db: Session, reg: Registro) -> Dict[str, Any]:
        moto = reg.moto or db.query(Moto).filter(Moto.id_moto == reg.id_moto).first()
        cliente = moto.usuario if moto else None
        encargado = reg.encargado or (
            db.query(Usuario).filter(Usuario.id_usuario == reg.id_encargado).first()
            if reg.id_encargado
            else None
        )
        tipo_obj = reg.tipo or (
            db.query(Tipo).filter(Tipo.id_tipo == reg.id_tipo).first()
            if reg.id_tipo
            else None
        )

        detalles_dto: List[Dict[str, Any]] = []
        costo_final = float(reg.costo_total or 0.0)

        if reg.id_factura:
            factura = reg.factura or db.query(Factura).filter(Factura.id_factura == reg.id_factura).first()
            if factura and factura.costo_total is not None and factura.costo_total > 0:
                costo_final = float(factura.costo_total)
            dets = (
                db.query(DetalleFactura)
                .filter(DetalleFactura.id_factura == reg.id_factura)
                .order_by(DetalleFactura.id_detalle.asc())
                .all()
            )
            detalles_dto = [d.to_dict() for d in dets]

        return {
            "id_registro": reg.id_registro,
            "id_moto": reg.id_moto,
            "id_cliente": cliente.id_usuario if cliente else 0,
            "nombre_cliente": cliente.nombre_completo if cliente else "Cliente General",
            "cliente_cedula": cliente.cedula if cliente else None,
            "cliente_telefono": cliente.telefono if cliente else None,
            "cliente_correo": cliente.correo if cliente else None,
            "cliente_direccion": cliente.direccion if cliente else None,
            "id_encargado": encargado.id_usuario if encargado else (reg.id_encargado or 0),
            "nombre_encargado": encargado.nombre_completo if encargado else "Por asignar",
            "marca_moto": moto.marca if moto else "",
            "modelo_moto": moto.modelo if moto else "",
            "placa": moto.placa if moto else "",
            "ruta_imagen_moto": moto.ruta_imagen_motos if moto else None,
            "fecha": reg.fecha.isoformat() if reg.fecha else date.today().isoformat(),
            "fecha_entrega_estimada": (
                reg.fecha_entrega_estimada.isoformat() if reg.fecha_entrega_estimada else None
            ),
            "fecha_completado": reg.fecha_completado.isoformat() if reg.fecha_completado else None,
            "fecha_entregado": reg.fecha_entregado.isoformat() if reg.fecha_entregado else None,
            "fecha_facturado": reg.fecha_facturado.isoformat() if reg.fecha_facturado else None,
            "descripcion": reg.descripcion or "",
            "observaciones": reg.observaciones or "",
            "id_tipo": reg.id_tipo,
            "tipo_servicio": tipo_obj.nombre if tipo_obj else "Servicio General",
            "kilometraje": (
                reg.kilometraje
                if reg.kilometraje is not None
                else (moto.kilometraje if moto and moto.kilometraje is not None else 0)
            ),
            "costo_total": round(costo_final, 2),
            "id_factura": reg.id_factura,
            "detalles": detalles_dto,
            "estado": reg.estado if reg.estado is not None else 1,
        }

    @staticmethod
    def crear(db: Session, payload: Any) -> Dict[str, Any]:
        moto = db.query(Moto).filter(Moto.id_moto == payload.id_moto).first()
        if not moto:
            raise EntityNotFoundError("Moto", payload.id_moto)

        km_reg = payload.kilometraje if payload.kilometraje is not None else (moto.kilometraje or 0)

        nuevo = Registro(
            fecha=RegistroService._parse_date(payload.fecha),
            fecha_entrega_estimada=RegistroService._parse_datetime(payload.fecha_entrega_estimada),
            descripcion=payload.descripcion,
            observaciones=payload.observaciones,
            costo_total=float(payload.costo_total or 0.0),
            id_moto=payload.id_moto,
            id_encargado=payload.id_encargado,
            id_tipo=payload.id_tipo,
            id_factura=payload.id_factura,
            kilometraje=km_reg,
            estado=payload.estado if payload.estado is not None else 1,
        )
        db.add(nuevo)

        # Si el kilometraje de ingreso es mayor al actual de la moto, actualizar la moto
        if km_reg and (moto.kilometraje is None or km_reg > moto.kilometraje):
            moto.kilometraje = km_reg
            db.flush()
            AlertaMantenimientoService.verificar_y_enviar_alertas(db, moto)

        db.commit()
        db.refresh(nuevo)
        return RegistroService.construir_listado_dto(db, nuevo)

    @staticmethod
    def listar_todos_dto(db: Session) -> List[Dict[str, Any]]:
        regs = db.query(Registro).order_by(Registro.id_registro.desc()).all()
        return [RegistroService.construir_listado_dto(db, r) for r in regs]

    @staticmethod
    def obtener_por_id_dto(db: Session, id_registro: int) -> Dict[str, Any]:
        reg = db.query(Registro).filter(Registro.id_registro == id_registro).first()
        if not reg:
            raise EntityNotFoundError("Registro", id_registro)
        return RegistroService.construir_listado_dto(db, reg)

    @staticmethod
    def listar_por_cliente(db: Session, id_cliente: int) -> List[Dict[str, Any]]:
        regs = (
            db.query(Registro)
            .join(Moto, Registro.id_moto == Moto.id_moto)
            .filter(Moto.id_usuario == id_cliente)
            .order_by(Registro.id_registro.desc())
            .all()
        )
        return [RegistroService.construir_listado_dto(db, r) for r in regs]

    @staticmethod
    def listar_por_encargado(db: Session, id_encargado: int) -> List[Dict[str, Any]]:
        regs = (
            db.query(Registro)
            .filter(Registro.id_encargado == id_encargado)
            .order_by(Registro.id_registro.desc())
            .all()
        )
        return [RegistroService.construir_listado_dto(db, r) for r in regs]

    @staticmethod
    def buscar_por_placa(db: Session, placa: str) -> List[Dict[str, Any]]:
        q = (placa or "").strip().upper()
        regs = (
            db.query(Registro)
            .join(Moto, Registro.id_moto == Moto.id_moto)
            .filter(func.upper(Moto.placa).contains(q))
            .order_by(Registro.id_registro.desc())
            .all()
        )
        return [RegistroService.construir_listado_dto(db, r) for r in regs]

    @staticmethod
    def buscar_por_nombre_cliente(db: Session, nombre: str) -> List[Dict[str, Any]]:
        q = (nombre or "").strip().lower()
        regs = (
            db.query(Registro)
            .join(Moto, Registro.id_moto == Moto.id_moto)
            .join(Usuario, Moto.id_usuario == Usuario.id_usuario)
            .filter(func.lower(Usuario.nombre_completo).contains(q))
            .order_by(Registro.id_registro.desc())
            .all()
        )
        return [RegistroService.construir_listado_dto(db, r) for r in regs]

    @staticmethod
    def asociar_factura(db: Session, id_registro: int, id_factura: int) -> Dict[str, Any]:
        reg = db.query(Registro).filter(Registro.id_registro == id_registro).first()
        if not reg:
            raise EntityNotFoundError("Registro", id_registro)
        factura = db.query(Factura).filter(Factura.id_factura == id_factura).first()
        if not factura:
            raise EntityNotFoundError("Factura", id_factura)

        reg.id_factura = id_factura
        if factura.costo_total and factura.costo_total > 0:
            reg.costo_total = factura.costo_total
        db.commit()
        db.refresh(reg)
        return RegistroService.construir_listado_dto(db, reg)

    @staticmethod
    def cambiar_estado(db: Session, id_registro: int, nuevo_estado: int) -> Dict[str, Any]:
        reg = db.query(Registro).filter(Registro.id_registro == id_registro).first()
        if not reg:
            raise EntityNotFoundError("Registro", id_registro)

        ahora = datetime.now()
        reg.estado = nuevo_estado
        if nuevo_estado == 2 and not reg.fecha_completado:
            reg.fecha_completado = ahora
        elif nuevo_estado == 3 and not reg.fecha_entregado:
            if not reg.fecha_completado:
                reg.fecha_completado = ahora
            reg.fecha_entregado = ahora
        elif nuevo_estado == 4:
            if not reg.fecha_completado:
                reg.fecha_completado = ahora
            if not reg.fecha_entregado:
                reg.fecha_entregado = ahora
            reg.fecha_facturado = ahora

        db.commit()
        db.refresh(reg)
        dto = RegistroService.construir_listado_dto(db, reg)

        # Enviar factura por correo cuando pasa a estado 4 (Facturado / Entregado)
        if nuevo_estado == 4 and dto.get("cliente_correo"):
            try:
                email_service.enviar_factura_mantenimiento(
                    destinatario=dto["cliente_correo"],
                    nombre_cliente=dto["nombre_cliente"],
                    cedula_cliente=dto.get("cliente_cedula"),
                    telefono_cliente=dto.get("cliente_telefono"),
                    direccion_cliente=dto.get("cliente_direccion"),
                    id_factura=dto.get("id_factura") or reg.id_registro,
                    moto_desc=f"{dto.get('marca_moto', '')} {dto.get('modelo_moto', '')}".strip(),
                    placa=dto.get("placa", ""),
                    encargado=dto.get("nombre_encargado", ""),
                    tipo_servicio=dto.get("tipo_servicio", "Mantenimiento"),
                    observaciones=dto.get("observaciones"),
                    detalles=dto.get("detalles", []),
                    costo_total=dto.get("costo_total", 0.0),
                )
            except Exception as exc:
                logger.warning(f"No se pudo enviar correo de factura para registro {id_registro}: {exc}")

        return dto

    @staticmethod
    def eliminar(db: Session, id_registro: int) -> None:
        reg = db.query(Registro).filter(Registro.id_registro == id_registro).first()
        if not reg:
            raise EntityNotFoundError("Registro", id_registro)
        db.delete(reg)
        db.commit()


class DiagnosticoService:
    @staticmethod
    def crear(db: Session, payload: Any) -> DiagnosticoMoto:
        moto = db.query(Moto).filter(Moto.id_moto == payload.id_moto).first()
        if not moto:
            raise EntityNotFoundError("Moto", payload.id_moto)

        mecanico = db.query(Usuario).filter(Usuario.id_usuario == payload.id_mecanico).first()

        nuevo = DiagnosticoMoto(
            id_moto=payload.id_moto,
            id_mecanico=payload.id_mecanico,
            fecha=datetime.now(),
            kilometraje_ingreso=payload.kilometraje_ingreso or moto.kilometraje or 0,
            observaciones_generales=payload.observaciones_generales,
        )
        db.add(nuevo)
        db.flush()

        detalles_email = []
        for det in (payload.detalles or []):
            d_obj = DetalleDiagnostico(
                id_diagnostico=nuevo.id_diagnostico,
                parte=det.parte,
                estado=det.estado,
                observacion=det.observacion,
            )
            db.add(d_obj)
            detalles_email.append({
                "parte": det.parte,
                "estado": det.estado,
                "observacion": det.observacion,
            })

        if payload.kilometraje_ingreso and (
            moto.kilometraje is None or payload.kilometraje_ingreso > moto.kilometraje
        ):
            moto.kilometraje = payload.kilometraje_ingreso

        db.commit()
        db.refresh(nuevo)

        # Enviar informe de diagnóstico por correo al dueño de la moto
        try:
            dueno = moto.usuario or db.query(Usuario).filter(Usuario.id_usuario == moto.id_usuario).first()
            if dueno and dueno.correo:
                email_service.enviar_informe_diagnostico(
                    destinatario=dueno.correo,
                    nombre_cliente=dueno.nombre_completo,
                    nombre_mecanico=mecanico.nombre_completo if mecanico else "Mecánico Open Motors",
                    moto_desc=f"{moto.marca} {moto.modelo}",
                    placa=moto.placa,
                    kilometraje=nuevo.kilometraje_ingreso,
                    observaciones_generales=nuevo.observaciones_generales,
                    detalles=detalles_email,
                )
        except Exception as exc:
            logger.warning(f"No se pudo enviar correo de diagnóstico: {exc}")

        return nuevo

    @staticmethod
    def listar_por_moto(db: Session, id_moto: int) -> List[DiagnosticoMoto]:
        return (
            db.query(DiagnosticoMoto)
            .filter(DiagnosticoMoto.id_moto == id_moto)
            .order_by(DiagnosticoMoto.fecha.desc())
            .all()
        )

    @staticmethod
    def listar_por_mecanico(db: Session, id_mecanico: int) -> List[DiagnosticoMoto]:
        return (
            db.query(DiagnosticoMoto)
            .filter(DiagnosticoMoto.id_mecanico == id_mecanico)
            .order_by(DiagnosticoMoto.fecha.desc())
            .all()
        )

    @staticmethod
    def obtener_por_id(db: Session, id_diagnostico: int) -> DiagnosticoMoto:
        diag = (
            db.query(DiagnosticoMoto)
            .filter(DiagnosticoMoto.id_diagnostico == id_diagnostico)
            .first()
        )
        if not diag:
            raise EntityNotFoundError("Diagnóstico", id_diagnostico)
        return diag

