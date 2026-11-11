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
        return db.query(Factura).order_by(Factura.id_factura.desc()).all()

    @staticmethod
    def obtener_por_id(db: Session, id_factura: int) -> Factura:
        factura = db.query(Factura).filter(Factura.id_factura == id_factura).first()
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
        detalles = db.query(DetalleFactura).filter(DetalleFactura.id_factura == id_factura).all()
        total = sum(float(d.subtotal or 0.0) for d in detalles)
        factura.costo_total = round(max(0.0, total), 2)
        db.commit()
        db.refresh(factura)
        return factura

    @staticmethod
    def eliminar(db: Session, id_factura: int) -> None:
        factura = FacturaService.obtener_por_id(db, id_factura)
        # Restaurar stock de los productos asociados antes de eliminar la factura
        detalles = db.query(DetalleFactura).filter(DetalleFactura.id_factura == id_factura).all()
        for det in detalles:
            if det.id_producto and det.cantidad > 0:
                prod = db.query(Producto).filter(Producto.id_producto == det.id_producto).first()
                if prod:
                    prod.stock = (prod.stock or 0) + det.cantidad
                    prod.fecha_modificacion = datetime.now()
        db.delete(factura)
        db.commit()


class DetalleFacturaService:
    @staticmethod
    def listar_por_factura(db: Session, id_factura: int) -> List[DetalleFactura]:
        return (
            db.query(DetalleFactura)
            .filter(DetalleFactura.id_factura == id_factura)
            .order_by(DetalleFactura.id_detalle.asc())
            .all()
        )

    @staticmethod
    def crear(db: Session, payload: Any) -> DetalleFactura:
        factura = FacturaService.obtener_por_id(db, payload.id_factura)
        cantidad = int(payload.cantidad or 1)
        if cantidad <= 0:
            raise BusinessValidationError("La cantidad debe ser mayor a cero")

        descripcion = (payload.descripcion or "").strip()
        es_descuento = descripcion.startswith("[DESC")

        if payload.id_producto:
            prod = db.query(Producto).filter(Producto.id_producto == payload.id_producto).first()
            if not prod:
                raise EntityNotFoundError("Producto", payload.id_producto)
            if prod.stock < cantidad:
                raise BusinessValidationError(
                    f"Stock insuficiente para '{prod.nombre}'. Disponible: {prod.stock}, requerido: {cantidad}"
                )
            prod.stock -= cantidad
            prod.fecha_modificacion = datetime.now()
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
        db.commit()
        db.refresh(nuevo)

        FacturaService.recalcular_total(db, factura.id_factura)
        return nuevo

    @staticmethod
    def eliminar(db: Session, id_detalle: int) -> None:
        det = db.query(DetalleFactura).filter(DetalleFactura.id_detalle == id_detalle).first()
        if not det:
            raise EntityNotFoundError("Detalle de factura", id_detalle)

        id_factura = det.id_factura
        if det.id_producto and det.cantidad > 0:
            prod = db.query(Producto).filter(Producto.id_producto == det.id_producto).first()
            if prod:
                prod.stock = (prod.stock or 0) + det.cantidad
                prod.fecha_modificacion = datetime.now()

        db.delete(det)
        db.commit()
        FacturaService.recalcular_total(db, id_factura)


class NotaDeVentaService:
    """
    Gestión de Cobro, Emisión de Nota de Venta interna y Cierre Financiero (Procesos 10, 11, 11.1, 12, 13, 13.1 y 14).
    """

    @staticmethod
    def generar_numero_nota_venta(db: Session) -> str:
        anio = datetime.now().year
        prefijo = f"NV-{anio}-"
        total = db.query(NotaDeVenta).filter(NotaDeVenta.numero_nota_venta.like(f"{prefijo}%")).count()
        return f"{prefijo}{total + 1:04d}"

    @staticmethod
    def preparar_cobro(db: Session, payload: Any) -> Dict[str, Any]:
        """
        Proceso 10: Preparar el cobro desglosando repuestos usados, mano de obra, horas del mecánico y cálculo de ganancia.
        """
        reg = db.query(Registro).filter(Registro.id_registro == payload.id_registro).first()
        if not reg:
            raise EntityNotFoundError("Registro / Orden de taller", payload.id_registro)

        # Si ya existe una nota de venta en PENDIENTE_PAGO, la reutilizamos o actualizamos
        nota_existente = (
            db.query(NotaDeVenta)
            .filter(NotaDeVenta.id_registro == payload.id_registro)
            .order_by(NotaDeVenta.id_nota_venta.desc())
            .first()
        )
        if nota_existente and nota_existente.estado_pago == "PAGADO":
            return nota_existente.to_dict()

        # Datos del cliente y vehículo
        vehiculo = db.query(Vehiculo).filter(Vehiculo.id_vehiculo == reg.id_vehiculo).first()
        cliente = vehiculo.usuario if vehiculo else None

        cliente_nombre = cliente.nombre_completo if cliente else (reg.descripcion or "Cliente Taller")
        cliente_cedula = cliente.cedula if cliente else None
        cliente_telefono = cliente.telefono if cliente else None
        cliente_correo = cliente.correo if cliente else None
        vehiculo_placa = vehiculo.placa if vehiculo else "S/P"
        vehiculo_desc = f"{vehiculo.marca} {vehiculo.modelo} ({vehiculo.anio})" if vehiculo else "Vehículo"

        # Calcular horas y pago del mecánico (Proceso Fin-6)
        bitacoras = db.query(BitacoraReparacion).filter(BitacoraReparacion.id_registro == reg.id_registro).all()
        horas_mec = sum(float(b.horas_trabajadas or 0.0) for b in bitacoras)
        tarifa_hora = float(payload.tarifa_hora_mecanico or 10.0)
        pago_mec = round(horas_mec * tarifa_hora, 2)

        # Buscar repuestos y mano de obra del presupuesto aprobado
        presupuesto = (
            db.query(Presupuesto)
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
            db.query(DanoAdicional)
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
        if nota_existente and nota_existente.estado_pago == "PENDIENTE_PAGO":
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
                estado_pago="PENDIENTE_PAGO",
            )
            db.add(nota)

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
        - Emite Nota de Venta formal (Proceso 12: Estado 7 PAGADO).
        - Descuenta repuestos de bodega y Kardex (Proceso 13 y 13.1).
        - Cierra finanzas y calcula la ganancia (Proceso 14).
        """
        nota = db.query(NotaDeVenta).filter(NotaDeVenta.id_nota_venta == id_nota_venta).first()
        if not nota:
            raise EntityNotFoundError("Nota de Venta", id_nota_venta)

        monto = float(payload.monto_recibido or 0.0)

        # Proceso 11.1: Pago incompleto o rechazado -> Mantener orden pendiente y retener vehículo
        if monto < nota.total:
            faltante = round(nota.total - monto, 2)
            raise BusinessValidationError(
                f"Proceso 11.1: El monto recibido (${monto}) es menor al total de la Nota de Venta (${nota.total}). "
                f"Faltan ${faltante}. La orden permanece en PENDIENTE DE PAGO y el vehículo no puede ser entregado."
            )

        ahora = datetime.now()
        nota.estado_pago = "PAGADO"
        nota.metodo_pago = (payload.metodo_pago or "EFECTIVO").upper()
        nota.numero_referencia_pago = payload.numero_referencia
        nota.comprobante_url = payload.comprobante_url
        nota.fecha_pago = ahora
        nota.id_usuario_cajero = payload.id_usuario_cajero

        # Proceso 13: Descontar repuestos del inventario físico y Kardex
        alertas_reposicion = []
        for it in nota.items:
            if it.tipo_item == "REPUESTO" and it.id_producto:
                prod = db.query(Producto).filter(Producto.id_producto == it.id_producto).first()
                if prod:
                    cant = int(it.cantidad or 1)
                    stock_ant = prod.stock

                    # Revisar si existía reserva para liberarla / pasar a retirado
                    reserva = (
                        db.query(ReservaRepuesto)
                        .filter(
                            ReservaRepuesto.id_registro == nota.id_registro,
                            ReservaRepuesto.id_producto == prod.id_producto,
                            ReservaRepuesto.estado == "RESERVADO",
                        )
                        .first()
                    )
                    if reserva:
                        reserva.estado = "RETIRADO"
                        reserva.fecha_retiro = ahora
                    prod.stock_reservado = max(0, prod.stock_reservado - cant)

                    prod.stock = max(0, prod.stock - cant)
                    stock_nuev = prod.stock

                    # Movimiento de salida definitiva en Kardex
                    mov = MovimientoKardex(
                        id_producto=prod.id_producto,
                        tipo_movimiento="SALIDA",
                        origen="COBRO_NOTA_VENTA",
                        cantidad=cant,
                        stock_anterior=stock_ant,
                        stock_nuevo=stock_nuev,
                        costo_unitario=float(prod.costo or 0.0),
                        precio_unitario=float(it.precio_unitario or 0.0),
                        codigo_escaneado=prod.codigo_barras or prod.codigo_personal,
                        id_registro=nota.id_registro,
                        id_usuario=payload.id_usuario_cajero,
                        motivo=f"Salida por liquidación y cobro de Nota de Venta #{nota.numero_nota_venta}",
                        fecha=ahora,
                    )
                    db.add(mov)

                    # Proceso 13.1: Alerta si quedó en stock mínimo o por debajo
                    if prod.alerta_stock_minimo:
                        alertas_reposicion.append({
                            "id_producto": prod.id_producto,
                            "nombre": prod.nombre,
                            "stock_actual": prod.stock,
                            "stock_minimo": prod.stock_minimo,
                            "mensaje": f"⚠️ ALERTA: '{prod.nombre}' requiere reposición urgente (Stock: {prod.stock}).",
                        })

        # Actualizar orden de taller (Registro) al Estado 7: PAGADO
        reg = db.query(Registro).filter(Registro.id_registro == nota.id_registro).first()
        if reg:
            reg.estado = 7  # Estado 7: PAGADO según el diagrama de flujo
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
            "estado_orden": 7,  # Estado 7: PAGADO
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
        nv = db.query(NotaDeVenta).filter(NotaDeVenta.id_nota_venta == id_nota_venta).first()
        if not nv:
            raise EntityNotFoundError("Nota de Venta", id_nota_venta)
        return nv.to_dict()

    @staticmethod
    def obtener_por_registro(db: Session, id_registro: int) -> Optional[Dict[str, Any]]:
        nv = (
            db.query(NotaDeVenta)
            .filter(NotaDeVenta.id_registro == id_registro)
            .order_by(NotaDeVenta.id_nota_venta.desc())
            .first()
        )
        return nv.to_dict() if nv else None

    @staticmethod
    def listar_todas(db: Session, estado_pago: Optional[str] = None) -> List[Dict[str, Any]]:
        query = db.query(NotaDeVenta)
        if estado_pago:
            query = query.filter(func.upper(NotaDeVenta.estado_pago) == estado_pago.strip().upper())
        notas = query.order_by(NotaDeVenta.fecha_emision.desc()).all()
        return [n.to_dict() for n in notas]

    @staticmethod
    def reporte_financiero_global(db: Session) -> Dict[str, Any]:
        """
        Proceso 14 / Proceso Fin-8: Reporte de ingresos, costos de repuestos, pagos a mecánicos y utilidades netas.
        """
        notas_pagadas = db.query(NotaDeVenta).filter(NotaDeVenta.estado_pago == "PAGADO").all()
        total_ingresos = sum(float(n.total or 0.0) for n in notas_pagadas)
        total_costo_repuestos = sum(float(n.costo_repuestos_taller or 0.0) for n in notas_pagadas)
        total_pago_mecanicos = sum(float(n.pago_mecanico or 0.0) for n in notas_pagadas)
        ganancia_neta_total = sum(float(n.ganancia_neta_taller or 0.0) for n in notas_pagadas)

        return {
            "total_notas_cobradas": len(notas_pagadas),
            "ingresos_totales": round(total_ingresos, 2),
            "costo_total_repuestos": round(total_costo_repuestos, 2),
            "pago_total_mecanicos": round(total_pago_mecanicos, 2),
            "ganancia_neta_taller": round(ganancia_neta_total, 2),
        }


