"""Una sola vía para movimientos físicos; el cobro solo completa consumos faltantes."""
import hashlib
import json
from datetime import datetime
from sqlalchemy import Column, String, JSON, select, update, func, case
from app.core.database import Base
from app.core.access_scope import scoped_query
from app.core.exceptions import BusinessValidationError, EntityNotFoundError, ConflictError
from app.modules.inventario.models import Producto, MovimientoKardex, ReservaRepuesto
from app.modules.taller.models import Registro

class OperacionInventario(Base):
    __tablename__ = "operaciones_inventario"
    clave = Column(String(160), primary_key=True)
    huella = Column(String(64), nullable=False)
    resultado = Column(JSON, nullable=False)


def bloquear_orden(db, id_registro):
    if id_registro is None:
        return None
    reg = scoped_query(db, Registro).filter(Registro.id_registro == id_registro).with_for_update(of=Registro).first()
    if not reg:
        raise EntityNotFoundError("Orden", id_registro)
    return reg


def bloquear_producto(db, id_producto):
    prod = db.query(Producto).filter(Producto.id_producto == id_producto).with_for_update(of=Producto).populate_existing().first()
    if not prod:
        raise EntityNotFoundError("Producto", id_producto)
    return prod


def mover(db, prod, delta, origen, usuario=None, orden=None, motivo=None, **extras):
    if not isinstance(delta, int) or not delta:
        raise BusinessValidationError("La cantidad del movimiento debe ser un entero distinto de cero")
    before = int(prod.stock)
    condition = Producto.id_producto == prod.id_producto
    if delta < 0:
        condition = condition & (Producto.stock - Producto.stock_reservado >= -delta)
    result = db.execute(update(Producto).where(condition).values(stock=Producto.stock + delta, fecha_modificacion=datetime.now()).execution_options(synchronize_session=False))
    if result.rowcount != 1:
        raise BusinessValidationError("Stock insuficiente; hay unidades reservadas o consumidas por otra operación")
    db.refresh(prod)
    mov = MovimientoKardex(id_producto=prod.id_producto, tipo_movimiento="ENTRADA" if delta > 0 else "SALIDA", cantidad=abs(delta), stock_anterior=prod.stock - delta, stock_nuevo=prod.stock,
        origen=origen, id_usuario=usuario, id_registro=orden, motivo=motivo, codigo_escaneado=prod.codigo_barras or prod.codigo_personal,
        costo_unitario=float(prod.costo or 0), precio_unitario=float(prod.pvp or 0), **extras)
    db.add(mov)
    db.flush()
    return mov


def consumo_neto(db, orden, producto):
    value = db.query(func.coalesce(func.sum(case((MovimientoKardex.tipo_movimiento == "SALIDA", MovimientoKardex.cantidad), (MovimientoKardex.tipo_movimiento == "ENTRADA", -MovimientoKardex.cantidad), else_=0)), 0)).filter(MovimientoKardex.id_registro == orden, MovimientoKardex.id_producto == producto).scalar()
    return max(0, int(value))


def asegurar_consumo(db, orden, producto, cantidad, origen, usuario=None, cerrar_reservas=False):
    if cantidad <= 0 or int(cantidad) != cantidad:
        raise BusinessValidationError("Los repuestos de inventario requieren cantidades enteras positivas")
    bloquear_orden(db, orden)
    prod = bloquear_producto(db, producto)
    if cerrar_reservas:
        pending = db.query(ReservaRepuesto).filter_by(id_registro=orden, id_producto=producto, estado="RESERVADO").order_by(ReservaRepuesto.id_reserva).all()
        retired = int(db.query(func.coalesce(func.sum(ReservaRepuesto.cantidad), 0)).filter_by(id_registro=orden, id_producto=producto, estado="RETIRADO").scalar())
        for reserva in pending:
            if retired + reserva.cantidad > cantidad:
                raise BusinessValidationError("Hay reservas superiores a los repuestos aprobados; libere el excedente antes de cobrar")
            if prod.stock_reservado < reserva.cantidad:
                raise BusinessValidationError("La reserva necesita conciliación de inventario")
            prod.stock_reservado -= reserva.cantidad
            reserva.estado = "RETIRADO"
            reserva.fecha_retiro = datetime.now()
            retired += reserva.cantidad
        db.flush()
    difference = max(0, int(cantidad) - consumo_neto(db, orden, producto))
    return mover(db, prod, -difference, origen, usuario, orden, "Consumo único de repuestos de la orden") if difference else None


def cache_key(db, payload, kind):
    actor = db.info.get("actor")
    key = getattr(payload, "id_operacion", None)
    if not key:
        return None, None
    data = payload.model_dump(exclude={"id_operacion", "id_usuario"})
    fingerprint = hashlib.sha256(json.dumps({"tipo": kind, **data}, sort_keys=True, default=str).encode()).hexdigest()
    return f"mov:{actor.id_usuario if actor else payload.id_usuario or 0}:{key}", fingerprint


def cached(db, key, fingerprint):
    previous = db.get(OperacionInventario, key) if key else None
    if previous:
        if previous.huella != fingerprint:
            raise ConflictError("La operación ya existe con otros datos")
        return previous.resultado
    return None


def registrar_escaneo(db, payload, entrada=True):
    from app.modules.inventario.service import KardexService
    key, fingerprint = cache_key(db, payload, "ENTRADA" if entrada else "SALIDA")
    previous = cached(db, key, fingerprint)
    if previous is not None:
        return previous
    reg = bloquear_orden(db, getattr(payload, "id_registro", None))
    if reg and reg.estado == 3:
        raise BusinessValidationError("La orden ya fue entregada")
    codigo = payload.codigo_barras.strip()
    if not codigo:
        raise BusinessValidationError("Debe ingresar un código de barras")
    prod = KardexService.buscar_por_codigo(db, codigo)
    if not prod and entrada and payload.crear_si_no_existe and payload.nombre:
        from app.modules.inventario.models import Categoria
        category = db.query(Categoria).filter_by(id_categoria=payload.id_categoria).first() if payload.id_categoria else db.query(Categoria).first()
        if not category:
            category = Categoria(nombre="Repuestos Generales")
            db.add(category); db.flush()
        prod = Producto(nombre=payload.nombre.strip(), codigo_personal=codigo, codigo_barras=codigo, id_categoria=category.id_categoria, stock=0, stock_reservado=0,
            costo=payload.costo_unitario or 0, pvp=payload.precio_venta or 0, marca=payload.marca, stock_minimo=payload.stock_minimo if payload.stock_minimo is not None else 2)
        db.add(prod); db.flush()
    if not prod:
        raise EntityNotFoundError("Producto con código " + codigo)
    prod = bloquear_producto(db, prod.id_producto)
    previous = cached(db, key, fingerprint)
    if previous is not None:
        return previous
    if entrada and reg:
        if payload.origen != "DEVOLUCION_TALLER":
            raise BusinessValidationError("Las entradas vinculadas a órdenes deben registrarse como devolución")
        if payload.cantidad > consumo_neto(db, reg.id_registro, prod.id_producto):
            raise BusinessValidationError("La devolución supera el consumo registrado para esta orden")
    if entrada:
        if payload.costo_unitario is not None: prod.costo = payload.costo_unitario
        if payload.precio_venta is not None: prod.pvp = payload.precio_venta
        if payload.proveedor: prod.proveedor = payload.proveedor
        db.flush()
    mov = mover(db, prod, payload.cantidad if entrada else -payload.cantidad, payload.origen or ("COMPRA_PROVEEDOR" if entrada else "TALLER_ORDEN"), payload.id_usuario, getattr(payload, "id_registro", None), payload.motivo,
        **({"numero_factura_proveedor": payload.numero_factura_proveedor, "comprobante_url": payload.comprobante_url} if entrada else {}))
    response = {"exito": True, "tipo": mov.tipo_movimiento, "mensaje": "Movimiento registrado", "producto": prod.to_dict(), "movimiento": mov.to_dict(),
        "stock_anterior": mov.stock_anterior, "stock_nuevo": mov.stock_nuevo, "alerta_stock_minimo": prod.alerta_stock_minimo, "mensaje_alerta": "ALERTA DE STOCK: se alcanzó el mínimo" if prod.alerta_stock_minimo else None}
    if key:
        db.add(OperacionInventario(clave=key, huella=fingerprint, resultado=response))
    db.commit()
    return response


def retirar_reserva(db, reserva_id, usuario):
    reserva = scoped_query(db, ReservaRepuesto).filter_by(id_reserva=reserva_id).first()
    if not reserva: raise EntityNotFoundError("Reserva", reserva_id)
    reg = bloquear_orden(db, reserva.id_registro)
    reserva = scoped_query(db, ReservaRepuesto).filter_by(id_reserva=reserva_id).with_for_update(of=ReservaRepuesto).populate_existing().first()
    if reserva.estado == "RETIRADO":
        return {"exito": True, "mensaje": "El consumo ya estaba registrado", "reserva": reserva.to_dict(), "producto": bloquear_producto(db, reserva.id_producto).to_dict(), "movimiento_kardex": None}
    if reserva.estado != "RESERVADO" or reg.estado == 3:
        raise BusinessValidationError("La reserva no está disponible para retirar")
    prod = bloquear_producto(db, reserva.id_producto)
    if prod.stock_reservado < reserva.cantidad:
        raise BusinessValidationError("La reserva necesita conciliación de inventario")
    prod.stock_reservado -= reserva.cantidad
    reserva.estado = "RETIRADO"; reserva.fecha_retiro = datetime.now(); reserva.id_usuario = usuario
    db.flush()
    total = int(db.query(func.sum(ReservaRepuesto.cantidad)).filter_by(id_registro=reserva.id_registro, id_producto=reserva.id_producto, estado="RETIRADO").scalar())
    mov = asegurar_consumo(db, reserva.id_registro, reserva.id_producto, total, "RETIRO_INSTALACION_TALLER", usuario)
    db.commit()
    return {"exito": True, "mensaje": "Consumo registrado" if mov else "Consumo ya registrado; reserva conciliada sin otra salida", "reserva": reserva.to_dict(), "producto": prod.to_dict(), "movimiento_kardex": mov.to_dict() if mov else None}


def importar_consumos_anteriores(db):
    from app.modules.facturacion.models import DetalleFactura
    if db.get(OperacionInventario, "migracion:consumos-v1"):
        return
    for detail in db.query(DetalleFactura).filter(DetalleFactura.id_producto.is_not(None)).order_by(DetalleFactura.id_detalle).all():
        if db.get(OperacionInventario, f"detalle:{detail.id_detalle}"):
            continue
        prod = db.query(Producto).filter_by(id_producto=detail.id_producto).first()
        if not prod: continue
        reg = db.query(Registro).filter_by(id_factura=detail.id_factura).first()
        difference = detail.cantidad
        if reg:
            billed = db.query(func.sum(DetalleFactura.cantidad)).filter(DetalleFactura.id_factura == detail.id_factura, DetalleFactura.id_producto == detail.id_producto, DetalleFactura.id_detalle <= detail.id_detalle).scalar()
            difference = max(0, int(billed) - consumo_neto(db, reg.id_registro, detail.id_producto))
        mov = None
        if difference:
            mov = MovimientoKardex(id_producto=prod.id_producto, tipo_movimiento="SALIDA", origen="LEGADO_CONCILIACION", cantidad=difference, stock_anterior=prod.stock, stock_nuevo=prod.stock, id_registro=reg.id_registro if reg else None, costo_unitario=prod.costo, precio_unitario=prod.pvp, motivo="Consumo de factura antigua importado sin modificar stock físico")
            db.add(mov); db.flush()
        db.add(OperacionInventario(clave=f"detalle:{detail.id_detalle}", huella="detalle", resultado={"id_movimiento": mov.id_movimiento if mov else None, "id_factura": detail.id_factura}))
    db.add(OperacionInventario(clave="migracion:consumos-v1", huella="v1", resultado={}))
    db.commit()
