from app.core.access_scope import scoped_query
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.exceptions import EntityNotFoundError, BusinessValidationError
from app.modules.facturacion.models import (
    Factura,
    DetalleFactura,
    NotaDeVenta,
    ItemNotaDeVenta,
)
from app.modules.inventario.models import Producto, MovimientoKardex, ReservaRepuesto
from app.modules.taller.models import (
    Registro,
    Presupuesto,
    ItemPresupuesto,
    DanoAdicional,
    BitacoraReparacion,
)
from app.modules.vehiculos.models import Vehiculo
from app.modules.usuarios.models import Usuario


class FacturaService:
    @staticmethod
    def listar_todas(db: Session) -> List[Factura]:
        return scoped_query(db, Factura).order_by(Factura.id_factura.desc()).all()

    @staticmethod
    def obtener_por_id(db: Session, id_factura: int) -> Factura:
        factura = scoped_query(db, Factura).filter(Factura.id_factura == id_factura).first()
        if not factura:
            raise EntityNotFoundError("Factura", id_factura)
        return factura

    @staticmethod
    def crear(db: Session, payload: Any) -> Factura:
        nueva = Factura(
            fecha_emision=datetime.now(),
            id_usuario=payload.id_usuario,
            costo_total=float(payload.costo_total or 0.0),
            cliente_nombre=payload.cliente_nombre,
            cliente_cedula=payload.cliente_cedula,
            cliente_telefono=payload.cliente_telefono,
            cliente_correo=payload.cliente_correo,
            cliente_direccion=payload.cliente_direccion,
            cliente_tipo=payload.cliente_tipo or ("SISTEMA" if payload.id_usuario else "EXTERNO"),
            origen_venta=payload.origen_venta or "TALLER",
        )
        db.add(nueva)
        db.commit()
        db.refresh(nueva)
        return nueva

    @staticmethod
    def actualizar(db: Session, id_factura: int, payload: Any) -> Factura:
        factura = FacturaService.obtener_por_id(db, id_factura)
        if scoped_query(db, Registro).filter(Registro.id_factura == id_factura, Registro.monto_pagado > 0).first():
            raise BusinessValidationError("La orden tiene pagos registrados; no se puede alterar el comprobante")
        if payload.id_usuario is not None:
            factura.id_usuario = payload.id_usuario
        if payload.costo_total is not None:
            factura.costo_total = float(payload.costo_total)
        if payload.cliente_nombre is not None:
            factura.cliente_nombre = payload.cliente_nombre
        if payload.cliente_cedula is not None:
            factura.cliente_cedula = payload.cliente_cedula
        if payload.cliente_telefono is not None:
            factura.cliente_telefono = payload.cliente_telefono
        if payload.cliente_correo is not None:
            factura.cliente_correo = payload.cliente_correo
        if payload.cliente_direccion is not None:
            factura.cliente_direccion = payload.cliente_direccion
        if payload.cliente_tipo is not None:
            factura.cliente_tipo = payload.cliente_tipo
        if payload.origen_venta is not None:
            factura.origen_venta = payload.origen_venta

        db.commit()
        db.refresh(factura)
        return factura

    @staticmethod
    def recalcular_total(db: Session, id_factura: int) -> Factura:
        factura = FacturaService.obtener_por_id(db, id_factura)
        detalles = scoped_query(db, DetalleFactura).filter(DetalleFactura.id_factura == id_factura).all()
        total = sum(float(d.subtotal or 0.0) for d in detalles)
        factura.costo_total = round(max(0.0, total), 2)
        db.commit()
        db.refresh(factura)
        return factura

    @staticmethod
    def eliminar(db: Session, id_factura: int) -> None:
        factura = FacturaService.obtener_por_id(db, id_factura)
        if scoped_query(db, Registro).filter(Registro.id_factura == id_factura, Registro.monto_pagado > 0).first():
            raise BusinessValidationError("La orden tiene pagos registrados; no se puede alterar el comprobante")
        if not scoped_query(db, Registro).filter_by(id_factura=id_factura).first():
            from app.modules.inventario.movimientos import bloquear_producto, mover
            for det in scoped_query(db, DetalleFactura).filter_by(id_factura=id_factura).all():
                if det.id_producto:
                    mover(db, bloquear_producto(db, det.id_producto), det.cantidad, "ANULACION_FACTURA", db.info.get("actor").id_usuario if db.info.get("actor") else None, motivo=f"Anulación factura #{id_factura}")
        db.delete(factura)
        db.commit()


class DetalleFacturaService:
    @staticmethod
    def listar_por_factura(db: Session, id_factura: int) -> List[DetalleFactura]:
        return (
            scoped_query(db, DetalleFactura)
            .filter(DetalleFactura.id_factura == id_factura)
            .order_by(DetalleFactura.id_detalle.asc())
            .all()
        )

    @staticmethod
    def crear(db: Session, payload: Any) -> DetalleFactura:
        factura = FacturaService.obtener_por_id(db, payload.id_factura)
        if scoped_query(db, Registro).filter(Registro.id_factura == payload.id_factura, Registro.monto_pagado > 0).first():
            raise BusinessValidationError("No se puede modificar una orden con pagos registrados")
        cantidad = int(payload.cantidad or 1)
        if cantidad <= 0:
            raise BusinessValidationError("La cantidad debe ser mayor a cero")

        descripcion = (payload.descripcion or "").strip()
        es_descuento = descripcion.startswith("[DESC")

        if payload.id_producto:
            prod = db.query(Producto).filter(Producto.id_producto == payload.id_producto).first()
            if not prod:
                raise EntityNotFoundError("Producto", payload.id_producto)
            precio_unit = (
                float(payload.precio_unitario)
                if payload.precio_unitario is not None
                else float(prod.pvp)
            )
            if not descripcion:
                descripcion = prod.nombre
        else:
            precio_unit = float(payload.precio_unitario or 0.0)
            if not es_descuento and precio_unit < 0:
                raise BusinessValidationError("El precio unitario no puede ser negativo salvo en descuentos")
            if not descripcion:
                descripcion = "Servicio mecánico"

        subtotal = (
            float(payload.subtotal)
            if payload.subtotal is not None
            else round(cantidad * precio_unit, 2)
        )

        nuevo = DetalleFactura(
            id_factura=factura.id_factura,
            id_producto=payload.id_producto,
            descripcion=descripcion,
            cantidad=cantidad,
            precio_unitario=precio_unit,
            subtotal=subtotal,
        )
        db.add(nuevo)
        db.flush()
        if payload.id_producto:
            from app.modules.inventario.movimientos import asegurar_consumo, bloquear_producto, mover, OperacionInventario
            reg = scoped_query(db, Registro).filter_by(id_factura=factura.id_factura).first()
            if reg:
                total = db.query(func.sum(DetalleFactura.cantidad)).filter_by(id_factura=factura.id_factura, id_producto=payload.id_producto).scalar()
                mov = asegurar_consumo(db, reg.id_registro, payload.id_producto, int(total), "DETALLE_FACTURA", db.info.get("actor").id_usuario if db.info.get("actor") else None)
            else:
                mov = mover(db, bloquear_producto(db, payload.id_producto), -cantidad, "DETALLE_FACTURA", db.info.get("actor").id_usuario if db.info.get("actor") else None, motivo=f"Factura #{factura.id_factura}, detalle #{nuevo.id_detalle}")
            db.add(OperacionInventario(clave=f"detalle:{nuevo.id_detalle}", huella="detalle", resultado={"id_movimiento": mov.id_movimiento if mov else None, "id_factura": factura.id_factura}))
        db.flush()
        factura.costo_total = round(float(db.query(func.coalesce(func.sum(DetalleFactura.subtotal), 0)).filter_by(id_factura=factura.id_factura).scalar()), 2)
        db.commit()
        db.refresh(nuevo)
        return nuevo

    @staticmethod
    def eliminar(db: Session, id_detalle: int) -> None:
        det = scoped_query(db, DetalleFactura).filter(DetalleFactura.id_detalle == id_detalle).first()
        if not det:
            raise EntityNotFoundError("Detalle de factura", id_detalle)

        if scoped_query(db, Registro).filter(Registro.id_factura == det.id_factura, Registro.monto_pagado > 0).first():
            raise BusinessValidationError("La orden tiene pagos registrados; no se puede alterar el comprobante")
        id_factura = det.id_factura
        if det.id_producto and not scoped_query(db, Registro).filter_by(id_factura=id_factura).first():
            from app.modules.inventario.movimientos import bloquear_producto, mover
            mover(db, bloquear_producto(db, det.id_producto), det.cantidad, "ANULACION_FACTURA", db.info.get("actor").id_usuario if db.info.get("actor") else None, motivo=f"Anulación detalle #{det.id_detalle}")
        db.delete(det)
        db.flush()
        factura = FacturaService.obtener_por_id(db, id_factura)
        factura.costo_total = round(float(db.query(func.coalesce(func.sum(DetalleFactura.subtotal), 0)).filter_by(id_factura=id_factura).scalar()), 2)
        db.commit()


class NotaDeVentaService:
    """
    Gestión de Cobro, Emisión de Nota de Venta interna y Cierre Financiero (Procesos 10, 11, 11.1, 12, 13, 13.1 y 14).
    """

    @staticmethod
    def generar_numero_nota_venta(db: Session) -> str:
        from app.core.documentos import siguiente_numero
        return siguiente_numero(db, NotaDeVenta, "numero_nota_venta", "NV")

    @staticmethod
    def preparar_cobro(db: Session, payload: Any) -> Dict[str, Any]:
        """
        Proceso 10: Preparar el cobro desglosando repuestos usados, mano de obra, horas del mecánico y cálculo de ganancia.
        """
        reg = scoped_query(db, Registro).filter(Registro.id_registro == payload.id_registro).first()
        if not reg:
            raise EntityNotFoundError("Registro / Orden de taller", payload.id_registro)

        from app.modules.taller.flujo import validar_etapa
        validar_etapa(db, reg, "cobro")
        # Si ya existe una nota de venta en PENDIENTE, la reutilizamos o actualizamos
        nota_existente = (
            scoped_query(db, NotaDeVenta)
            .filter(NotaDeVenta.id_registro == payload.id_registro)
            .order_by(NotaDeVenta.id_nota_venta.desc())
            .first()
        )
        if nota_existente and nota_existente.estado_pago in ("PARCIAL", "PAGADO"):
            return nota_existente.to_dict()

        # Datos del cliente y vehículo
        vehiculo = scoped_query(db, Vehiculo).filter(Vehiculo.id_vehiculo == reg.id_vehiculo).first()
        cliente = vehiculo.usuario if vehiculo else None

        cliente_nombre = cliente.nombre_completo if cliente else (reg.descripcion or "Cliente Taller")
        cliente_cedula = cliente.cedula if cliente else None
        cliente_telefono = cliente.telefono if cliente else None
        cliente_correo = cliente.correo if cliente else None
        vehiculo_placa = vehiculo.placa if vehiculo else "S/P"
        vehiculo_desc = f"{vehiculo.marca} {vehiculo.modelo} ({vehiculo.anio})" if vehiculo else "Vehículo"

        # Calcular horas y pago del mecánico (Proceso Fin-6)
        bitacoras = scoped_query(db, BitacoraReparacion).filter(BitacoraReparacion.id_registro == reg.id_registro).all()
        horas_mec = sum(float(b.horas_trabajadas or 0.0) for b in bitacoras)
        tarifa_hora = float(10.0 if payload.tarifa_hora_mecanico is None else payload.tarifa_hora_mecanico)
        pago_mec = round(horas_mec * tarifa_hora, 2)

        # Buscar repuestos y mano de obra del presupuesto aprobado
        presupuesto = (
            scoped_query(db, Presupuesto)
            .filter(Presupuesto.id_registro == reg.id_registro)
            .order_by(Presupuesto.id_presupuesto.desc())
            .first()
        )

        subtotal_rep = 0.0
        subtotal_mo = 0.0
        costo_rep_taller = 0.0
        items_a_cobrar = []

        if presupuesto and presupuesto.items:
            for item in presupuesto.items:
                if str(item.estado_aprobacion).upper() == "APROBADO":
                    cant = float(item.cantidad or 1.0)
                    pu = float(item.precio_unitario or 0.0)
                    subt = round(cant * pu, 2)
                    tipo_it = str(item.tipo_item).upper()

                    costo_u = 0.0
                    if tipo_it == "REPUESTO" and item.id_producto:
                        prod = db.query(Producto).filter(Producto.id_producto == item.id_producto).first()
                        if prod:
                            costo_u = float(prod.costo or 0.0)
                            costo_rep_taller += round(cant * costo_u, 2)
                        subtotal_rep += subt
                    else:
                        subtotal_mo += subt

                    items_a_cobrar.append({
                        "tipo_item": tipo_it,
                        "id_producto": item.id_producto,
                        "descripcion": item.descripcion,
                        "cantidad": cant,
                        "precio_unitario": pu,
                        "subtotal": subt,
                        "costo_unitario": costo_u,
                    })

        # Sumar daños adicionales aprobados (Proceso 7.1)
        danos_aprobados = (
            scoped_query(db, DanoAdicional)
            .filter(DanoAdicional.id_registro == reg.id_registro, DanoAdicional.estado == "APROBADO")
            .all()
        )
        for da in danos_aprobados:
            c = float(da.costo_estimado or 0.0)
            costo_u = 0.0
            if da.id_producto:
                prod = db.query(Producto).filter(Producto.id_producto == da.id_producto).first()
                if prod:
                    costo_u = float(prod.costo or 0.0)
                    costo_rep_taller += costo_u
                subtotal_rep += c
                tipo_it = "REPUESTO"
            else:
                subtotal_mo += c
                tipo_it = "MANO_OBRA"

            items_a_cobrar.append({
                "tipo_item": tipo_it,
                "id_producto": da.id_producto,
                "descripcion": f"[Adicional aprobado]: {da.descripcion}",
                "cantidad": 1.0,
                "precio_unitario": c,
                "subtotal": c,
                "costo_unitario": costo_u,
            })

        # Si no hubo items detallados, cobrar el costo_total registrado en la orden
        if not items_a_cobrar:
            costo_base = float(reg.costo_total or 0.0)
            subtotal_mo = costo_base
            items_a_cobrar.append({
                "tipo_item": "MANO_OBRA",
                "id_producto": None,
                "descripcion": reg.descripcion or "Servicio de reparación automotriz",
                "cantidad": 1.0,
                "precio_unitario": costo_base,
                "subtotal": costo_base,
                "costo_unitario": 0.0,
            })

        descuento = float(payload.descuento or (presupuesto.descuento if presupuesto else 0.0) or 0.0)
        total_cobro = max(0.0, round(subtotal_rep + subtotal_mo - descuento, 2))
        ganancia_neta = max(0.0, round(total_cobro - costo_rep_taller - pago_mec, 2))

        # Crear o actualizar nota de venta
        if nota_existente and nota_existente.estado_pago == "PENDIENTE":
            nota = nota_existente
            # Limpiar items anteriores para recalcular
            nota.items.clear()
        else:
            numero_nv = NotaDeVentaService.generar_numero_nota_venta(db)
            nota = NotaDeVenta(
                numero_nota_venta=numero_nv,
                id_registro=reg.id_registro,
                cliente_nombre=cliente_nombre,
                fecha_emision=datetime.now(),
                estado_pago="PENDIENTE",
            )
            db.add(nota)

        if float(reg.monto_pagado or 0) > total_cobro:
            raise BusinessValidationError("El total no puede ser menor a los pagos registrados")
        reg.costo_total = total_cobro
        nota.cliente_nombre = cliente_nombre
        nota.cliente_cedula = cliente_cedula
        nota.cliente_telefono = cliente_telefono
        nota.cliente_correo = cliente_correo
        nota.vehiculo_placa = vehiculo_placa
        nota.vehiculo_descripcion = vehiculo_desc
        nota.subtotal_repuestos = round(subtotal_rep, 2)
        nota.subtotal_mano_obra = round(subtotal_mo, 2)
        nota.descuento = round(descuento, 2)
        nota.total = total_cobro
        nota.costo_repuestos_taller = round(costo_rep_taller, 2)
        nota.horas_mecanico = round(horas_mec, 2)
        nota.tarifa_hora_mecanico = round(tarifa_hora, 2)
        nota.pago_mecanico = round(pago_mec, 2)
        nota.ganancia_neta_taller = round(ganancia_neta, 2)
        nota.observaciones = payload.observaciones

        amount = float(reg.monto_pagado or 0)
        reg.estado_pago = "PAGADO" if amount > 0 and amount == nota.total else "PARCIAL" if amount else "PENDIENTE"
        nota.estado_pago = reg.estado_pago
        if reg.estado_pago == "PAGADO": nota.fecha_pago = reg.fecha_facturado
        db.flush()

        for it in items_a_cobrar:
            item_db = ItemNotaDeVenta(
                id_nota_venta=nota.id_nota_venta,
                tipo_item=it["tipo_item"],
                id_producto=it["id_producto"],
                descripcion=it["descripcion"],
                cantidad=it["cantidad"],
                precio_unitario=it["precio_unitario"],
                subtotal=it["subtotal"],
                costo_unitario=it["costo_unitario"],
            )
            db.add(item_db)

        db.commit()
        db.refresh(nota)
        return nota.to_dict()

    @staticmethod
    def confirmar_pago(db: Session, id_nota_venta: int, payload: Any) -> Dict[str, Any]:
        """
        Procesos 11, 11.1, 12, 13, 13.1 y 14:
        - Confirma el pago (Efectivo, Transferencia o Tarjeta).
        - Si está incompleto, retiene la orden (Proceso 11.1).
        - Emite Nota de Venta formal (Proceso 12: pago confirmado).
        - Descuenta repuestos de bodega y Kardex (Proceso 13 y 13.1).
        - Cierra finanzas y calcula la ganancia (Proceso 14).
        """
        nota = scoped_query(db, NotaDeVenta).filter(NotaDeVenta.id_nota_venta == id_nota_venta).first()
        if not nota:
            raise EntityNotFoundError("Nota de Venta", id_nota_venta)

        if nota.estado_pago == "PAGADO":
            raise BusinessValidationError("La nota de venta ya fue pagada")
        from app.modules.taller.pagos import registrar_abono
        reg = scoped_query(db, Registro).filter(Registro.id_registro == nota.id_registro).with_for_update(of=Registro).first()
        if not reg:
            raise EntityNotFoundError("Orden", nota.id_registro)
        db.refresh(nota)
        if nota.estado_pago == "PAGADO":
            raise BusinessValidationError("La nota de venta ya fue pagada")
        reg.costo_total = nota.total
        monto = float(payload.monto_recibido or 0.0)

        registrar_abono(db, reg, monto, payload.metodo_pago or "EFECTIVO", payload.id_usuario_cajero, payload.numero_referencia, payload.id_operacion)
        if reg.estado_pago == "PARCIAL":
            nota.estado_pago = "PARCIAL"
            db.commit()
            return {"exito": True, "estado_pago": "PARCIAL", "estado_orden": reg.estado,
                    "monto_pagado": reg.monto_pagado, "saldo_pendiente": round(nota.total - reg.monto_pagado, 2),
                    "nota_de_venta": nota.to_dict(), "mensaje": "Abono registrado; queda saldo pendiente"}

        ahora = datetime.now()
        nota.estado_pago = "PAGADO"
        nota.metodo_pago = (payload.metodo_pago or "EFECTIVO").upper()
        nota.numero_referencia_pago = payload.numero_referencia
        nota.comprobante_url = payload.comprobante_url
        nota.fecha_pago = ahora
        nota.id_usuario_cajero = payload.id_usuario_cajero

        from app.modules.inventario.movimientos import asegurar_consumo
        required = {}
        for item in nota.items:
            if item.tipo_item == "REPUESTO" and item.id_producto:
                required[item.id_producto] = required.get(item.id_producto, 0) + float(item.cantidad)
        alertas_reposicion = []
        for product_id, qty in sorted(required.items()):
            asegurar_consumo(db, nota.id_registro, product_id, qty, "COBRO_NOTA_VENTA", payload.id_usuario_cajero, cerrar_reservas=True)
            prod = db.query(Producto).filter_by(id_producto=product_id).first()
            if prod.alerta_stock_minimo:
                alertas_reposicion.append({"id_producto": product_id, "nombre": prod.nombre, "stock_actual": prod.stock, "stock_minimo": prod.stock_minimo})

        # Actualizar el importe y fecha de cobro sin cambiar el trabajo.
        reg = scoped_query(db, Registro).filter(Registro.id_registro == nota.id_registro).first()
        if reg:
            # El cobro no modifica el estado del trabajo.
            reg.fecha_facturado = ahora
            reg.costo_total = nota.total

        db.commit()
        db.refresh(nota)
        if reg:
            db.refresh(reg)

        return {
            "exito": True,
            "mensaje": f"Pago confirmado exitosamente. Nota de Venta #{nota.numero_nota_venta} emitida.",
            "estado_pago": "PAGADO",
            "estado_orden": reg.estado,
            "nota_de_venta": nota.to_dict(),
            "resumen_financiero": {
                "total_ingreso": nota.total,
                "costo_repuestos": nota.costo_repuestos_taller,
                "pago_mecanico": nota.pago_mecanico,
                "ganancia_neta": nota.ganancia_neta_taller,
            },
            "alertas_stock_minimo": alertas_reposicion,
        }

    @staticmethod
    def obtener_por_id(db: Session, id_nota_venta: int) -> Dict[str, Any]:
        nv = scoped_query(db, NotaDeVenta).filter(NotaDeVenta.id_nota_venta == id_nota_venta).first()
        if not nv:
            raise EntityNotFoundError("Nota de Venta", id_nota_venta)
        return nv.to_dict()

    @staticmethod
    def obtener_por_registro(db: Session, id_registro: int) -> Optional[Dict[str, Any]]:
        nv = (
            scoped_query(db, NotaDeVenta)
            .filter(NotaDeVenta.id_registro == id_registro)
            .order_by(NotaDeVenta.id_nota_venta.desc())
            .first()
        )
        return nv.to_dict() if nv else None

    @staticmethod
    def listar_todas(db: Session, estado_pago: Optional[str] = None) -> List[Dict[str, Any]]:
        query = scoped_query(db, NotaDeVenta)
        if estado_pago:
            query = query.filter(func.upper(NotaDeVenta.estado_pago) == estado_pago.strip().upper())
        notas = query.order_by(NotaDeVenta.fecha_emision.desc()).all()
        return [n.to_dict() for n in notas]

    @staticmethod
    def reporte_financiero_global(
        db: Session,
        fecha_inicio: Optional[str] = None,
        fecha_fin: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Proceso 14 / Proceso Fin-8: Reporte de ingresos, costos de repuestos, pagos a mecánicos y utilidades netas.
        Soporta filtro opcional por rango de fechas (fecha_inicio, fecha_fin).
        """
        from datetime import date
        fi = ff = None
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

        q = scoped_query(db, NotaDeVenta).filter(NotaDeVenta.estado_pago == "PAGADO")
        if fi:
            q = q.filter(NotaDeVenta.fecha_pago >= datetime.combine(fi, datetime.min.time()))
        if ff:
            q = q.filter(NotaDeVenta.fecha_pago <= datetime.combine(ff, datetime.max.time()))
        notas_pagadas = q.all()
        total_ingresos = sum(float(n.total or 0.0) for n in notas_pagadas)
        total_costo_repuestos = sum(float(n.costo_repuestos_taller or 0.0) for n in notas_pagadas)
        total_pago_mecanicos = sum(float(n.pago_mecanico or 0.0) for n in notas_pagadas)
        ganancia_neta_total = sum(float(n.ganancia_neta_taller or 0.0) for n in notas_pagadas)

        return {
            "fecha_inicio": fi.isoformat() if fi else None,
            "fecha_fin": ff.isoformat() if ff else None,
            "total_notas_cobradas": len(notas_pagadas),
            "ingresos_totales": round(total_ingresos, 2),
            "costo_total_repuestos": round(total_costo_repuestos, 2),
            "pago_total_mecanicos": round(total_pago_mecanicos, 2),
            "ganancia_neta_taller": round(ganancia_neta_total, 2),
        }


