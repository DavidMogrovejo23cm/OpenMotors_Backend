from app.core.access_scope import scoped_query
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

from app.modules.taller.pagos import PagoOrden
from app.modules.taller.estados import EstadoOrden, EstadoPago, aplicar_estado

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
        vehiculo = reg.vehiculo or scoped_query(db, Vehiculo).filter(Vehiculo.id_vehiculo == reg.id_vehiculo).first()
        cliente = vehiculo.usuario if vehiculo else None
        encargado = reg.encargado or (
            scoped_query(db, Usuario).filter(Usuario.id_usuario == reg.id_encargado).first()
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
            factura = reg.factura or scoped_query(db, Factura).filter(Factura.id_factura == reg.id_factura).first()
            if factura and factura.costo_total is not None and factura.costo_total > 0:
                costo_final = float(factura.costo_total)
            dets = (
                scoped_query(db, DetalleFactura)
                .filter(DetalleFactura.id_factura == reg.id_factura)
                .order_by(DetalleFactura.id_detalle.asc())
                .all()
            )
            detalles_dto = [d.to_dict() for d in dets]

        nota = scoped_query(db, NotaDeVenta).filter(NotaDeVenta.id_registro == reg.id_registro).order_by(NotaDeVenta.id_nota_venta.desc()).first()
        if nota:
            costo_final = float(nota.total)
            if not reg.id_factura:
                detalles_dto = [{"idDetalleFactura": item.id_item, "id_producto": item.id_producto, "idProducto": item.id_producto, "descripcion": item.descripcion, "cantidad": item.cantidad, "precioUnitario": item.precio_unitario, "subtotal": item.subtotal} for item in nota.items]
        pagos = scoped_query(db, PagoOrden).filter(PagoOrden.id_registro == reg.id_registro).order_by(PagoOrden.id_pago).all()
        return {
            "pagos": [{"id_pago": p.id_pago, "monto": float(p.monto), "metodo": p.metodo, "fecha": p.fecha.isoformat()} for p in pagos],
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
            "horas_estimadas": round(float(reg.horas_estimadas), 2) if reg.horas_estimadas is not None else None,
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
            "estado": reg.estado if reg.estado is not None else 0,
            "estado_pago": reg.estado_pago,
            "monto_pagado": round(float(reg.monto_pagado or 0), 2),
            "saldo_pendiente": round(max(0, costo_final - float(reg.monto_pagado or 0)), 2),
            "revision_estado": reg.revision_estado,
            "estado_legacy": reg.estado_legacy,
            "flujo_integrado": reg.flujo_integrado,
        }

    @staticmethod
    def _parse_estimada_estricta(val: Optional[str], fecha_ingreso: date) -> Optional[datetime]:
        if val is None or not str(val).strip():
            return None
        try:
            dt = datetime.fromisoformat(str(val).strip().replace("Z", "+00:00"))
        except ValueError:
            raise BusinessValidationError("La fecha estimada de entrega tiene un formato inválido")
        if dt.date() < fecha_ingreso:
            raise BusinessValidationError("La fecha estimada de entrega no puede ser anterior a la fecha de ingreso")
        return dt.replace(tzinfo=None)

    @staticmethod
    def crear(db: Session, payload: Any) -> Dict[str, Any]:
        vehiculo = scoped_query(db, Vehiculo).filter(Vehiculo.id_vehiculo == payload.id_vehiculo).first()
        if not vehiculo:
            raise EntityNotFoundError("Vehiculo", payload.id_vehiculo)

        fecha_ingreso = RegistroService._parse_date(payload.fecha)
        fecha_estimada = RegistroService._parse_estimada_estricta(payload.fecha_entrega_estimada, fecha_ingreso)
        horas_est = getattr(payload, "horas_estimadas", None)
        if horas_est is not None and float(horas_est) < 0:
            raise BusinessValidationError("Las horas estimadas no pueden ser negativas")

        km_reg = payload.kilometraje if payload.kilometraje is not None else (vehiculo.kilometraje or 0)

        nuevo = Registro(
            fecha=fecha_ingreso,
            fecha_entrega_estimada=fecha_estimada,
            horas_estimadas=float(horas_est) if horas_est is not None else None,
            descripcion=payload.descripcion,
            observaciones=payload.observaciones,
            costo_total=float(payload.costo_total or 0.0),
            id_vehiculo=payload.id_vehiculo,
            id_encargado=payload.id_encargado,
            id_tipo=payload.id_tipo,
            id_factura=payload.id_factura,
            kilometraje=km_reg,
            estado=EstadoOrden.PENDIENTE,
            flujo_integrado=getattr(payload, "flujo_integrado", False),
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
        regs = scoped_query(db, Registro).order_by(Registro.id_registro.desc()).all()
        return [RegistroService.construir_listado_dto(db, r) for r in regs]

    @staticmethod
    def obtener_por_id_dto(db: Session, id_registro: int) -> Dict[str, Any]:
        reg = scoped_query(db, Registro).filter(Registro.id_registro == id_registro).first()
        if not reg:
            raise EntityNotFoundError("Registro", id_registro)
        return RegistroService.construir_listado_dto(db, reg)

    @staticmethod
    def listar_por_cliente(db: Session, id_cliente: int) -> List[Dict[str, Any]]:
        regs = (
            scoped_query(db, Registro)
            .join(Vehiculo, Registro.id_vehiculo == Vehiculo.id_vehiculo)
            .filter(Vehiculo.id_usuario == id_cliente)
            .order_by(Registro.id_registro.desc())
            .all()
        )
        return [RegistroService.construir_listado_dto(db, r) for r in regs]

    @staticmethod
    def listar_por_encargado(db: Session, id_encargado: int) -> List[Dict[str, Any]]:
        regs = (
            scoped_query(db, Registro)
            .filter(Registro.id_encargado == id_encargado)
            .order_by(Registro.id_registro.desc())
            .all()
        )
        return [RegistroService.construir_listado_dto(db, r) for r in regs]

    @staticmethod
    def buscar_por_placa(db: Session, placa: str) -> List[Dict[str, Any]]:
        q = (placa or "").strip().upper()
        regs = (
            scoped_query(db, Registro)
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
            scoped_query(db, Registro)
            .join(Vehiculo, Registro.id_vehiculo == Vehiculo.id_vehiculo)
            .join(Usuario, Vehiculo.id_usuario == Usuario.id_usuario)
            .filter(func.lower(Usuario.nombre_completo).contains(q))
            .order_by(Registro.id_registro.desc())
            .all()
        )
        return [RegistroService.construir_listado_dto(db, r) for r in regs]

    @staticmethod
    def asociar_factura(db: Session, id_registro: int, id_factura: int) -> Dict[str, Any]:
        reg = scoped_query(db, Registro).filter(Registro.id_registro == id_registro).first()
        if not reg:
            raise EntityNotFoundError("Registro", id_registro)
        factura = scoped_query(db, Factura).filter(Factura.id_factura == id_factura).first()
        if not factura:
            raise EntityNotFoundError("Factura", id_factura)

        if float(reg.monto_pagado or 0) > 0:
            raise BusinessValidationError("No se puede reemplazar el comprobante de una orden con pagos")
        if db.query(Registro).filter(Registro.id_factura == id_factura, Registro.id_registro != id_registro).first():
            raise BusinessValidationError("El comprobante ya pertenece a otra orden")
        from app.modules.inventario.movimientos import OperacionInventario
        from app.modules.inventario.models import MovimientoKardex
        for detail in db.query(DetalleFactura).filter_by(id_factura=id_factura).all():
            operation = db.get(OperacionInventario, f"detalle:{detail.id_detalle}")
            if operation and operation.resultado.get("id_movimiento"):
                mov = db.get(MovimientoKardex, operation.resultado["id_movimiento"])
                if mov: mov.id_registro = id_registro
        reg.id_factura = id_factura
        if factura.costo_total and factura.costo_total > 0:
            reg.costo_total = factura.costo_total
        db.commit()
        db.refresh(reg)
        return RegistroService.construir_listado_dto(db, reg)

    @staticmethod
    def cambiar_estado(db: Session, id_registro: int, nuevo_estado: int) -> Dict[str, Any]:
        reg = scoped_query(db, Registro).filter(Registro.id_registro == id_registro).first()
        if not reg:
            raise EntityNotFoundError("Registro", id_registro)

        # Regla de Proceso 2.1: Bloquear avance si la recepción no está completa (4 fotos y firma)
        if reg.estado == EstadoOrden.PENDIENTE and nuevo_estado != EstadoOrden.PENDIENTE:
            rec = (
                scoped_query(db, RecepcionVehiculo)
                .filter(RecepcionVehiculo.id_registro == id_registro)
                .first()
            )
            if not rec:
                rec = (
                    scoped_query(db, RecepcionVehiculo)
                    .filter(RecepcionVehiculo.id_vehiculo == reg.id_vehiculo)
                    .order_by(RecepcionVehiculo.fecha_ingreso.desc())
                    .first()
                )
            if rec and not rec.esta_completa:
                faltantes_txt = ", ".join(rec.faltantes)
                raise BusinessValidationError(
                    f"Proceso 2.1: No se permite avanzar la orden a la siguiente fase sin completar la recepción. Faltan: {faltantes_txt}"
                )

        if reg.flujo_integrado:
            from app.modules.taller.flujo import validar_etapa
            if nuevo_estado == 3 and reg.estado != 3:
                raise BusinessValidationError("Registre la entrega con la firma y datos de quien recibe")
            if nuevo_estado == 1: validar_etapa(db, reg, "diagnostico")
            if nuevo_estado == 2: validar_etapa(db, reg, "cobro")
        aplicar_estado(reg, nuevo_estado)

        db.commit()
        db.refresh(reg)
        dto = RegistroService.construir_listado_dto(db, reg)

        # Enviar el comprobante al entregar, sin registrar un cobro adicional.
        if nuevo_estado == EstadoOrden.ENTREGADA and dto.get("cliente_correo"):
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
        reg = scoped_query(db, Registro).filter(Registro.id_registro == id_registro).first()
        if not reg:
            raise EntityNotFoundError("Registro", id_registro)
        if float(reg.monto_pagado or 0) > 0:
            raise BusinessValidationError("No se puede eliminar una orden con pagos registrados")
        db.delete(reg)
        db.commit()

    @staticmethod
    def actualizar_estimacion(db: Session, id_registro: int, payload: Any, actor_id: int) -> Dict[str, Any]:
        """RF-15 / HU-17: Actualiza la fecha y horas estimadas de una orden abierta."""
        reg = scoped_query(db, Registro).filter(Registro.id_registro == id_registro).first()
        if not reg:
            raise EntityNotFoundError("Registro", id_registro)
        if reg.estado == EstadoOrden.ENTREGADA:
            raise BusinessValidationError("No se puede modificar la estimación de una orden ya entregada")

        fecha_ingreso = reg.fecha or date.today()
        if payload.fecha_entrega_estimada is not None:
            reg.fecha_entrega_estimada = RegistroService._parse_estimada_estricta(
                payload.fecha_entrega_estimada, fecha_ingreso
            )
        if payload.horas_estimadas is not None:
            if float(payload.horas_estimadas) < 0:
                raise BusinessValidationError("Las horas estimadas no pueden ser negativas")
            reg.horas_estimadas = round(float(payload.horas_estimadas), 2)

        from app.modules.sistema.auditoria import registrar_auditoria
        registrar_auditoria(
            db,
            actor_id,
            "ORDEN_ESTIMACION_ACTUALIZADA",
            "Registro",
            reg.id_registro,
            f"Estimación actualizada para orden #{reg.id_registro}: "
            f"entrega={reg.fecha_entrega_estimada.isoformat() if reg.fecha_entrega_estimada else 'N/A'}, "
            f"horas={reg.horas_estimadas}",
        )
        db.commit()
        db.refresh(reg)
        return RegistroService.construir_listado_dto(db, reg)

    @staticmethod
    def reporte_trabajos(
        db: Session,
        fecha_inicio: Optional[str] = None,
        fecha_fin: Optional[str] = None,
        estado: Optional[int] = None,
        id_encargado: Optional[int] = None,
        id_tipo: Optional[int] = None,
    ) -> Dict[str, Any]:
        """RF-54 / HU-65: Genera reporte consolidado de trabajos por período y filtros."""
        fi: Optional[date] = None
        ff: Optional[date] = None
        if fecha_inicio:
            try:
                fi = date.fromisoformat(fecha_inicio[:10])
            except ValueError:
                raise BusinessValidationError("La fecha_inicio debe tener formato AAAA-MM-DD")
        if fecha_fin:
            try:
                ff = date.fromisoformat(fecha_fin[:10])
            except ValueError:
                raise BusinessValidationError("La fecha_fin debe tener formato AAAA-MM-DD")
        if fi and ff and fi > ff:
            raise BusinessValidationError("La fecha de inicio no puede ser mayor que la fecha final")

        query = scoped_query(db, Registro)
        if fi:
            query = query.filter(Registro.fecha >= fi)
        if ff:
            query = query.filter(Registro.fecha <= ff)
        if estado is not None:
            if estado not in (0, 1, 2, 3):
                raise BusinessValidationError("Estado de trabajo inválido")
            query = query.filter(Registro.estado == estado)
        if id_encargado is not None:
            query = query.filter(Registro.id_encargado == id_encargado)
        if id_tipo is not None:
            query = query.filter(Registro.id_tipo == id_tipo)

        regs = query.order_by(Registro.fecha.desc(), Registro.id_registro.desc()).all()
        conteo = {0: 0, 1: 0, 2: 0, 3: 0}
        total_facturado = 0.0
        total_cobrado = 0.0
        total_pendiente = 0.0
        horas_totales = 0.0
        items = []

        for reg in regs:
            dto = RegistroService.construir_listado_dto(db, reg)
            est = int(dto.get("estado") or 0)
            conteo[est] = conteo.get(est, 0) + 1
            costo = float(dto.get("costo_total") or 0.0)
            pagado = float(dto.get("monto_pagado") or 0.0)
            saldo = float(dto.get("saldo_pendiente") or 0.0)
            horas_orden = sum(
                float(b.horas_trabajadas or 0.0)
                for b in db.query(BitacoraReparacion).filter(BitacoraReparacion.id_registro == reg.id_registro).all()
            )
            total_facturado += costo
            total_cobrado += pagado
            total_pendiente += saldo
            horas_totales += horas_orden
            items.append({
                **dto,
                "horas_trabajadas": round(horas_orden, 2),
            })

        return {
            "filtros": {
                "fecha_inicio": fi.isoformat() if fi else None,
                "fecha_fin": ff.isoformat() if ff else None,
                "estado": estado,
                "id_encargado": id_encargado,
                "id_tipo": id_tipo,
            },
            "resumen": {
                "total_ordenes": len(items),
                "total_facturado": round(total_facturado, 2),
                "total_cobrado": round(total_cobrado, 2),
                "total_pendiente": round(total_pendiente, 2),
                "horas_trabajadas_totales": round(horas_totales, 2),
                "conteo_por_estado": {
                    "pendiente": conteo[0],
                    "en_proceso": conteo[1],
                    "finalizada": conteo[2],
                    "entregada": conteo[3],
                },
            },
            "items": items,
        }


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
        vehiculo = scoped_query(db, Vehiculo).filter(Vehiculo.id_vehiculo == payload.id_vehiculo).first()
        if not vehiculo:
            raise EntityNotFoundError("Vehículo", payload.id_vehiculo)

        mecanico = scoped_query(db, Usuario).filter(Usuario.id_usuario == payload.id_mecanico).first()
        if not mecanico:
            raise EntityNotFoundError("Responsable del diagnóstico", payload.id_mecanico)
        if not any(link.estado == 1 and link.rol and link.rol.nombre in ("ADMIN", "MECANICO") for link in mecanico.roles):
            raise BusinessValidationError("El responsable debe ser un mecánico o administrador activo")
        if not payload.id_registro and not payload.id_recepcion:
            raise BusinessValidationError("Seleccione la orden o recepción correspondiente al diagnóstico")
        rec = None
        if payload.id_recepcion:
            rec = scoped_query(db, RecepcionVehiculo).filter_by(id_recepcion=payload.id_recepcion).first()
            if not rec or rec.id_vehiculo != payload.id_vehiculo:
                raise BusinessValidationError("La recepción no corresponde al vehículo del diagnóstico")
            if payload.id_registro and rec.id_registro != payload.id_registro:
                raise BusinessValidationError("La recepción no corresponde a la orden del diagnóstico")
            payload.id_registro = rec.id_registro
        reg = scoped_query(db, Registro).filter_by(id_registro=payload.id_registro).first()
        if not reg or reg.id_vehiculo != payload.id_vehiculo:
            raise BusinessValidationError("El diagnóstico debe corresponder a la orden y vehículo seleccionados")
        if reg.estado in (EstadoOrden.FINALIZADA, EstadoOrden.ENTREGADA):
            raise BusinessValidationError("No se puede diagnosticar una orden finalizada o entregada")
        if rec is None:
            rec = scoped_query(db, RecepcionVehiculo).filter_by(id_registro=reg.id_registro).order_by(RecepcionVehiculo.id_recepcion.desc()).first()
        if not rec or not rec.esta_completa:
            raise BusinessValidationError("Complete la recepción con las cuatro fotos y la firma del cliente")
        payload.id_recepcion = rec.id_recepcion
        if payload.kilometraje_ingreso is not None and payload.kilometraje_ingreso < rec.kilometraje:
            raise BusinessValidationError("El kilometraje del diagnóstico no puede ser menor al de recepción")
        if not any(str(text or "").strip() for text in (
            payload.observaciones_generales, payload.problemas_adicionales,
            payload.descripcion_escaner, *(d.observacion for d in payload.detalles),
        )):
            raise BusinessValidationError("Describa los hallazgos del diagnóstico")
        if payload.origen_diagnostico in ("ESCANER", "AMBOS") and not any(
            str(text or "").strip() for text in (payload.codigos_dtc, payload.descripcion_escaner)
        ):
            raise BusinessValidationError("Registre los códigos o resultados observados en el escáner")
        nuevo = DiagnosticoVehiculo(
            id_vehiculo=payload.id_vehiculo,
            id_mecanico=payload.id_mecanico,
            origen_diagnostico=payload.origen_diagnostico,
            id_registro=getattr(payload, "id_registro", None),
            id_recepcion=getattr(payload, "id_recepcion", None),
            fecha=datetime.now(),
            kilometraje_ingreso=payload.kilometraje_ingreso if payload.kilometraje_ingreso is not None else rec.kilometraje,
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

        # Iniciar el trabajo cuando el diagnóstico se vincula a una orden pendiente.
        if nuevo.id_registro:
            reg = scoped_query(db, Registro).filter(Registro.id_registro == nuevo.id_registro).first()
            if reg and reg.estado == EstadoOrden.PENDIENTE:
                aplicar_estado(reg, EstadoOrden.EN_PROCESO)

        db.commit()
        db.refresh(nuevo)

        # Enviar informe de diagnóstico por correo al dueño del auto
        try:
            dueno = vehiculo.usuario or scoped_query(db, Usuario).filter(Usuario.id_usuario == vehiculo.id_usuario).first()
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
            scoped_query(db, DiagnosticoVehiculo)
            .filter(DiagnosticoVehiculo.id_vehiculo == id_vehiculo)
            .order_by(DiagnosticoVehiculo.fecha.desc())
            .all()
        )

    @staticmethod
    def listar_por_mecanico(db: Session, id_mecanico: int) -> List[DiagnosticoVehiculo]:
        return (
            scoped_query(db, DiagnosticoVehiculo)
            .filter(DiagnosticoVehiculo.id_mecanico == id_mecanico)
            .order_by(DiagnosticoVehiculo.fecha.desc())
            .all()
        )

    @staticmethod
    def listar_por_registro(db: Session, id_registro: int) -> List[DiagnosticoVehiculo]:
        return (
            scoped_query(db, DiagnosticoVehiculo)
            .filter(DiagnosticoVehiculo.id_registro == id_registro)
            .order_by(DiagnosticoVehiculo.fecha.desc())
            .all()
        )

    @staticmethod
    def obtener_por_id(db: Session, id_diagnostico: int) -> DiagnosticoVehiculo:
        diag = (
            scoped_query(db, DiagnosticoVehiculo)
            .filter(DiagnosticoVehiculo.id_diagnostico == id_diagnostico)
            .first()
        )
        if not diag:
            raise EntityNotFoundError("Diagnóstico", id_diagnostico)
        return diag


class RecepcionService:
    @staticmethod
    def crear(db: Session, payload: Any) -> Dict[str, Any]:
        vehiculo = scoped_query(db, Vehiculo).filter(Vehiculo.id_vehiculo == payload.id_vehiculo).first()
        if not vehiculo:
            raise EntityNotFoundError("Vehículo", payload.id_vehiculo)

        km_ingreso = int(payload.kilometraje or 0)
        if vehiculo.kilometraje is None or km_ingreso > vehiculo.kilometraje:
            vehiculo.kilometraje = km_ingreso
            db.flush()
            AlertaMantenimientoService.verificar_y_enviar_alertas(db, vehiculo)

        id_reg = payload.id_registro
        if id_reg:
            orden = scoped_query(db, Registro).filter_by(id_registro=id_reg).first()
            if not orden or orden.id_vehiculo != payload.id_vehiculo:
                raise BusinessValidationError("La recepción debe corresponder a la orden y vehículo seleccionados")
            if orden.estado != EstadoOrden.PENDIENTE:
                raise BusinessValidationError("La recepción solo puede registrarse en una orden pendiente")
            if scoped_query(db, RecepcionVehiculo).filter_by(id_registro=id_reg).first():
                raise BusinessValidationError("La orden ya tiene recepción; actualice la existente")
            orden.kilometraje = km_ingreso
        if not id_reg and getattr(payload, "crear_orden_automatica", True):
            nueva_orden = Registro(
                fecha=date.today(),
                descripcion=f"Ingreso por recepción en taller ({payload.nivel_combustible} tanque)",
                observaciones=payload.danos_previos or payload.observaciones,
                costo_total=0.0,
                id_vehiculo=payload.id_vehiculo,
                id_encargado=payload.id_encargado,
                kilometraje=km_ingreso,
                estado=EstadoOrden.PENDIENTE,
                flujo_integrado=True,
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
        rec = scoped_query(db, RecepcionVehiculo).filter(RecepcionVehiculo.id_recepcion == id_recepcion).first()
        if not rec:
            raise EntityNotFoundError("Recepción", id_recepcion)

        datos = payload if isinstance(payload, dict) else payload.model_dump(exclude_unset=True)
        if rec.registro and rec.registro.estado != EstadoOrden.PENDIENTE:
            raise BusinessValidationError("La recepción no puede modificarse después de iniciar el diagnóstico")
        if "id_registro" in datos and datos["id_registro"] != rec.id_registro:
            raise BusinessValidationError("No se puede cambiar la orden de una recepción registrada")
        for key, val in datos.items():
            if hasattr(rec, key) and val is not None:
                setattr(rec, key, val)

        if rec.kilometraje and rec.vehiculo:
            if rec.vehiculo.kilometraje is None or rec.kilometraje > rec.vehiculo.kilometraje:
                rec.vehiculo.kilometraje = rec.kilometraje
        if rec.registro:
            rec.registro.kilometraje = rec.kilometraje

        db.commit()
        db.refresh(rec)
        return rec.to_dict()

    @staticmethod
    def obtener_por_id(db: Session, id_recepcion: int) -> Dict[str, Any]:
        rec = scoped_query(db, RecepcionVehiculo).filter(RecepcionVehiculo.id_recepcion == id_recepcion).first()
        if not rec:
            raise EntityNotFoundError("Recepción", id_recepcion)
        return rec.to_dict()

    @staticmethod
    def listar_todas(db: Session) -> List[Dict[str, Any]]:
        recs = scoped_query(db, RecepcionVehiculo).order_by(RecepcionVehiculo.fecha_ingreso.desc()).all()
        return [r.to_dict() for r in recs]

    @staticmethod
    def listar_por_vehiculo(db: Session, id_vehiculo: int) -> List[Dict[str, Any]]:
        recs = (
            scoped_query(db, RecepcionVehiculo)
            .filter(RecepcionVehiculo.id_vehiculo == id_vehiculo)
            .order_by(RecepcionVehiculo.fecha_ingreso.desc())
            .all()
        )
        return [r.to_dict() for r in recs]

    @staticmethod
    def obtener_por_registro(db: Session, id_registro: int) -> Optional[Dict[str, Any]]:
        rec = (
            scoped_query(db, RecepcionVehiculo)
            .filter(RecepcionVehiculo.id_registro == id_registro)
            .first()
        )
        return rec.to_dict() if rec else None

    @staticmethod
    def validar_completitud(db: Session, id_recepcion: int) -> Dict[str, Any]:
        rec = scoped_query(db, RecepcionVehiculo).filter(RecepcionVehiculo.id_recepcion == id_recepcion).first()
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
        from app.core.documentos import siguiente_numero
        return siguiente_numero(db, Presupuesto, "numero_presupuesto", "PRE")

    @staticmethod
    def crear(db: Session, payload: Any) -> Dict[str, Any]:
        reg = scoped_query(db, Registro).filter(Registro.id_registro == payload.id_registro).first()
        if not reg:
            raise EntityNotFoundError("Registro / Orden de trabajo", payload.id_registro)

        vehiculo = scoped_query(db, Vehiculo).filter(Vehiculo.id_vehiculo == payload.id_vehiculo).first()
        if not vehiculo:
            raise EntityNotFoundError("Vehículo", payload.id_vehiculo)

        reg = scoped_query(db, Registro).filter_by(id_registro=payload.id_registro).with_for_update(of=Registro).first()
        if reg.flujo_integrado:
            latest = scoped_query(db, Presupuesto).filter_by(id_registro=reg.id_registro).order_by(Presupuesto.id_presupuesto.desc()).first()
            if latest and latest.estado != "RECHAZADO":
                raise BusinessValidationError("Ya existe un presupuesto activo para esta orden")
            if not payload.items:
                raise BusinessValidationError("Agregue al menos un trabajo o repuesto al presupuesto")
        if reg.id_vehiculo != payload.id_vehiculo:
            raise BusinessValidationError("El presupuesto no corresponde al vehículo de la orden")
        from app.modules.taller.flujo import validar_etapa
        validar_etapa(db, reg, "presupuesto")
        if reg.flujo_integrado and reg.monto_pagado:
            raise BusinessValidationError("No se puede cambiar el presupuesto después de registrar pagos")
        for item in payload.items:
            if item.id_producto and item.cantidad != int(item.cantidad):
                raise BusinessValidationError("Los repuestos de inventario requieren unidades enteras")
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
        p = scoped_query(db, Presupuesto).filter(Presupuesto.id_presupuesto == id_presupuesto).first()
        if not p:
            raise EntityNotFoundError("Presupuesto", id_presupuesto)
        return p.to_dict()

    @staticmethod
    def listar_todos(db: Session) -> List[Dict[str, Any]]:
        pres = scoped_query(db, Presupuesto).order_by(Presupuesto.id_presupuesto.desc()).all()
        return [p.to_dict() for p in pres]

    @staticmethod
    def listar_por_registro(db: Session, id_registro: int) -> List[Dict[str, Any]]:
        pres = (
            scoped_query(db, Presupuesto)
            .filter(Presupuesto.id_registro == id_registro)
            .order_by(Presupuesto.id_presupuesto.desc())
            .all()
        )
        return [p.to_dict() for p in pres]

    @staticmethod
    def listar_por_vehiculo(db: Session, id_vehiculo: int) -> List[Dict[str, Any]]:
        pres = (
            scoped_query(db, Presupuesto)
            .filter(Presupuesto.id_vehiculo == id_vehiculo)
            .order_by(Presupuesto.id_presupuesto.desc())
            .all()
        )
        return [p.to_dict() for p in pres]

    @staticmethod
    def enviar_al_cliente(db: Session, id_presupuesto: int) -> Dict[str, Any]:
        p = scoped_query(db, Presupuesto).filter(Presupuesto.id_presupuesto == id_presupuesto).first()
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
        p = scoped_query(db, Presupuesto).filter(Presupuesto.id_presupuesto == id_presupuesto).first()
        if not p:
            raise EntityNotFoundError("Presupuesto", id_presupuesto)

        decision = (payload.decision or "").strip().upper()
        if decision not in ("APROBADO_TOTAL", "APROBADO_PARCIAL", "RECHAZADO"):
            raise BusinessValidationError(
                f"Decisión inválida: '{decision}'. Debe ser 'APROBADO_TOTAL', 'APROBADO_PARCIAL' o 'RECHAZADO'."
            )

        reg = scoped_query(db, Registro).filter(Registro.id_registro == p.id_registro).first()
        if reg and reg.flujo_integrado and p.estado != "ENVIADO":
            raise BusinessValidationError("Envíe el presupuesto al cliente antes de registrar su respuesta")
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
                # Iniciar una orden pendiente tras aprobar el presupuesto.
                if reg.estado == EstadoOrden.PENDIENTE or (reg.flujo_integrado and reg.estado == EstadoOrden.FINALIZADA):
                    aplicar_estado(reg, EstadoOrden.EN_PROCESO)

        elif decision == "APROBADO_PARCIAL":
            p.estado = "APROBADO_PARCIAL"
            ids_aprobados = set(payload.items_aprobados_ids or [])
            if not ids_aprobados.issubset({item.id_item for item in p.items}):
                raise BusinessValidationError("Los conceptos seleccionados no pertenecen a este presupuesto")
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
                if reg.estado == EstadoOrden.PENDIENTE or (reg.flujo_integrado and reg.estado == EstadoOrden.FINALIZADA):
                    aplicar_estado(reg, EstadoOrden.EN_PROCESO)

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
                # El rechazo pertenece al presupuesto; no implica entregar el vehículo.
                # La decisión RECHAZADO permanece en el presupuesto.
                reg.observaciones = ((reg.observaciones or "") + " | Presupuesto rechazado").strip(" |")
                if reg.flujo_integrado:
                    aplicar_estado(reg, EstadoOrden.FINALIZADA)

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
        reg = scoped_query(db, Registro).filter(Registro.id_registro == payload.id_registro).first()
        if not reg:
            raise EntityNotFoundError("Registro de taller", payload.id_registro)

        from app.modules.taller.flujo import validar_etapa
        validar_etapa(db, reg, "reparacion")
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
        if reg.estado == EstadoOrden.PENDIENTE:
            aplicar_estado(reg, EstadoOrden.EN_PROCESO)

        db.commit()
        db.refresh(bitacora)
        return bitacora.to_dict()

    @staticmethod
    def listar_bitacoras_por_registro(db: Session, id_registro: int) -> List[Dict[str, Any]]:
        bits = (
            scoped_query(db, BitacoraReparacion)
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
        reg = scoped_query(db, Registro).filter(Registro.id_registro == payload.id_registro).first()
        if not reg:
            raise EntityNotFoundError("Registro de taller", payload.id_registro)

        from app.modules.taller.flujo import validar_etapa
        validar_etapa(db, reg, "reparacion")
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
        dano = scoped_query(db, DanoAdicional).filter(DanoAdicional.id_dano == id_dano).first()
        if not dano:
            raise EntityNotFoundError("Daño adicional", id_dano)

        aprobado = bool(payload.aprobado)
        dano.estado = "APROBADO" if aprobado else "RECHAZADO"
        dano.fecha_respuesta = datetime.now()
        dano.observaciones_cliente = payload.observaciones_cliente

        reg = scoped_query(db, Registro).filter(Registro.id_registro == dano.id_registro).first()
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
            scoped_query(db, DanoAdicional)
            .filter(DanoAdicional.id_registro == id_registro)
            .order_by(DanoAdicional.fecha_deteccion.desc())
            .all()
        )
        return [d.to_dict() for d in danos]

    @staticmethod
    def registrar_control_calidad(db: Session, payload: Any) -> Dict[str, Any]:
        """
        Proceso 8 y 8.1: Revisión post-reparación y escaneo OBD2.
        - Si pasa (Proceso 9): Se marca orden finalizada (estado 2) y fecha de completado.
        - Si no pasa (Proceso 8.1): Se devuelve al mecánico para corregir el problema SIN cobrar extra (estado 1).
        """
        reg = scoped_query(db, Registro).filter(Registro.id_registro == payload.id_registro).first()
        if not reg:
            raise EntityNotFoundError("Registro de taller", payload.id_registro)

        from app.modules.taller.flujo import validar_etapa
        validar_etapa(db, reg, "calidad")
        if reg.estado not in (EstadoOrden.EN_PROCESO, EstadoOrden.FINALIZADA):
            raise BusinessValidationError("El control requiere una orden en proceso o finalizada")
        if not payload.paso_inspeccion and not (payload.motivo_devolucion or "").strip():
            raise BusinessValidationError("Indique el motivo de devolución a reparación")
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
            # Proceso 9: Trabajo finalizado, listo para entrega.
            aplicar_estado(reg, EstadoOrden.FINALIZADA)
            if not reg.fecha_completado:
                reg.fecha_completado = ahora
            mensaje = "El vehículo superó exitosamente el control de calidad y escaneo final. Marcado como LISTO PARA ENTREGA."
        else:
            # Proceso 8.1: Devolver al mecánico sin costo extra (Garantía interna de taller)
            aplicar_estado(reg, EstadoOrden.EN_PROCESO)
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
            scoped_query(db, ControlCalidad)
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
        reg = scoped_query(db, Registro).filter(Registro.id_registro == payload.id_registro).first()
        if not reg:
            raise EntityNotFoundError("Registro / Orden de taller", payload.id_registro)

        from app.modules.taller.flujo import validar_etapa
        validar_etapa(db, reg, "entrega")
        if reg.flujo_integrado and (not payload.firma_cliente_entrega or not payload.persona_recibe.strip()):
            raise BusinessValidationError("La entrega requiere nombre y firma de quien recibe")
        # Regla estricta Proceso 11.1 / Proceso 15: La orden debe estar PAGADA
        # El pago se consulta de forma independiente al estado del trabajo.
        nota = (
            scoped_query(db, NotaDeVenta)
            .filter(NotaDeVenta.id_registro == reg.id_registro)
            .order_by(NotaDeVenta.id_nota_venta.desc())
            .first()
        )
        esta_pagada = reg.estado_pago == EstadoPago.PAGADO
        if not esta_pagada and reg.costo_total > 0:
            raise BusinessValidationError(
                "Proceso 11.1 / Proceso 15: No se puede entregar el vehículo al cliente. "
                "La orden no ha sido pagada. Debe confirmarse el pago y emitirse la Nota de Venta primero."
            )

        vehiculo = scoped_query(db, Vehiculo).filter(Vehiculo.id_vehiculo == reg.id_vehiculo).first()
        km_salida = int(payload.kilometraje_salida or reg.kilometraje or (vehiculo.kilometraje if vehiculo else 0) or 0)

        # Actualizar kilometraje del vehículo si aumentó
        if vehiculo and km_salida > (vehiculo.kilometraje or 0):
            vehiculo.kilometraje = km_salida

        ahora = datetime.now()
        if reg.estado == EstadoOrden.ENTREGADA:
            raise BusinessValidationError("El vehículo ya fue entregado")
        aplicar_estado(reg, EstadoOrden.ENTREGADA)

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
            scoped_query(db, Presupuesto)
            .filter(Presupuesto.id_registro == reg.id_registro)
            .order_by(Presupuesto.id_presupuesto.desc())
            .first()
        )
        if presupuesto and presupuesto.items:
            for item in presupuesto.items:
                if str(item.estado_aprobacion).upper() == "APROBADO":
                    desc_pieza = item.descripcion.strip().upper()
                    mantenimiento = (
                        scoped_query(db, MantenimientoRealizado)
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
        ent = scoped_query(db, EntregaVehiculo).filter(EntregaVehiculo.id_registro == id_registro).first()
        return ent.to_dict() if ent else None

    @staticmethod
    def listar_entregas(db: Session) -> List[Dict[str, Any]]:
        ents = scoped_query(db, EntregaVehiculo).order_by(EntregaVehiculo.fecha_entrega.desc()).all()
        return [e.to_dict() for e in ents]




