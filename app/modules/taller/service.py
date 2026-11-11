import logging
from datetime import date, datetime
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.exceptions import EntityNotFoundError, BusinessValidationError
from app.modules.taller.models import (
    Tipo,
    Registro,
    DiagnosticoVehiculo,
    DetalleDiagnostico,
    RecepcionVehiculo,
    Presupuesto,
    ItemPresupuesto,
    BitacoraReparacion,
    DanoAdicional,
    ControlCalidad,
    EntregaVehiculo,
)
from app.modules.vehiculos.models import Vehiculo
from app.modules.usuarios.models import Usuario
from app.modules.facturacion.models import Factura, DetalleFactura, NotaDeVenta
from app.modules.mantenimiento.models import MantenimientoRealizado
from app.modules.mantenimiento.service import AlertaMantenimientoService
from app.shared.email_service import email_service

logger = logging.getLogger("openauto.taller")


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
        vehiculo = reg.vehiculo or db.query(Vehiculo).filter(Vehiculo.id_vehiculo == reg.id_vehiculo).first()
        cliente = vehiculo.usuario if vehiculo else None
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
            "id_vehiculo": reg.id_vehiculo,
            "id_cliente": cliente.id_usuario if cliente else 0,
            "nombre_cliente": cliente.nombre_completo if cliente else "Cliente General",
            "cliente_cedula": cliente.cedula if cliente else None,
            "cliente_telefono": cliente.telefono if cliente else None,
            "cliente_correo": cliente.correo if cliente else None,
            "cliente_direccion": cliente.direccion if cliente else None,
            "id_encargado": encargado.id_usuario if encargado else (reg.id_encargado or 0),
            "nombre_encargado": encargado.nombre_completo if encargado else "Por asignar",
            "marca_vehiculo": vehiculo.marca if vehiculo else "",
            "modelo_vehiculo": vehiculo.modelo if vehiculo else "",
            "placa": vehiculo.placa if vehiculo else "",
            "ruta_imagen_vehiculo": vehiculo.ruta_imagen_vehiculo if vehiculo else None,
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
                else (vehiculo.kilometraje if vehiculo and vehiculo.kilometraje is not None else 0)
            ),
            "costo_total": round(costo_final, 2),
            "id_factura": reg.id_factura,
            "detalles": detalles_dto,
            "estado": reg.estado if reg.estado is not None else 1,
        }

    @staticmethod
    def crear(db: Session, payload: Any) -> Dict[str, Any]:
        vehiculo = db.query(Vehiculo).filter(Vehiculo.id_vehiculo == payload.id_vehiculo).first()
        if not vehiculo:
            raise EntityNotFoundError("Vehiculo", payload.id_vehiculo)

        km_reg = payload.kilometraje if payload.kilometraje is not None else (vehiculo.kilometraje or 0)

        nuevo = Registro(
            fecha=RegistroService._parse_date(payload.fecha),
            fecha_entrega_estimada=RegistroService._parse_datetime(payload.fecha_entrega_estimada),
            descripcion=payload.descripcion,
            observaciones=payload.observaciones,
            costo_total=float(payload.costo_total or 0.0),
            id_vehiculo=payload.id_vehiculo,
            id_encargado=payload.id_encargado,
            id_tipo=payload.id_tipo,
            id_factura=payload.id_factura,
            kilometraje=km_reg,
            estado=payload.estado if payload.estado is not None else 1,
        )
        db.add(nuevo)

        # Si el kilometraje de ingreso es mayor al actual de la vehiculo, actualizar la vehiculo
        if km_reg and (vehiculo.kilometraje is None or km_reg > vehiculo.kilometraje):
            vehiculo.kilometraje = km_reg
            db.flush()
            AlertaMantenimientoService.verificar_y_enviar_alertas(db, vehiculo)

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
            .join(Vehiculo, Registro.id_vehiculo == Vehiculo.id_vehiculo)
            .filter(Vehiculo.id_usuario == id_cliente)
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
            .join(Vehiculo, Registro.id_vehiculo == Vehiculo.id_vehiculo)
            .filter(func.upper(Vehiculo.placa).contains(q))
            .order_by(Registro.id_registro.desc())
            .all()
        )
        return [RegistroService.construir_listado_dto(db, r) for r in regs]

    @staticmethod
    def buscar_por_nombre_cliente(db: Session, nombre: str) -> List[Dict[str, Any]]:
        q = (nombre or "").strip().lower()
        regs = (
            db.query(Registro)
            .join(Vehiculo, Registro.id_vehiculo == Vehiculo.id_vehiculo)
            .join(Usuario, Vehiculo.id_usuario == Usuario.id_usuario)
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

        # Regla de Proceso 2.1: Bloquear avance si la recepción no está completa (4 fotos y firma)
        if reg.estado == 1 and nuevo_estado > 1:
            rec = (
                db.query(RecepcionVehiculo)
                .filter(RecepcionVehiculo.id_registro == id_registro)
                .first()
            )
            if not rec:
                rec = (
                    db.query(RecepcionVehiculo)
                    .filter(RecepcionVehiculo.id_vehiculo == reg.id_vehiculo)
                    .order_by(RecepcionVehiculo.fecha_ingreso.desc())
                    .first()
                )
            if rec and not rec.esta_completa:
                faltantes_txt = ", ".join(rec.faltantes)
                raise BusinessValidationError(
                    f"Proceso 2.1: No se permite avanzar la orden a la siguiente fase sin completar la recepción. Faltan: {faltantes_txt}"
                )

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
                    vehiculo_desc=f"{dto.get('marca_vehiculo', '')} {dto.get('modelo_vehiculo', '')}".strip(),
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
    def plantilla_8_sistemas() -> List[Dict[str, Any]]:
        """Retorna la lista de los 8 sistemas del auto y puntos de inspección sugeridos para el mecánico."""
        return [
            {
                "sistema": "MOTOR",
                "nombre": "1. Sistema de Motor",
                "descripcion": "Inspección de fugas, correas/cadenas, soportes, ruidos y componentes internos",
                "partes_sugeridas": [
                    "Aceite de motor y filtro",
                    "Fugas de aceite o refrigerante",
                    "Correa o cadena de distribución",
                    "Banda de accesorios",
                    "Soportes de motor",
                    "Bujías y bobinas de encendido",
                ],
            },
            {
                "sistema": "FRENOS",
                "nombre": "2. Sistema de Frenos",
                "descripcion": "Revisión de fricción, hidráulica y discos/tambores",
                "partes_sugeridas": [
                    "Pastillas de freno delanteras",
                    "Pastillas o zapatas traseras",
                    "Discos y tambores de freno",
                    "Líquido de frenos (nivel y punto de ebullición)",
                    "Mangueras y tuberías de freno",
                    "Freno de estacionamiento (mano)",
                ],
            },
            {
                "sistema": "SUSPENSION",
                "nombre": "3. Sistema de Suspensión",
                "descripcion": "Amortiguación, estabilidad y articulaciones",
                "partes_sugeridas": [
                    "Amortiguadores delanteros",
                    "Amortiguadores traseros",
                    "Bases y rodamientos de amortiguador",
                    "Bujes de horquillas/trapecios",
                    "Rótulas y terminales",
                    "Barras estabilizadoras y enlaces",
                ],
            },
            {
                "sistema": "DIRECCION",
                "nombre": "4. Sistema de Dirección",
                "descripcion": "Mecanismo de guiado y asistencia hidráulica o electro-asistida",
                "partes_sugeridas": [
                    "Caja o cremallera de dirección",
                    "Terminales axiales y de dirección",
                    "Líquido o asistencia de dirección",
                    "Alineación y juego de volante",
                ],
            },
            {
                "sistema": "TRANSMISION",
                "nombre": "5. Sistema de Transmisión",
                "descripcion": "Tracción, caja de cambios y embrague",
                "partes_sugeridas": [
                    "Embrague (disco, plato y collarín)",
                    "Fluido de transmisión (manual o automática)",
                    "Juntas homocinéticas y fuelles/guardapolvos",
                    "Soportes de transmisión",
                ],
            },
            {
                "sistema": "SISTEMA_ELECTRICO",
                "nombre": "6. Sistema Eléctrico",
                "descripcion": "Batería, carga, arranque, cableado y alumbrado",
                "partes_sugeridas": [
                    "Batería (voltaje y estado de salud)",
                    "Alternador y sistema de carga",
                    "Motor de arranque",
                    "Luces altas, bajas, direccionales y freno",
                    "Fusibles y arneses eléctricos",
                ],
            },
            {
                "sistema": "CLIMATIZACION",
                "nombre": "7. Sistema de Climatización (A/C y Calefacción)",
                "descripcion": "Compresor, refrigerante y flujo de aire de cabina",
                "partes_sugeridas": [
                    "Compresor de A/C",
                    "Presión de gas refrigerante",
                    "Filtro de cabina/polen",
                    "Ventilador/blower y calefacción",
                ],
            },
            {
                "sistema": "ESCAPE_EMISIONES",
                "nombre": "8. Sistema de Escape y Emisiones",
                "descripcion": "Gases de combustión, catalizador y sensores",
                "partes_sugeridas": [
                    "Convertidor catalítico",
                    "Sensores de oxígeno (O2)",
                    "Silenciador y tubería de escape",
                    "Fugas de gases o soportes de escape",
                ],
            },
        ]

    @staticmethod
    def crear(db: Session, payload: Any) -> DiagnosticoVehiculo:
        vehiculo = db.query(Vehiculo).filter(Vehiculo.id_vehiculo == payload.id_vehiculo).first()
        if not vehiculo:
            raise EntityNotFoundError("Vehículo", payload.id_vehiculo)

        mecanico = db.query(Usuario).filter(Usuario.id_usuario == payload.id_mecanico).first()

        nuevo = DiagnosticoVehiculo(
            id_vehiculo=payload.id_vehiculo,
            id_mecanico=payload.id_mecanico,
            id_registro=getattr(payload, "id_registro", None),
            id_recepcion=getattr(payload, "id_recepcion", None),
            fecha=datetime.now(),
            kilometraje_ingreso=payload.kilometraje_ingreso or vehiculo.kilometraje or 0,
            escaner_utilizado=getattr(payload, "escaner_utilizado", None),
            codigos_dtc=getattr(payload, "codigos_dtc", None),
            descripcion_escaner=getattr(payload, "descripcion_escaner", None),
            observaciones_generales=payload.observaciones_generales,
            problemas_adicionales=getattr(payload, "problemas_adicionales", None),
            fotos_problemas=getattr(payload, "fotos_problemas", None),
        )
        db.add(nuevo)
        db.flush()

        detalles_email = []
        for det in (payload.detalles or []):
            d_obj = DetalleDiagnostico(
                id_diagnostico=nuevo.id_diagnostico,
                sistema=getattr(det, "sistema", "GENERAL") or "GENERAL",
                parte=det.parte,
                estado=det.estado,
                observacion=det.observacion,
                foto_evidencia=getattr(det, "foto_evidencia", None),
                requiere_repuesto=bool(getattr(det, "requiere_repuesto", False)),
            )
            db.add(d_obj)
            detalles_email.append({
                "sistema": d_obj.sistema,
                "parte": det.parte,
                "estado": det.estado,
                "observacion": det.observacion,
            })

        if payload.kilometraje_ingreso and (
            vehiculo.kilometraje is None or payload.kilometraje_ingreso > vehiculo.kilometraje
        ):
            vehiculo.kilometraje = payload.kilometraje_ingreso

        # Si el diagnóstico está ligado a una orden y la orden está en estado 1 (Recepcionada),
        # avanzarla a estado 2 (En Revisión/Diagnóstico)
        if nuevo.id_registro:
            reg = db.query(Registro).filter(Registro.id_registro == nuevo.id_registro).first()
            if reg and reg.estado == 1:
                reg.estado = 2

        db.commit()
        db.refresh(nuevo)

        # Enviar informe de diagnóstico por correo al dueño del auto
        try:
            dueno = vehiculo.usuario or db.query(Usuario).filter(Usuario.id_usuario == vehiculo.id_usuario).first()
            if dueno and dueno.correo:
                email_service.enviar_informe_diagnostico(
                    destinatario=dueno.correo,
                    nombre_cliente=dueno.nombre_completo,
                    nombre_mecanico=mecanico.nombre_completo if mecanico else "Mecánico Open Auto",
                    vehiculo_desc=f"{vehiculo.marca} {vehiculo.modelo}",
                    placa=vehiculo.placa,
                    kilometraje=nuevo.kilometraje_ingreso,
                    observaciones_generales=nuevo.observaciones_generales,
                    detalles=detalles_email,
                )
        except Exception as exc:
            logger.warning(f"No se pudo enviar correo de diagnóstico: {exc}")

        return nuevo

    @staticmethod
    def listar_por_vehiculo(db: Session, id_vehiculo: int) -> List[DiagnosticoVehiculo]:
        return (
            db.query(DiagnosticoVehiculo)
            .filter(DiagnosticoVehiculo.id_vehiculo == id_vehiculo)
            .order_by(DiagnosticoVehiculo.fecha.desc())
            .all()
        )

    @staticmethod
    def listar_por_mecanico(db: Session, id_mecanico: int) -> List[DiagnosticoVehiculo]:
        return (
            db.query(DiagnosticoVehiculo)
            .filter(DiagnosticoVehiculo.id_mecanico == id_mecanico)
            .order_by(DiagnosticoVehiculo.fecha.desc())
            .all()
        )

    @staticmethod
    def listar_por_registro(db: Session, id_registro: int) -> List[DiagnosticoVehiculo]:
        return (
            db.query(DiagnosticoVehiculo)
            .filter(DiagnosticoVehiculo.id_registro == id_registro)
            .order_by(DiagnosticoVehiculo.fecha.desc())
            .all()
        )

    @staticmethod
    def obtener_por_id(db: Session, id_diagnostico: int) -> DiagnosticoVehiculo:
        diag = (
            db.query(DiagnosticoVehiculo)
            .filter(DiagnosticoVehiculo.id_diagnostico == id_diagnostico)
            .first()
        )
        if not diag:
            raise EntityNotFoundError("Diagnóstico", id_diagnostico)
        return diag


class RecepcionService:
    @staticmethod
    def crear(db: Session, payload: Any) -> Dict[str, Any]:
        vehiculo = db.query(Vehiculo).filter(Vehiculo.id_vehiculo == payload.id_vehiculo).first()
        if not vehiculo:
            raise EntityNotFoundError("Vehículo", payload.id_vehiculo)

        km_ingreso = int(payload.kilometraje or 0)
        if vehiculo.kilometraje is None or km_ingreso > vehiculo.kilometraje:
            vehiculo.kilometraje = km_ingreso
            db.flush()
            AlertaMantenimientoService.verificar_y_enviar_alertas(db, vehiculo)

        id_reg = payload.id_registro
        if not id_reg and getattr(payload, "crear_orden_automatica", True):
            nueva_orden = Registro(
                fecha=date.today(),
                descripcion=f"Ingreso por recepción en taller ({payload.nivel_combustible} tanque)",
                observaciones=payload.danos_previos or payload.observaciones,
                costo_total=0.0,
                id_vehiculo=payload.id_vehiculo,
                id_encargado=payload.id_encargado,
                kilometraje=km_ingreso,
                estado=1,
            )
            db.add(nueva_orden)
            db.flush()
            id_reg = nueva_orden.id_registro

        nueva_rec = RecepcionVehiculo(
            id_vehiculo=payload.id_vehiculo,
            id_encargado=payload.id_encargado,
            id_registro=id_reg,
            fecha_ingreso=datetime.now(),
            kilometraje=km_ingreso,
            nivel_combustible=payload.nivel_combustible or "1/2",
            luces_tablero=payload.luces_tablero,
            danos_previos=payload.danos_previos,
            foto_frente=payload.foto_frente,
            foto_posterior=payload.foto_posterior,
            foto_lateral_izq=payload.foto_lateral_izq,
            foto_lateral_der=payload.foto_lateral_der,
            firma_cliente=payload.firma_cliente,
            observaciones=payload.observaciones,
        )
        db.add(nueva_rec)
        db.commit()
        db.refresh(nueva_rec)
        return nueva_rec.to_dict()

    @staticmethod
    def actualizar(db: Session, id_recepcion: int, payload: Any) -> Dict[str, Any]:
        rec = db.query(RecepcionVehiculo).filter(RecepcionVehiculo.id_recepcion == id_recepcion).first()
        if not rec:
            raise EntityNotFoundError("Recepción", id_recepcion)

        datos = payload if isinstance(payload, dict) else payload.model_dump(exclude_unset=True)
        for key, val in datos.items():
            if hasattr(rec, key) and val is not None:
                setattr(rec, key, val)

        if rec.kilometraje and rec.vehiculo:
            if rec.vehiculo.kilometraje is None or rec.kilometraje > rec.vehiculo.kilometraje:
                rec.vehiculo.kilometraje = rec.kilometraje

        db.commit()
        db.refresh(rec)
        return rec.to_dict()

    @staticmethod
    def obtener_por_id(db: Session, id_recepcion: int) -> Dict[str, Any]:
        rec = db.query(RecepcionVehiculo).filter(RecepcionVehiculo.id_recepcion == id_recepcion).first()
        if not rec:
            raise EntityNotFoundError("Recepción", id_recepcion)
        return rec.to_dict()

    @staticmethod
    def listar_todas(db: Session) -> List[Dict[str, Any]]:
        recs = db.query(RecepcionVehiculo).order_by(RecepcionVehiculo.fecha_ingreso.desc()).all()
        return [r.to_dict() for r in recs]

    @staticmethod
    def listar_por_vehiculo(db: Session, id_vehiculo: int) -> List[Dict[str, Any]]:
        recs = (
            db.query(RecepcionVehiculo)
            .filter(RecepcionVehiculo.id_vehiculo == id_vehiculo)
            .order_by(RecepcionVehiculo.fecha_ingreso.desc())
            .all()
        )
        return [r.to_dict() for r in recs]

    @staticmethod
    def obtener_por_registro(db: Session, id_registro: int) -> Optional[Dict[str, Any]]:
        rec = (
            db.query(RecepcionVehiculo)
            .filter(RecepcionVehiculo.id_registro == id_registro)
            .first()
        )
        return rec.to_dict() if rec else None

    @staticmethod
    def validar_completitud(db: Session, id_recepcion: int) -> Dict[str, Any]:
        rec = db.query(RecepcionVehiculo).filter(RecepcionVehiculo.id_recepcion == id_recepcion).first()
        if not rec:
            raise EntityNotFoundError("Recepción", id_recepcion)
        return {
            "id_recepcion": rec.id_recepcion,
            "completa": rec.esta_completa,
            "faltantes": rec.faltantes,
            "puede_avanzar_fase_b": rec.esta_completa,
        }


class PresupuestoService:
    @staticmethod
    def generar_numero_presupuesto(db: Session) -> str:
        anio = datetime.now().year
        prefijo = f"PRE-{anio}-"
        total = db.query(Presupuesto).filter(Presupuesto.numero_presupuesto.like(f"{prefijo}%")).count()
        return f"{prefijo}{total + 1:04d}"

    @staticmethod
    def crear(db: Session, payload: Any) -> Dict[str, Any]:
        reg = db.query(Registro).filter(Registro.id_registro == payload.id_registro).first()
        if not reg:
            raise EntityNotFoundError("Registro / Orden de trabajo", payload.id_registro)

        vehiculo = db.query(Vehiculo).filter(Vehiculo.id_vehiculo == payload.id_vehiculo).first()
        if not vehiculo:
            raise EntityNotFoundError("Vehículo", payload.id_vehiculo)

        numero = PresupuestoService.generar_numero_presupuesto(db)
        descuento = float(payload.descuento or 0.0)
        costo_diag = float(payload.costo_diagnostico or 0.0)

        subtotal_mo = 0.0
        subtotal_rep = 0.0

        presupuesto = Presupuesto(
            numero_presupuesto=numero,
            id_registro=payload.id_registro,
            id_vehiculo=payload.id_vehiculo,
            id_diagnostico=payload.id_diagnostico,
            id_usuario=payload.id_usuario,
            fecha_emision=datetime.now(),
            estado="BORRADOR",
            descuento=descuento,
            costo_diagnostico=costo_diag,
            observaciones=payload.observaciones,
        )
        db.add(presupuesto)
        db.flush()

        # Procesar items
        items_db = []
        for item in payload.items:
            cant = float(item.cantidad or 1.0)
            pu = float(item.precio_unitario or 0.0)
            subt = round(cant * pu, 2)
            tipo_item = str(item.tipo_item or "REPUESTO").upper()

            if tipo_item == "MANO_OBRA":
                subtotal_mo += subt
            else:
                subtotal_rep += subt

            nuevo_item = ItemPresupuesto(
                id_presupuesto=presupuesto.id_presupuesto,
                tipo_item=tipo_item,
                id_producto=item.id_producto,
                descripcion=item.descripcion.strip(),
                cantidad=cant,
                precio_unitario=pu,
                subtotal=subt,
                estado_aprobacion="PENDIENTE",
                es_adicional=bool(item.es_adicional),
            )
            items_db.append(nuevo_item)
            db.add(nuevo_item)

        presupuesto.subtotal_mano_obra = round(subtotal_mo, 2)
        presupuesto.subtotal_repuestos = round(subtotal_rep, 2)
        presupuesto.total_presupuestado = max(0.0, round(subtotal_mo + subtotal_rep - descuento, 2))
        presupuesto.total_aprobado = 0.0

        db.commit()
        db.refresh(presupuesto)
        return presupuesto.to_dict()

    @staticmethod
    def obtener_por_id(db: Session, id_presupuesto: int) -> Dict[str, Any]:
        p = db.query(Presupuesto).filter(Presupuesto.id_presupuesto == id_presupuesto).first()
        if not p:
            raise EntityNotFoundError("Presupuesto", id_presupuesto)
        return p.to_dict()

    @staticmethod
    def listar_todos(db: Session) -> List[Dict[str, Any]]:
        pres = db.query(Presupuesto).order_by(Presupuesto.id_presupuesto.desc()).all()
        return [p.to_dict() for p in pres]

    @staticmethod
    def listar_por_registro(db: Session, id_registro: int) -> List[Dict[str, Any]]:
        pres = (
            db.query(Presupuesto)
            .filter(Presupuesto.id_registro == id_registro)
            .order_by(Presupuesto.id_presupuesto.desc())
            .all()
        )
        return [p.to_dict() for p in pres]

    @staticmethod
    def listar_por_vehiculo(db: Session, id_vehiculo: int) -> List[Dict[str, Any]]:
        pres = (
            db.query(Presupuesto)
            .filter(Presupuesto.id_vehiculo == id_vehiculo)
            .order_by(Presupuesto.id_presupuesto.desc())
            .all()
        )
        return [p.to_dict() for p in pres]

    @staticmethod
    def enviar_al_cliente(db: Session, id_presupuesto: int) -> Dict[str, Any]:
        p = db.query(Presupuesto).filter(Presupuesto.id_presupuesto == id_presupuesto).first()
        if not p:
            raise EntityNotFoundError("Presupuesto", id_presupuesto)
        if p.estado not in ("BORRADOR", "ENVIADO"):
            raise BusinessValidationError(f"No se puede enviar un presupuesto que ya está en estado {p.estado}.")

        p.estado = "ENVIADO"
        db.commit()
        db.refresh(p)
        return p.to_dict()

    @staticmethod
    def registrar_decision_cliente(db: Session, id_presupuesto: int, payload: Any) -> Dict[str, Any]:
        """
        Procesa la respuesta del cliente según el diagrama de flujo (Proceso 5):
        - APROBADO_TOTAL: Se aprueba la totalidad de repuestos y mano de obra -> Avanza a Proceso 6.
        - APROBADO_PARCIAL (Proceso 5.1): Ajuste de presupuesto, se aprueban ciertos ítems y otros se postergan.
        - RECHAZADO (Proceso 5.2): Se rechaza el presupuesto. Si aplica cobrar diagnóstico, se fija dicho costo y se entrega sin reparación.
        """
        p = db.query(Presupuesto).filter(Presupuesto.id_presupuesto == id_presupuesto).first()
        if not p:
            raise EntityNotFoundError("Presupuesto", id_presupuesto)

        decision = (payload.decision or "").strip().upper()
        if decision not in ("APROBADO_TOTAL", "APROBADO_PARCIAL", "RECHAZADO"):
            raise BusinessValidationError(
                f"Decisión inválida: '{decision}'. Debe ser 'APROBADO_TOTAL', 'APROBADO_PARCIAL' o 'RECHAZADO'."
            )

        reg = db.query(Registro).filter(Registro.id_registro == p.id_registro).first()
        ahora = datetime.now()
        p.fecha_respuesta = ahora
        p.motivo_rechazo_ajuste = payload.motivo

        if decision == "APROBADO_TOTAL":
            p.estado = "APROBADO_TOTAL"
            for item in p.items:
                item.estado_aprobacion = "APROBADO"
            p.total_aprobado = p.total_presupuestado
            if reg:
                reg.costo_total = p.total_aprobado
                # Si estaba en diagnóstico/recepción, pasa a en proceso / reparación (estado 2)
                if reg.estado == 1:
                    reg.estado = 2

        elif decision == "APROBADO_PARCIAL":
            p.estado = "APROBADO_PARCIAL"
            ids_aprobados = set(payload.items_aprobados_ids or [])
            if not ids_aprobados:
                raise BusinessValidationError("Para aprobación parcial (Proceso 5.1) debe especificar al menos un ítem aprobado.")

            suma_aprobada = 0.0
            for item in p.items:
                if item.id_item in ids_aprobados:
                    item.estado_aprobacion = "APROBADO"
                    suma_aprobada += float(item.subtotal or 0.0)
                else:
                    item.estado_aprobacion = "POSTERGADO"

            # Aplicar descuento si no excede el subtotal aprobado
            total_neto = max(0.0, round(suma_aprobada - float(p.descuento or 0.0), 2))
            p.total_aprobado = total_neto
            if reg:
                reg.costo_total = p.total_aprobado
                if reg.estado == 1:
                    reg.estado = 2

        elif decision == "RECHAZADO":
            p.estado = "RECHAZADO"
            p.cobrar_solo_diagnostico = bool(payload.cobrar_solo_diagnostico)
            for item in p.items:
                item.estado_aprobacion = "RECHAZADO"

            if p.cobrar_solo_diagnostico:
                p.total_aprobado = round(float(p.costo_diagnostico or 0.0), 2)
            else:
                p.total_aprobado = 0.0

            if reg:
                reg.costo_total = p.total_aprobado
                # Proceso 5.2: Estado 8 = Entregado sin reparación / Presupuesto rechazado
                reg.estado = 8
                reg.fecha_completado = ahora
                reg.fecha_entregado = ahora

        db.commit()
        db.refresh(p)
        if reg:
            db.refresh(reg)
        return p.to_dict()


class ReparacionService:
    """
    Control de la Fase C: Reparar y revisar el vehículo (Procesos 7, 7.1, 8, 8.1 y 9).
    """

    @staticmethod
    def registrar_bitacora(db: Session, payload: Any) -> Dict[str, Any]:
        """
        Proceso 7: Anotar horas trabajadas, avance técnico y fotos de la reparación.
        """
        reg = db.query(Registro).filter(Registro.id_registro == payload.id_registro).first()
        if not reg:
            raise EntityNotFoundError("Registro de taller", payload.id_registro)

        # Si no se pasó mecánico, hereda el encargado de la orden
        id_mec = payload.id_mecanico or reg.id_encargado

        bitacora = BitacoraReparacion(
            id_registro=payload.id_registro,
            id_mecanico=id_mec,
            horas_trabajadas=float(payload.horas_trabajadas or 0.0),
            descripcion_trabajo=payload.descripcion_trabajo.strip(),
            fotos_evidencia=payload.fotos_evidencia,
            repuestos_instalados=payload.repuestos_instalados,
            fecha=datetime.now(),
        )
        db.add(bitacora)

        # Si estaba en recepción (1), pasa a en reparación (2)
        if reg.estado == 1:
            reg.estado = 2

        db.commit()
        db.refresh(bitacora)
        return bitacora.to_dict()

    @staticmethod
    def listar_bitacoras_por_registro(db: Session, id_registro: int) -> List[Dict[str, Any]]:
        bits = (
            db.query(BitacoraReparacion)
            .filter(BitacoraReparacion.id_registro == id_registro)
            .order_by(BitacoraReparacion.fecha.desc())
            .all()
        )
        return [b.to_dict() for b in bits]

    @staticmethod
    def reportar_dano_adicional(db: Session, payload: Any) -> Dict[str, Any]:
        """
        Proceso 7.1: Notificar hallazgo de daño adicional no contemplado inicialmente.
        Requiere aprobación del cliente antes de continuar el trabajo adicional.
        """
        reg = db.query(Registro).filter(Registro.id_registro == payload.id_registro).first()
        if not reg:
            raise EntityNotFoundError("Registro de taller", payload.id_registro)

        id_mec = payload.id_mecanico or reg.id_encargado

        dano = DanoAdicional(
            id_registro=payload.id_registro,
            id_mecanico=id_mec,
            descripcion=payload.descripcion.strip(),
            fotos_evidencia=payload.fotos_evidencia,
            repuesto_sugerido=payload.repuesto_sugerido,
            id_producto=payload.id_producto,
            costo_estimado=float(payload.costo_estimado or 0.0),
            estado="PENDIENTE",
            fecha_deteccion=datetime.now(),
        )
        db.add(dano)
        db.commit()
        db.refresh(dano)
        return dano.to_dict()

    @staticmethod
    def responder_dano_adicional(db: Session, id_dano: int, payload: Any) -> Dict[str, Any]:
        """
        Proceso 7.1: Registrar respuesta del cliente sobre el daño adicional.
        Si es aprobado, se suma el costo estimado a la orden de trabajo.
        """
        dano = db.query(DanoAdicional).filter(DanoAdicional.id_dano == id_dano).first()
        if not dano:
            raise EntityNotFoundError("Daño adicional", id_dano)

        aprobado = bool(payload.aprobado)
        dano.estado = "APROBADO" if aprobado else "RECHAZADO"
        dano.fecha_respuesta = datetime.now()
        dano.observaciones_cliente = payload.observaciones_cliente

        reg = db.query(Registro).filter(Registro.id_registro == dano.id_registro).first()
        if reg and aprobado and dano.costo_estimado > 0:
            reg.costo_total = round(float(reg.costo_total or 0.0) + dano.costo_estimado, 2)

        db.commit()
        db.refresh(dano)
        if reg:
            db.refresh(reg)

        return {
            "exito": True,
            "mensaje": f"Daño adicional {'APROBADO' if aprobado else 'RECHAZADO'} por el cliente.",
            "dano": dano.to_dict(),
            "costo_total_actualizado": reg.costo_total if reg else None,
        }

    @staticmethod
    def listar_danos_por_registro(db: Session, id_registro: int) -> List[Dict[str, Any]]:
        danos = (
            db.query(DanoAdicional)
            .filter(DanoAdicional.id_registro == id_registro)
            .order_by(DanoAdicional.fecha_deteccion.desc())
            .all()
        )
        return [d.to_dict() for d in danos]

    @staticmethod
    def registrar_control_calidad(db: Session, payload: Any) -> Dict[str, Any]:
        """
        Proceso 8 y 8.1: Revisión post-reparación y escaneo OBD2.
        - Si pasa (Proceso 9): Se marca orden lista para entrega (estado 3) y fecha de completado.
        - Si no pasa (Proceso 8.1): Se devuelve al mecánico para corregir el problema SIN cobrar extra (estado 2).
        """
        reg = db.query(Registro).filter(Registro.id_registro == payload.id_registro).first()
        if not reg:
            raise EntityNotFoundError("Registro de taller", payload.id_registro)

        paso = bool(payload.paso_inspeccion)
        accion = "APROBADO_LISTO" if paso else "DEVUELTO_A_MECANICO"

        control = ControlCalidad(
            id_registro=payload.id_registro,
            id_revisor=payload.id_revisor or reg.id_encargado,
            fecha=datetime.now(),
            paso_inspeccion=paso,
            escaner_utilizado=payload.escaner_utilizado,
            codigos_dtc_detectados=payload.codigos_dtc_detectados or "Sin códigos de falla",
            observaciones=payload.observaciones,
            motivo_devolucion=payload.motivo_devolucion if not paso else None,
            accion_tomada=accion,
        )
        db.add(control)

        ahora = datetime.now()
        if paso:
            # Proceso 9: Vehículo listo para entrega (Estado 3)
            reg.estado = 3
            if not reg.fecha_completado:
                reg.fecha_completado = ahora
            mensaje = "El vehículo superó exitosamente el control de calidad y escaneo final. Marcado como LISTO PARA ENTREGA."
        else:
            # Proceso 8.1: Devolver al mecánico sin costo extra (Garantía interna de taller)
            reg.estado = 2  # Regresa a en proceso / reproceso
            motivo = payload.motivo_devolucion or "No superó la prueba de calidad"
            if reg.observaciones:
                reg.observaciones = f"{reg.observaciones} | [Control Calidad - Reproceso sin costo]: {motivo}"
            else:
                reg.observaciones = f"[Control Calidad - Reproceso sin costo]: {motivo}"
            mensaje = f"Control de calidad no superado. Vehículo devuelto al mecánico responsable para corrección sin costo extra: {motivo}"

        db.commit()
        db.refresh(control)
        db.refresh(reg)

        return {
            "exito": True,
            "mensaje": mensaje,
            "control": control.to_dict(),
            "estado_orden": reg.estado,
            "registro": reg.to_raw_dict(),
        }

    @staticmethod
    def listar_controles_por_registro(db: Session, id_registro: int) -> List[Dict[str, Any]]:
        controles = (
            db.query(ControlCalidad)
            .filter(ControlCalidad.id_registro == id_registro)
            .order_by(ControlCalidad.fecha.desc())
            .all()
        )
        return [c.to_dict() for c in controles]


class EntregaService:
    """
    Gestión de la Entrega Física del Vehículo al cliente (Proceso 15).
    Verifica pago previo, registra firma de conformidad y reinicia ciclos de desgaste de repuestos.
    """

    @staticmethod
    def entregar_vehiculo(db: Session, payload: Any) -> Dict[str, Any]:
        reg = db.query(Registro).filter(Registro.id_registro == payload.id_registro).first()
        if not reg:
            raise EntityNotFoundError("Registro / Orden de taller", payload.id_registro)

        # Regla estricta Proceso 11.1 / Proceso 15: La orden debe estar PAGADA
        # Se verifica si está en estado 7 (PAGADO) o si tiene Nota de Venta pagada
        nota = (
            db.query(NotaDeVenta)
            .filter(NotaDeVenta.id_registro == reg.id_registro)
            .order_by(NotaDeVenta.id_nota_venta.desc())
            .first()
        )
        esta_pagada = (reg.estado == 7) or (nota and nota.estado_pago == "PAGADO")
        if not esta_pagada and reg.costo_total > 0:
            raise BusinessValidationError(
                "Proceso 11.1 / Proceso 15: No se puede entregar el vehículo al cliente. "
                "La orden no ha sido pagada. Debe confirmarse el pago y emitirse la Nota de Venta primero."
            )

        vehiculo = db.query(Vehiculo).filter(Vehiculo.id_vehiculo == reg.id_vehiculo).first()
        km_salida = int(payload.kilometraje_salida or reg.kilometraje or (vehiculo.kilometraje if vehiculo else 0) or 0)

        # Actualizar kilometraje del vehículo si aumentó
        if vehiculo and km_salida > (vehiculo.kilometraje or 0):
            vehiculo.kilometraje = km_salida

        ahora = datetime.now()
        reg.estado = 4  # Estado 4: Entregado / Completado
        reg.fecha_entregado = ahora

        entrega = EntregaVehiculo(
            id_registro=reg.id_registro,
            id_vehiculo=reg.id_vehiculo,
            id_usuario_entrega=payload.id_usuario_entrega,
            fecha_entrega=ahora,
            kilometraje_salida=km_salida,
            firma_cliente_entrega=payload.firma_cliente_entrega,
            persona_recibe=payload.persona_recibe.strip(),
            cedula_recibe=payload.cedula_recibe,
            observaciones=payload.observaciones,
        )
        db.add(entrega)

        # Reiniciar ciclo de desgaste para los repuestos instalados (Proceso 15)
        presupuesto = (
            db.query(Presupuesto)
            .filter(Presupuesto.id_registro == reg.id_registro)
            .order_by(Presupuesto.id_presupuesto.desc())
            .first()
        )
        if presupuesto and presupuesto.items:
            for item in presupuesto.items:
                if str(item.estado_aprobacion).upper() == "APROBADO":
                    desc_pieza = item.descripcion.strip().upper()
                    mantenimiento = (
                        db.query(MantenimientoRealizado)
                        .filter(
                            MantenimientoRealizado.id_vehiculo == reg.id_vehiculo,
                            MantenimientoRealizado.tipo == desc_pieza,
                        )
                        .first()
                    )
                    if mantenimiento:
                        mantenimiento.km_servicio = km_salida
                        mantenimiento.fecha = ahora
                    else:
                        db.add(
                            MantenimientoRealizado(
                                id_vehiculo=reg.id_vehiculo,
                                tipo=desc_pieza,
                                km_servicio=km_salida,
                                fecha=ahora,
                            )
                        )

        db.commit()
        db.refresh(entrega)
        db.refresh(reg)
        if vehiculo:
            db.refresh(vehiculo)

        return {
            "exito": True,
            "mensaje": f"Vehículo placa {vehiculo.placa if vehiculo else ''} entregado exitosamente a {entrega.persona_recibe}.",
            "entrega": entrega.to_dict(),
            "estado_orden": reg.estado,
            "registro": reg.to_raw_dict(),
        }

    @staticmethod
    def obtener_entrega_por_registro(db: Session, id_registro: int) -> Optional[Dict[str, Any]]:
        ent = db.query(EntregaVehiculo).filter(EntregaVehiculo.id_registro == id_registro).first()
        return ent.to_dict() if ent else None

    @staticmethod
    def listar_entregas(db: Session) -> List[Dict[str, Any]]:
        ents = db.query(EntregaVehiculo).order_by(EntregaVehiculo.fecha_entrega.desc()).all()
        return [e.to_dict() for e in ents]




