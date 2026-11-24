"""Servicios de gestión financiera, catálogo de movimientos, cuentas por cobrar y caja."""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessValidationError, ConflictError
from app.modules.finanzas.models import (
    CategoriaMovimiento,
    PagoEmpleado,
    MovimientoCaja,
    CierreCaja,
)
from app.modules.sistema.auditoria import registrar_auditoria
from app.modules.taller.models import Registro
from app.modules.taller.pagos import PagoOrden
from app.modules.taller.service import RegistroService
from app.modules.facturacion.models import Factura


DEFAULT_CATEGORIAS = [
    ("Compra inventario", "EGRESO", "Reposición de repuestos y materiales", False),
    ("Sueldo", "EGRESO", "Pago de remuneración fija o periódica a personal", True),
    ("Bono", "EGRESO", "Bonificación o incentivo al personal", True),
    ("Comisión", "EGRESO", "Comisión por órdenes o trabajos ejecutados", True),
    ("Anticipo", "EGRESO", "Adelanto de pago al personal", True),
    ("Servicio externo", "EGRESO", "Servicios tercerizados (rectificadora, grúa, etc.)", False),
    ("Alquiler", "EGRESO", "Arriendo del local del taller", False),
    ("Servicios básicos", "EGRESO", "Agua, luz, internet y telefonía", False),
    ("Herramientas", "EGRESO", "Adquisición o mantenimiento de herramientas", False),
    ("Otro", "EGRESO", "Otros gastos operativos", False),
    ("Servicio de taller", "INGRESO", "Ingresos por órdenes de trabajo y reparaciones", False),
    ("Venta mostrador", "INGRESO", "Venta directa de repuestos desde inventario", False),
    ("Ingreso a caja", "INGRESO", "Ingreso manual de efectivo a caja", False),
]


def _parse_money(val: Any, allow_zero: bool = False) -> float:
    try:
        dec = Decimal(str(val))
    except (InvalidOperation, ValueError):
        raise BusinessValidationError("El monto ingresado es inválido")
    if not dec.is_finite():
        raise BusinessValidationError("El monto ingresado es inválido")
    if allow_zero:
        if dec < 0:
            raise BusinessValidationError("El monto no puede ser negativo")
    else:
        if dec <= 0:
            raise BusinessValidationError("El monto debe ser mayor a cero")
    if dec != dec.quantize(Decimal("0.01")):
        raise BusinessValidationError("El monto debe tener máximo dos decimales")
    return float(dec)


def _parse_date_range(fecha_inicio: Optional[str], fecha_fin: Optional[str]) -> tuple[Optional[date], Optional[date]]:
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
    return fi, ff


class FinanzasService:
    @staticmethod
    def asegurar_categorias(db: Session) -> None:
        if db.query(CategoriaMovimiento).count() > 0:
            return
        for nombre, tipo, desc, es_personal in DEFAULT_CATEGORIAS:
            db.add(
                CategoriaMovimiento(
                    nombre=nombre,
                    tipo=tipo,
                    descripcion=desc,
                    es_personal=es_personal,
                    activa=True,
                )
            )
        db.commit()

    @staticmethod
    def listar_categorias(db: Session, tipo: Optional[str] = None) -> List[Dict[str, Any]]:
        FinanzasService.asegurar_categorias(db)
        query = db.query(CategoriaMovimiento).filter(CategoriaMovimiento.activa == True)  # noqa: E712
        if tipo:
            t = tipo.strip().upper()
            query = query.filter((CategoriaMovimiento.tipo == t) | (CategoriaMovimiento.tipo == "AMBOS"))
        return [c.to_dict() for c in query.order_by(CategoriaMovimiento.tipo.asc(), CategoriaMovimiento.nombre.asc()).all()]

    @staticmethod
    def crear_categoria(
        db: Session,
        nombre: str,
        tipo: str,
        descripcion: Optional[str],
        es_personal: bool,
        actor_id: int,
    ) -> Dict[str, Any]:
        FinanzasService.asegurar_categorias(db)
        nombre_limpio = (nombre or "").strip()
        if len(nombre_limpio) < 2:
            raise BusinessValidationError("El nombre de la categoría es obligatorio")
        tipo_norm = (tipo or "EGRESO").strip().upper()
        if tipo_norm not in ("INGRESO", "EGRESO", "AMBOS"):
            raise BusinessValidationError("El tipo debe ser INGRESO, EGRESO o AMBOS")
        existente = (
            db.query(CategoriaMovimiento)
            .filter(func.lower(CategoriaMovimiento.nombre) == nombre_limpio.lower())
            .first()
        )
        if existente:
            raise ConflictError("Ya existe una categoría financiera con ese nombre")
        cat = CategoriaMovimiento(
            nombre=nombre_limpio,
            tipo=tipo_norm,
            descripcion=descripcion.strip() if descripcion else None,
            es_personal=bool(es_personal),
            activa=True,
        )
        db.add(cat)
        db.flush()
        registrar_auditoria(
            db,
            actor_id,
            "FINANZAS_CATEGORIA_CREADA",
            "CategoriaMovimiento",
            cat.id_categoria,
            f"Categoría financiera creada: {cat.nombre} ({cat.tipo})",
        )
        db.commit()
        db.refresh(cat)
        return cat.to_dict()

    @staticmethod
    def validar_categoria_egreso(db: Session, categoria: Optional[str], concepto: str) -> str:
        """Valida que una categoría explícita exista en el catálogo activo; si se omite, infiere o conserva compatibilidad."""
        FinanzasService.asegurar_categorias(db)
        if categoria and categoria.strip():
            cat = (
                db.query(CategoriaMovimiento)
                .filter(
                    func.lower(CategoriaMovimiento.nombre) == categoria.strip().lower(),
                    CategoriaMovimiento.activa == True,  # noqa: E712
                    CategoriaMovimiento.tipo.in_(["EGRESO", "AMBOS"]),
                )
                .first()
            )
            if not cat:
                raise BusinessValidationError(f"Categoría de egreso inválida o no registrada en el catálogo: {categoria}")
            return cat.nombre
        match_concepto = (
            db.query(CategoriaMovimiento)
            .filter(
                func.lower(CategoriaMovimiento.nombre) == concepto.strip().lower(),
                CategoriaMovimiento.activa == True,  # noqa: E712
                CategoriaMovimiento.tipo.in_(["EGRESO", "AMBOS"]),
            )
            .first()
        )
        return match_concepto.nombre if match_concepto else "Otro"

    @staticmethod
    def consultar_deudas_clientes(
        db: Session,
        id_cliente: Optional[int] = None,
        q: Optional[str] = None,
    ) -> Dict[str, Any]:
        """RF-36 / HU-46: Consolidado de cuentas por cobrar agrupado por cliente."""
        registros = db.query(Registro).order_by(Registro.fecha.desc(), Registro.id_registro.desc()).all()
        por_cliente: Dict[int, Dict[str, Any]] = {}
        busqueda = (q or "").strip().lower()

        for reg in registros:
            dto = RegistroService.construir_listado_dto(db, reg)
            saldo = float(dto.get("saldo_pendiente") or 0.0)
            if saldo <= 0.009:
                continue
            cid = int(dto.get("id_cliente") or 0)
            if id_cliente is not None and cid != id_cliente:
                continue
            if busqueda:
                haystack = " ".join([
                    str(dto.get("nombre_cliente") or ""),
                    str(dto.get("cliente_cedula") or ""),
                    str(dto.get("placa") or ""),
                ]).lower()
                if busqueda not in haystack:
                    continue

            if cid not in por_cliente:
                por_cliente[cid] = {
                    "id_cliente": cid,
                    "nombre_cliente": dto.get("nombre_cliente") or "Cliente General",
                    "cedula": dto.get("cliente_cedula"),
                    "telefono": dto.get("cliente_telefono"),
                    "correo": dto.get("cliente_correo"),
                    "total_facturado": 0.0,
                    "total_abonado": 0.0,
                    "saldo_total_pendiente": 0.0,
                    "cantidad_ordenes": 0,
                    "ordenes": [],
                }
            bucket = por_cliente[cid]
            costo = float(dto.get("costo_total") or 0.0)
            pagado = float(dto.get("monto_pagado") or 0.0)
            bucket["total_facturado"] = round(bucket["total_facturado"] + costo, 2)
            bucket["total_abonado"] = round(bucket["total_abonado"] + pagado, 2)
            bucket["saldo_total_pendiente"] = round(bucket["saldo_total_pendiente"] + saldo, 2)
            bucket["cantidad_ordenes"] += 1
            bucket["ordenes"].append({
                "id_registro": dto["id_registro"],
                "fecha": dto["fecha"],
                "placa": dto["placa"],
                "marca_vehiculo": dto["marca_vehiculo"],
                "modelo_vehiculo": dto["modelo_vehiculo"],
                "tipo_servicio": dto["tipo_servicio"],
                "estado": dto["estado"],
                "estado_pago": dto["estado_pago"],
                "costo_total": costo,
                "monto_pagado": pagado,
                "saldo_pendiente": saldo,
                "pagos": dto.get("pagos", []),
            })

        clientes_lista = sorted(
            por_cliente.values(),
            key=lambda item: item["saldo_total_pendiente"],
            reverse=True,
        )
        total_cartera = round(sum(c["saldo_total_pendiente"] for c in clientes_lista), 2)
        return {
            "total_clientes_con_deuda": len(clientes_lista),
            "total_cartera_pendiente": total_cartera,
            "clientes": clientes_lista,
        }

    @staticmethod
    def resumen_financiero_periodo(
        db: Session,
        fecha_inicio: Optional[str] = None,
        fecha_fin: Optional[str] = None,
    ) -> Dict[str, Any]:
        """RF-38 / HU-48: Resumen financiero calculado en servidor por rango de fechas."""
        fi, ff = _parse_date_range(fecha_inicio, fecha_fin)

        pagos_q = db.query(PagoOrden)
        if fi:
            pagos_q = pagos_q.filter(PagoOrden.fecha >= datetime.combine(fi, datetime.min.time()))
        if ff:
            pagos_q = pagos_q.filter(PagoOrden.fecha <= datetime.combine(ff, datetime.max.time()))
        pagos = pagos_q.all()

        desglose_metodos = {"EFECTIVO": 0.0, "TRANSFERENCIA": 0.0, "TARJETA": 0.0}
        ingresos_servicios = 0.0
        for p in pagos:
            m = float(p.monto or 0.0)
            ingresos_servicios += m
            met = (p.metodo or "EFECTIVO").upper()
            desglose_metodos[met] = round(desglose_metodos.get(met, 0.0) + m, 2)

        # Incluir abonos históricos sin filas en pagos_orden (misma regla que cobrosDeOrdenes)
        registros_con_pago_tabla = {p.id_registro for p in db.query(PagoOrden.id_registro).distinct().all()}
        for reg in db.query(Registro).filter(Registro.monto_pagado > 0).all():
            if reg.id_registro in registros_con_pago_tabla:
                continue
            ref_date = reg.fecha_facturado.date() if reg.fecha_facturado else reg.fecha
            if fi and ref_date < fi:
                continue
            if ff and ref_date > ff:
                continue
            ingresos_servicios += float(reg.monto_pagado or 0.0)

        # Ventas directas de inventario (origen_venta == 'INVENTARIO' no asociadas a orden)
        ordenes_facturas = {
            r.id_factura for r in db.query(Registro.id_factura).filter(Registro.id_factura.isnot(None)).all()
        }
        fac_q = db.query(Factura).filter(Factura.origen_venta == "INVENTARIO")
        if fi:
            fac_q = fac_q.filter(Factura.fecha_emision >= datetime.combine(fi, datetime.min.time()))
        if ff:
            fac_q = fac_q.filter(Factura.fecha_emision <= datetime.combine(ff, datetime.max.time()))
        ingresos_mostrador = sum(
            float(f.costo_total or 0.0)
            for f in fac_q.all()
            if f.id_factura not in ordenes_facturas
        )

        # Egresos y pagos a empleados
        gastos_q = db.query(PagoEmpleado)
        if fi:
            gastos_q = gastos_q.filter(PagoEmpleado.fecha >= fi)
        if ff:
            gastos_q = gastos_q.filter(PagoEmpleado.fecha <= ff)
        gastos = gastos_q.all()

        egresos_empleados = sum(float(g.monto or 0.0) for g in gastos if g.id_empleado and g.id_empleado > 0)
        egresos_operativos = sum(float(g.monto or 0.0) for g in gastos if not g.id_empleado or g.id_empleado == 0)

        total_ingresos = round(ingresos_servicios + ingresos_mostrador, 2)
        total_egresos = round(egresos_empleados + egresos_operativos, 2)
        balance_neto = round(total_ingresos - total_egresos, 2)

        return {
            "fecha_inicio": fi.isoformat() if fi else None,
            "fecha_fin": ff.isoformat() if ff else None,
            "ingresos_servicios": round(ingresos_servicios, 2),
            "ingresos_mostrador": round(ingresos_mostrador, 2),
            "total_ingresos": total_ingresos,
            "desglose_metodos": desglose_metodos,
            "egresos_empleados": round(egresos_empleados, 2),
            "egresos_operativos": round(egresos_operativos, 2),
            "total_egresos": total_egresos,
            "balance_neto": balance_neto,
            "cantidad_cobros": len(pagos),
            "cantidad_egresos": len(gastos),
        }


class CajaService:
    @staticmethod
    def saldo_actual(db: Session) -> float:
        ultimo = (
            db.query(MovimientoCaja)
            .order_by(MovimientoCaja.id_movimiento.desc())
            .first()
        )
        return round(float(ultimo.saldo_resultante), 2) if ultimo else 0.0

    @staticmethod
    def sesion_abierta(db: Session) -> Optional[CierreCaja]:
        return (
            db.query(CierreCaja)
            .filter(CierreCaja.estado == "ABIERTA")
            .order_by(CierreCaja.id_cierre.desc())
            .first()
        )

    @staticmethod
    def resumen(db: Session) -> Dict[str, Any]:
        abierta = CajaService.sesion_abierta(db)
        saldo = CajaService.saldo_actual(db)
        hoy_inicio = datetime.combine(date.today(), datetime.min.time())
        movs_hoy = db.query(MovimientoCaja).filter(MovimientoCaja.fecha >= hoy_inicio).all()
        ingresos_hoy = sum(float(m.monto or 0.0) for m in movs_hoy if m.tipo in ("INGRESO", "APERTURA"))
        retiros_hoy = sum(float(m.monto or 0.0) for m in movs_hoy if m.tipo == "RETIRO")
        return {
            "saldo_actual": saldo,
            "caja_abierta": abierta is not None,
            "sesion_actual": abierta.to_dict() if abierta else None,
            "ingresos_hoy": round(ingresos_hoy, 2),
            "retiros_hoy": round(retiros_hoy, 2),
        }

    @staticmethod
    def listar_movimientos(
        db: Session,
        fecha_inicio: Optional[str] = None,
        fecha_fin: Optional[str] = None,
        tipo: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        fi, ff = _parse_date_range(fecha_inicio, fecha_fin)
        q = db.query(MovimientoCaja)
        if fi:
            q = q.filter(MovimientoCaja.fecha >= datetime.combine(fi, datetime.min.time()))
        if ff:
            q = q.filter(MovimientoCaja.fecha <= datetime.combine(ff, datetime.max.time()))
        if tipo:
            q = q.filter(func.upper(MovimientoCaja.tipo) == tipo.strip().upper())
        movs = q.order_by(MovimientoCaja.fecha.desc(), MovimientoCaja.id_movimiento.desc()).all()
        return [m.to_dict() for m in movs]

    @staticmethod
    def listar_cierres(db: Session) -> List[Dict[str, Any]]:
        cierres = db.query(CierreCaja).order_by(CierreCaja.id_cierre.desc()).limit(100).all()
        return [c.to_dict() for c in cierres]

    @staticmethod
    def abrir_caja(db: Session, monto_inicial: Any, observaciones: Optional[str], actor_id: int) -> Dict[str, Any]:
        if CajaService.sesion_abierta(db):
            raise BusinessValidationError("Ya existe una caja abierta. Ciérrala antes de abrir una nueva.")
        monto = _parse_money(monto_inicial, allow_zero=True)
        ahora = datetime.now()
        saldo_ant = CajaService.saldo_actual(db)
        nuevo_saldo = round(saldo_ant + monto, 2)

        sesion = CierreCaja(
            fecha_apertura=ahora,
            monto_inicial=monto,
            total_ingresos=0.0,
            total_retiros=0.0,
            saldo_esperado=nuevo_saldo,
            estado="ABIERTA",
            id_usuario_apertura=actor_id,
            observaciones=observaciones.strip() if observaciones else None,
        )
        db.add(sesion)
        db.add(
            MovimientoCaja(
                fecha=ahora,
                tipo="APERTURA",
                monto=monto,
                motivo="Apertura de caja",
                id_usuario=actor_id,
                saldo_anterior=saldo_ant,
                saldo_resultante=nuevo_saldo,
                observaciones=observaciones.strip() if observaciones else None,
            )
        )
        db.flush()
        registrar_auditoria(
            db,
            actor_id,
            "CAJA_APERTURA",
            "CierreCaja",
            sesion.id_cierre,
            f"Apertura de caja con monto inicial ${monto:.2f}. Saldo: ${nuevo_saldo:.2f}",
        )
        db.commit()
        db.refresh(sesion)
        return sesion.to_dict()

    @staticmethod
    def registrar_movimiento(
        db: Session,
        tipo: str,
        monto_raw: Any,
        motivo: str,
        referencia: Optional[str],
        observaciones: Optional[str],
        actor_id: int,
        id_registro: Optional[int] = None,
    ) -> Dict[str, Any]:
        tipo_norm = (tipo or "").strip().upper()
        if tipo_norm not in ("INGRESO", "RETIRO"):
            raise BusinessValidationError("El tipo de movimiento debe ser INGRESO o RETIRO")
        monto = _parse_money(monto_raw, allow_zero=False)
        motivo_limpio = (motivo or "").strip()
        if len(motivo_limpio) < 3:
            raise BusinessValidationError("El motivo del movimiento de caja es obligatorio")

        saldo_ant = CajaService.saldo_actual(db)
        if tipo_norm == "RETIRO" and monto > saldo_ant:
            raise BusinessValidationError(
                f"Saldo insuficiente en caja para retirar ${monto:.2f} (disponible: ${saldo_ant:.2f})"
            )

        nuevo_saldo = round(saldo_ant + monto if tipo_norm == "INGRESO" else saldo_ant - monto, 2)
        mov = MovimientoCaja(
            fecha=datetime.now(),
            tipo=tipo_norm,
            monto=monto,
            motivo=motivo_limpio,
            referencia=referencia.strip() if referencia else None,
            id_registro=id_registro,
            id_usuario=actor_id,
            saldo_anterior=saldo_ant,
            saldo_resultante=nuevo_saldo,
            observaciones=observaciones.strip() if observaciones else None,
        )
        db.add(mov)

        abierta = CajaService.sesion_abierta(db)
        if abierta:
            if tipo_norm == "INGRESO":
                abierta.total_ingresos = round(float(abierta.total_ingresos or 0.0) + monto, 2)
            else:
                abierta.total_retiros = round(float(abierta.total_retiros or 0.0) + monto, 2)
            abierta.saldo_esperado = nuevo_saldo

        db.flush()
        registrar_auditoria(
            db,
            actor_id,
            f"CAJA_{tipo_norm}",
            "MovimientoCaja",
            mov.id_movimiento,
            f"{tipo_norm} en caja por ${monto:.2f}. Motivo: {motivo_limpio}. Saldo: ${nuevo_saldo:.2f}",
        )
        db.commit()
        db.refresh(mov)
        return mov.to_dict()

    @staticmethod
    def cerrar_caja(
        db: Session,
        monto_fisico_raw: Any,
        observaciones: Optional[str],
        actor_id: int,
    ) -> Dict[str, Any]:
        abierta = CajaService.sesion_abierta(db)
        if not abierta:
            raise BusinessValidationError("No hay una sesión de caja abierta para cerrar")
        monto_fisico = _parse_money(monto_fisico_raw, allow_zero=True)
        saldo_esperado = CajaService.saldo_actual(db)
        diferencia = round(monto_fisico - saldo_esperado, 2)
        ahora = datetime.now()

        abierta.fecha_cierre = ahora
        abierta.saldo_esperado = saldo_esperado
        abierta.monto_fisico_contado = monto_fisico
        abierta.diferencia = diferencia
        abierta.estado = "CERRADA"
        abierta.id_usuario_cierre = actor_id
        if observaciones:
            abierta.observaciones = observaciones.strip()

        db.add(
            MovimientoCaja(
                fecha=ahora,
                tipo="CIERRE",
                monto=monto_fisico,
                motivo=f"Cierre / Arqueo de caja (Diferencia: ${diferencia:+.2f})",
                id_usuario=actor_id,
                saldo_anterior=saldo_esperado,
                saldo_resultante=saldo_esperado,
                observaciones=observaciones.strip() if observaciones else None,
            )
        )
        registrar_auditoria(
            db,
            actor_id,
            "CAJA_CIERRE",
            "CierreCaja",
            abierta.id_cierre,
            f"Arqueo/Cierre de caja. Esperado: ${saldo_esperado:.2f}, Físico: ${monto_fisico:.2f}, Dif: ${diferencia:+.2f}",
        )
        db.commit()
        db.refresh(abierta)
        return abierta.to_dict()

    @staticmethod
    def registrar_cobro_efectivo_si_abierta(db: Session, id_registro: int, monto: float, actor_id: int) -> None:
        """Si hay caja abierta, refleja el abono en efectivo dentro de los movimientos de caja."""
        abierta = CajaService.sesion_abierta(db)
        if not abierta:
            return
        saldo_ant = CajaService.saldo_actual(db)
        nuevo_saldo = round(saldo_ant + float(monto), 2)
        mov = MovimientoCaja(
            fecha=datetime.now(),
            tipo="INGRESO",
            monto=round(float(monto), 2),
            motivo=f"Cobro en efectivo Orden #{id_registro}",
            referencia=f"ORD-{id_registro:06d}",
            id_registro=id_registro,
            id_usuario=actor_id,
            saldo_anterior=saldo_ant,
            saldo_resultante=nuevo_saldo,
        )
        db.add(mov)
        abierta.total_ingresos = round(float(abierta.total_ingresos or 0.0) + float(monto), 2)
        abierta.saldo_esperado = nuevo_saldo
