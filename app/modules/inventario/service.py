from datetime import date, datetime
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.exceptions import EntityNotFoundError, BusinessValidationError, ConflictError
from app.modules.inventario.models import Categoria, Producto, ContactoProveedor
from app.shared.storage_service import storage_service
from app.shared.email_service import email_service


class CategoriaService:
    @staticmethod
    def listar_todas(db: Session) -> List[Categoria]:
        return db.query(Categoria).order_by(Categoria.id_categoria.asc()).all()

    @staticmethod
    def obtener_por_id(db: Session, id_categoria: int) -> Categoria:
        cat = db.query(Categoria).filter(Categoria.id_categoria == id_categoria).first()
        if not cat:
            raise EntityNotFoundError("Categoría", id_categoria)
        return cat

    @staticmethod
    def crear(db: Session, payload: Any) -> Categoria:
        nueva = Categoria(
            nombre=payload.nombre.strip(),
            descripcion=payload.descripcion,
        )
        db.add(nueva)
        db.commit()
        db.refresh(nueva)
        return nueva

    @staticmethod
    def actualizar(db: Session, id_categoria: int, payload: Any) -> Categoria:
        cat = CategoriaService.obtener_por_id(db, id_categoria)
        cat.nombre = payload.nombre.strip()
        cat.descripcion = payload.descripcion
        db.commit()
        db.refresh(cat)
        return cat

    @staticmethod
    def eliminar(db: Session, id_categoria: int) -> None:
        cat = CategoriaService.obtener_por_id(db, id_categoria)
        db.delete(cat)
        db.commit()


class ProductoService:
    @staticmethod
    def listar_todos(db: Session) -> List[Producto]:
        return db.query(Producto).order_by(Producto.id_producto.asc()).all()

    @staticmethod
    def obtener_por_id(db: Session, id_producto: int) -> Producto:
        prod = db.query(Producto).filter(Producto.id_producto == id_producto).first()
        if not prod:
            raise EntityNotFoundError("Producto", id_producto)
        return prod

    @staticmethod
    def crear(db: Session, payload: Any) -> Producto:
        codigo_pers = (payload.codigo_personal or "").strip()
        if not codigo_pers:
            raise BusinessValidationError("El código personal del producto es obligatorio")

        if db.query(Producto).filter(func.lower(Producto.codigo_personal) == codigo_pers.lower()).first():
            raise ConflictError(f"Ya existe un producto con el código personal '{codigo_pers}'")

        nuevo = Producto(
            codigo_proveedor=(payload.codigo_proveedor or "PROV-001").strip(),
            codigo_distribuidor=(payload.codigo_distribuidor or "DIST-001").strip(),
            codigo_personal=codigo_pers,
            nombre=(payload.nombre or "").strip(),
            descripcion=(payload.descripcion or "").strip(),
            costo=float(payload.costo or 0.0),
            pvp=float(payload.pvp or 0.0),
            stock=int(payload.stock or 0),
            fecha_registro=date.today(),
            fecha_modificacion=datetime.now(),
            id_categoria=payload.id_categoria,
            ruta_imagenproductos=payload.ruta_imagenproductos,
        )
        db.add(nuevo)
        db.commit()
        db.refresh(nuevo)
        return nuevo

    @staticmethod
    def actualizar(db: Session, id_producto: int, payload: Any) -> Producto:
        prod = ProductoService.obtener_por_id(db, id_producto)

        if payload.codigo_personal is not None and payload.codigo_personal.strip() != prod.codigo_personal:
            nuevo_cod = payload.codigo_personal.strip()
            choque = (
                db.query(Producto)
                .filter(
                    func.lower(Producto.codigo_personal) == nuevo_cod.lower(),
                    Producto.id_producto != id_producto,
                )
                .first()
            )
            if choque:
                raise ConflictError(f"Ya existe otro producto con el código personal '{nuevo_cod}'")
            prod.codigo_personal = nuevo_cod

        if payload.codigo_proveedor is not None:
            prod.codigo_proveedor = payload.codigo_proveedor.strip()
        if payload.codigo_distribuidor is not None:
            prod.codigo_distribuidor = payload.codigo_distribuidor.strip()
        if payload.nombre is not None:
            prod.nombre = payload.nombre.strip()
        if payload.descripcion is not None:
            prod.descripcion = payload.descripcion.strip()
        if payload.costo is not None:
            prod.costo = float(payload.costo)
        if payload.pvp is not None:
            prod.pvp = float(payload.pvp)
        if payload.stock is not None:
            prod.stock = int(payload.stock)
        if payload.id_categoria is not None:
            prod.id_categoria = payload.id_categoria

        if payload.ruta_imagenproductos is not None:
            if (
                prod.ruta_imagenproductos
                and prod.ruta_imagenproductos != payload.ruta_imagenproductos
                and "supabase.co" in prod.ruta_imagenproductos
            ):
                storage_service.delete_file(prod.ruta_imagenproductos)
            prod.ruta_imagenproductos = payload.ruta_imagenproductos

        prod.fecha_modificacion = datetime.now()
        db.commit()
        db.refresh(prod)
        return prod

    @staticmethod
    def eliminar(db: Session, id_producto: int) -> None:
        prod = ProductoService.obtener_por_id(db, id_producto)
        if prod.ruta_imagenproductos and "supabase.co" in prod.ruta_imagenproductos:
            storage_service.delete_file(prod.ruta_imagenproductos)
        db.delete(prod)
        db.commit()

    @staticmethod
    def eliminar_varios(db: Session, ids: List[int]) -> None:
        for id_prod in ids:
            prod = db.query(Producto).filter(Producto.id_producto == id_prod).first()
            if prod:
                if prod.ruta_imagenproductos and "supabase.co" in prod.ruta_imagenproductos:
                    storage_service.delete_file(prod.ruta_imagenproductos)
                db.delete(prod)
        db.commit()

    @staticmethod
    def venta_directa(db: Session, payload: Any) -> Dict[str, Any]:
        from app.modules.facturacion.models import Factura, DetalleFactura

        prod = ProductoService.obtener_por_id(db, payload.id_producto)
        cantidad = int(payload.cantidad or 1)
        if cantidad <= 0:
            raise BusinessValidationError("La cantidad debe ser mayor a cero")
        if prod.stock < cantidad:
            raise BusinessValidationError(
                f"Stock insuficiente para {prod.nombre}. Disponible: {prod.stock}, solicitado: {cantidad}"
            )

        precio_unit = float(payload.precio_unitario) if payload.precio_unitario is not None else float(prod.pvp)
        subtotal = round(cantidad * precio_unit, 2)

        # Descontar stock
        prod.stock -= cantidad
        prod.fecha_modificacion = datetime.now()

        # Crear Factura con origen INVENTARIO
        nueva_factura = Factura(
            fecha_emision=datetime.now(),
            id_usuario=payload.id_usuario,
            costo_total=subtotal,
            cliente_nombre=payload.cliente_nombre or "Consumidor Final",
            cliente_cedula=payload.cliente_cedula,
            cliente_telefono=payload.cliente_telefono,
            cliente_correo=payload.cliente_correo,
            cliente_direccion=payload.cliente_direccion,
            cliente_tipo=payload.cliente_tipo or ("SISTEMA" if payload.id_usuario else "EXTERNO"),
            origen_venta="INVENTARIO",
        )
        db.add(nueva_factura)
        db.flush()

        detalle = DetalleFactura(
            id_factura=nueva_factura.id_factura,
            id_producto=prod.id_producto,
            descripcion=prod.nombre,
            cantidad=cantidad,
            precio_unitario=precio_unit,
            subtotal=subtotal,
        )
        db.add(detalle)
        db.commit()
        db.refresh(prod)
        db.refresh(nueva_factura)

        return {
            "producto": prod.to_dict(),
            "id_factura": nueva_factura.id_factura,
            "total": subtotal,
        }

    @staticmethod
    def enviar_comprobante_venta(payload: Any) -> None:
        if not payload.correo or not payload.correo.strip():
            raise BusinessValidationError("El correo del destinatario es obligatorio")

        items_dict = [
            {
                "nombre": i.nombre,
                "cantidad": i.cantidad,
                "precio_unitario": i.precio_unitario,
                "subtotal": i.subtotal or round(i.cantidad * i.precio_unitario, 2),
            }
            for i in (payload.items or [])
        ]
        email_service.enviar_comprobante_venta_directa(
            destinatario=payload.correo.strip(),
            nombre_cliente=payload.nombre_cliente or "Consumidor Final",
            cedula=payload.cedula,
            telefono=payload.telefono,
            direccion=payload.direccion,
            id_factura=payload.id_factura,
            items=items_dict,
            total=payload.total,
        )


class ContactoProveedorService:
    @staticmethod
    def listar_todos(db: Session) -> List[ContactoProveedor]:
        return db.query(ContactoProveedor).order_by(ContactoProveedor.codigo.asc()).all()

    @staticmethod
    def guardar_o_actualizar(db: Session, codigo: str, payload: Any) -> ContactoProveedor:
        cod_limpio = codigo.strip()
        c = db.query(ContactoProveedor).filter(ContactoProveedor.codigo == cod_limpio).first()
        if not c:
            c = ContactoProveedor(codigo=cod_limpio)
            db.add(c)
        c.nombre = payload.nombre
        c.telefono = payload.telefono
        c.email = payload.email
        c.producto = payload.producto
        db.commit()
        db.refresh(c)
        return c

    @staticmethod
    def eliminar(db: Session, codigo: str) -> None:
        cod_limpio = codigo.strip()
        c = db.query(ContactoProveedor).filter(ContactoProveedor.codigo == cod_limpio).first()
        if c:
            db.delete(c)
            db.commit()

