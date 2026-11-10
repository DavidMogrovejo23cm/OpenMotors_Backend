from datetime import datetime
from typing import List, Any
from sqlalchemy.orm import Session

from app.core.exceptions import EntityNotFoundError, BusinessValidationError
from app.modules.facturacion.models import Factura, DetalleFactura
from app.modules.inventario.models import Producto


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

