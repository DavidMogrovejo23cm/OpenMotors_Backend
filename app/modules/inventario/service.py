from app.core.access_scope import scoped_query
from datetime import date, datetime
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.exceptions import EntityNotFoundError, BusinessValidationError, ConflictError
from app.modules.inventario.models import (
    Categoria,
    Producto,
    ContactoProveedor,
    MovimientoKardex,
    ReservaRepuesto,
)
from app.modules.usuarios.models import Usuario
from app.modules.taller.models import Registro, Presupuesto, ItemPresupuesto
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
            codigo_barras=(getattr(payload, "codigo_barras", None) or codigo_pers).strip(),
            codigo_proveedor=(payload.codigo_proveedor or "PROV-001").strip(),
            codigo_distribuidor=(payload.codigo_distribuidor or "DIST-001").strip(),
            codigo_personal=codigo_pers,
            nombre=(payload.nombre or "").strip(),
            marca=(getattr(payload, "marca", "Genérico") or "Genérico").strip(),
            proveedor=getattr(payload, "proveedor", None),
            descripcion=(payload.descripcion or "").strip(),
            costo=float(payload.costo or 0.0),
            pvp=float(payload.pvp or 0.0),
            stock=0,
            stock_minimo=int(payload.stock_minimo if payload.stock_minimo is not None else 2),
            duracion_estimada_km=getattr(payload, "duracion_estimada_km", None),
            ubicacion_bodega=getattr(payload, "ubicacion_bodega", None),
            fecha_registro=date.today(),
            fecha_modificacion=datetime.now(),
            id_categoria=payload.id_categoria,
            ruta_imagenproductos=payload.ruta_imagenproductos,
        )
        db.add(nuevo)
        db.flush()
        if payload.stock:
            from app.modules.inventario.movimientos import mover
            mover(db, nuevo, int(payload.stock), "SALDO_INICIAL", db.info.get("actor").id_usuario if db.info.get("actor") else None, motivo="Existencias iniciales del producto")
        db.commit()
        db.refresh(nuevo)
        return nuevo

    @staticmethod
    def actualizar(db: Session, id_producto: int, payload: Any) -> Producto:
        from app.modules.inventario.movimientos import bloquear_producto
        prod = bloquear_producto(db, id_producto)

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
        if payload.stock is not None and payload.stock != prod.stock:
            from app.modules.inventario.movimientos import bloquear_producto, mover
            db.flush()
            mover(db, prod, int(payload.stock) - prod.stock, "AJUSTE_CATALOGO", db.info.get("actor").id_usuario if db.info.get("actor") else None, motivo="Ajuste de existencias desde el catálogo")
        if payload.id_categoria is not None:
            prod.id_categoria = payload.id_categoria

        if getattr(payload, "codigo_barras", None) is not None:
            prod.codigo_barras = payload.codigo_barras.strip()
        if getattr(payload, "marca", None) is not None:
            prod.marca = payload.marca.strip()
        if getattr(payload, "proveedor", None) is not None:
            prod.proveedor = payload.proveedor.strip()
        if getattr(payload, "stock_minimo", None) is not None:
            prod.stock_minimo = int(payload.stock_minimo)
        if getattr(payload, "duracion_estimada_km", None) is not None:
            prod.duracion_estimada_km = int(payload.duracion_estimada_km)
        if getattr(payload, "ubicacion_bodega", None) is not None:
            prod.ubicacion_bodega = payload.ubicacion_bodega.strip()

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
        if db.query(MovimientoKardex).filter_by(id_producto=id_producto).first() or db.query(ReservaRepuesto).filter_by(id_producto=id_producto).first():
            raise ConflictError("El producto tiene historial; conserve el registro y actualice sus datos")
        db.delete(prod)
        db.commit()

    @staticmethod
    def eliminar_varios(db: Session, ids: List[int]) -> None:
        if db.query(MovimientoKardex).filter(MovimientoKardex.id_producto.in_(ids)).first() or db.query(ReservaRepuesto).filter(ReservaRepuesto.id_producto.in_(ids)).first():
            raise ConflictError("No se pueden eliminar productos con historial de movimientos o reservas")
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
        db.flush()
        from app.modules.inventario.movimientos import bloquear_producto, mover, OperacionInventario
        mov = mover(db, bloquear_producto(db, prod.id_producto), -cantidad, "VENTA_MOSTRADOR", db.info.get("actor").id_usuario if db.info.get("actor") else None, motivo=f"Venta de factura #{nueva_factura.id_factura}")
        db.add(OperacionInventario(clave=f"detalle:{detalle.id_detalle}", huella="detalle", resultado={"id_movimiento": mov.id_movimiento, "id_factura": nueva_factura.id_factura}))
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


class KardexService:
    """
    Servicio de control de Kardex y escaneo de códigos de barra para móvil (Procesos Inv-1 a Inv-6).
    """

    @staticmethod
    def buscar_por_codigo(db: Session, codigo: str) -> Optional[Producto]:
        c = (codigo or "").strip().lower()
        if not c:
            return None
        matches = db.query(Producto).filter((func.lower(Producto.codigo_barras) == c) | (func.lower(Producto.codigo_personal) == c)).all()
        if not matches:
            matches = db.query(Producto).filter((func.lower(Producto.codigo_proveedor) == c) | (func.lower(Producto.codigo_distribuidor) == c)).all()

        if len(matches) > 1:
            raise ConflictError("Código ambiguo: hay más de un producto; corrija los códigos antes de mover stock")
        return matches[0] if matches else None

    @staticmethod
    def escanear(db: Session, codigo: str) -> Dict[str, Any]:
        """Consulta rápida para el celular al escanear un código de barras."""
        prod = KardexService.buscar_por_codigo(db, codigo)
        if not prod:
            return {
                "encontrado": False,
                "codigo_escaneado": codigo,
                "mensaje": f"No se encontró ningún repuesto registrado con el código '{codigo}'.",
            }
        return {
            "encontrado": True,
            "codigo_escaneado": codigo,
            "producto": prod.to_dict(),
        }

    @staticmethod
    def registrar_entrada(db: Session, payload: Any) -> Dict[str, Any]:
        from app.modules.inventario.movimientos import registrar_escaneo, retirar_reserva
        return registrar_escaneo(db, payload, True)

    @staticmethod
    def registrar_salida(db: Session, payload: Any) -> Dict[str, Any]:
        from app.modules.inventario.movimientos import registrar_escaneo, retirar_reserva
        return registrar_escaneo(db, payload, False)

    @staticmethod
    def listar_movimientos(
        db: Session,
        id_producto: Optional[int] = None,
        tipo_movimiento: Optional[str] = None,
        id_registro: Optional[int] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        query = scoped_query(db, MovimientoKardex)
        if id_producto:
            query = query.filter(MovimientoKardex.id_producto == id_producto)
        if tipo_movimiento:
            query = query.filter(func.upper(MovimientoKardex.tipo_movimiento) == tipo_movimiento.strip().upper())
        if id_registro:
            query = query.filter(MovimientoKardex.id_registro == id_registro)

        movs = query.order_by(MovimientoKardex.fecha.desc()).limit(limit).all()
        return [m.to_dict() for m in movs]

    @staticmethod
    def listar_alertas_stock(db: Session) -> List[Dict[str, Any]]:
        prods = (
            db.query(Producto)
            .filter(Producto.stock <= Producto.stock_minimo)
            .order_by(Producto.stock.asc())
            .all()
        )
        return [p.to_dict() for p in prods]


class ReservaRepuestoService:
    """
    Gestión de Reservas de Repuestos y Asignación de Mecánicos (Proceso 6, Proceso 6.1 e Inv-4).
    """

    @staticmethod
    def reservar_item(db: Session, payload: Any) -> Dict[str, Any]:
        from app.modules.inventario.movimientos import bloquear_orden, bloquear_producto
        bloquear_orden(db, payload.id_registro)
        prod = bloquear_producto(db, payload.id_producto)
        if not prod:
            raise EntityNotFoundError("Producto", payload.id_producto)

        reg = scoped_query(db, Registro).filter(Registro.id_registro == payload.id_registro).first()
        if not reg:
            raise EntityNotFoundError("Registro de taller", payload.id_registro)

        cant = int(payload.cantidad or 1)
        if cant <= 0:
            raise BusinessValidationError("La cantidad a reservar debe ser mayor a cero.")

        if prod.stock_disponible < cant:
            raise BusinessValidationError(
                f"Stock insuficiente para '{prod.nombre}'. Disponible: {prod.stock_disponible}, solicitado: {cant}."
            )

        prod.stock_reservado += cant
        reserva = ReservaRepuesto(
            id_registro=payload.id_registro,
            id_producto=payload.id_producto,
            cantidad=cant,
            id_presupuesto=payload.id_presupuesto,
            id_item_presupuesto=payload.id_item_presupuesto,
            id_usuario=payload.id_usuario,
            estado="RESERVADO",
            fecha_reserva=datetime.now(),
        )
        db.add(reserva)
        db.commit()
        db.refresh(reserva)
        db.refresh(prod)
        return reserva.to_dict()

    @staticmethod
    def reservar_presupuesto_aprobado(db: Session, id_presupuesto: int, id_usuario: Optional[int] = None) -> Dict[str, Any]:
        """
        Reserva automáticamente en bodega todos los repuestos aprobados de un presupuesto (Proceso 6 / Inv-4).
        """
        presupuesto = scoped_query(db, Presupuesto).filter(Presupuesto.id_presupuesto == id_presupuesto).first()
        if not presupuesto:
            raise EntityNotFoundError("Presupuesto", id_presupuesto)

        from app.modules.inventario.movimientos import bloquear_orden, bloquear_producto
        bloquear_orden(db, presupuesto.id_registro)
        if presupuesto.estado not in ("APROBADO_TOTAL", "APROBADO_PARCIAL"):
            raise BusinessValidationError(
                f"No se pueden reservar repuestos de un presupuesto en estado '{presupuesto.estado}'. Debe estar aprobado por el cliente."
            )

        repuestos_aprobados = [
            it for it in (presupuesto.items or [])
            if str(it.tipo_item).upper() == "REPUESTO" and str(it.estado_aprobacion).upper() == "APROBADO"
        ]

        if not repuestos_aprobados:
            return {
                "exito": True,
                "mensaje": "El presupuesto no contiene repuestos aprobados pendientes de reservar.",
                "reservas_creadas": [],
            }

        reservas_creadas = []
        for item in repuestos_aprobados:
            if not item.id_producto:
                continue

            # Verificar si ya existe reserva activa para este ítem
            existente = (
                scoped_query(db, ReservaRepuesto)
                .filter(
                    ReservaRepuesto.id_item_presupuesto == item.id_item,
                    ReservaRepuesto.estado.in_(["RESERVADO", "RETIRADO"]),
                )
                .first()
            )
            if existente:
                continue

            prod = bloquear_producto(db, item.id_producto)
            if not prod:
                continue

            cant = int(item.cantidad or 1)
            if prod.stock_disponible < cant:
                raise BusinessValidationError(
                    f"Stock insuficiente para reservar '{prod.nombre}'. Disponible: {prod.stock_disponible}, Requerido: {cant}. Por favor registre la compra con factura del proveedor (Proceso 6.1)."
                )

            prod.stock_reservado += cant
            nueva_reserva = ReservaRepuesto(
                id_registro=presupuesto.id_registro,
                id_presupuesto=presupuesto.id_presupuesto,
                id_item_presupuesto=item.id_item,
                id_producto=prod.id_producto,
                cantidad=cant,
                estado="RESERVADO",
                fecha_reserva=datetime.now(),
                id_usuario=id_usuario,
            )
            db.add(nueva_reserva)
            reservas_creadas.append(nueva_reserva)

        db.flush()
        db.commit()
        for r in reservas_creadas:
            db.refresh(r)

        return {
            "exito": True,
            "mensaje": f"Se reservaron exitosamente {len(reservas_creadas)} repuestos en bodega para la orden #{presupuesto.id_registro}.",
            "reservas_creadas": [r.to_dict() for r in reservas_creadas],
        }

    @staticmethod
    def asignar_mecanico(
        db: Session,
        id_registro: int,
        id_mecanico: int,
        observaciones: Optional[str] = None,
        fecha_entrega_estimada: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Asigna el mecánico responsable de la ejecución del trabajo en la orden (Proceso 6).
        """
        reg = scoped_query(db, Registro).filter(Registro.id_registro == id_registro).first()
        if not reg:
            raise EntityNotFoundError("Registro de taller", id_registro)

        mecanico = scoped_query(db, Usuario).filter(Usuario.id_usuario == id_mecanico).first()
        if not mecanico:
            raise EntityNotFoundError("Usuario Mecánico", id_mecanico)

        from app.modules.roles.models import UsuarioRol, Rol
        if not db.query(UsuarioRol).join(Rol).filter(UsuarioRol.id_usuario == id_mecanico, UsuarioRol.estado == 1, Rol.nombre == "MECANICO").first():
            raise BusinessValidationError("Seleccione una cuenta con rol de mecánico activo")
        reg.id_encargado = id_mecanico
        if fecha_entrega_estimada:
            try:
                reg.fecha_entrega_estimada = datetime.fromisoformat(fecha_entrega_estimada.replace("Z", "+00:00"))
            except Exception:
                pass

        if observaciones:
            if reg.observaciones:
                reg.observaciones = f"{reg.observaciones} | Asignación: {observaciones}"
            else:
                reg.observaciones = f"Asignación: {observaciones}"

        # Si aún estaba en recepción (1), avanza a estado en reparación (2)
        from app.modules.taller.estados import EstadoOrden, aplicar_estado
        if reg.estado == EstadoOrden.PENDIENTE:
            aplicar_estado(reg, EstadoOrden.EN_PROCESO)

        db.commit()
        db.refresh(reg)

        return {
            "exito": True,
            "mensaje": f"Mecánico '{mecanico.nombre_completo}' asignado a la orden #{id_registro}.",
            "id_registro": reg.id_registro,
            "id_encargado": reg.id_encargado,
            "nombre_mecanico": mecanico.nombre_completo,
            "estado_orden": reg.estado,
            "registro": reg.to_raw_dict(),
        }

    @staticmethod
    def liberar_reserva(
        db: Session,
        id_reserva: int,
        motivo: Optional[str] = None,
        id_usuario: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Libera las unidades reservadas devolviéndolas al stock disponible (Proceso Inv-5.1).
        """
        reserva = scoped_query(db, ReservaRepuesto).filter(ReservaRepuesto.id_reserva == id_reserva).first()
        if not reserva:
            raise EntityNotFoundError("Reserva de repuesto", id_reserva)

        if reserva.estado != "RESERVADO":
            raise BusinessValidationError(
                f"Solo se pueden liberar reservas en estado 'RESERVADO'. Estado actual: '{reserva.estado}'."
            )

        prod = db.query(Producto).filter(Producto.id_producto == reserva.id_producto).first()
        if prod:
            prod.stock_reservado = max(0, prod.stock_reservado - reserva.cantidad)

        reserva.estado = "LIBERADO"
        reserva.fecha_liberacion = datetime.now()
        reserva.motivo_liberacion = motivo or "Liberación solicitada por cancelación o ajuste"
        if id_usuario:
            reserva.id_usuario = id_usuario

        db.commit()
        db.refresh(reserva)
        if prod:
            db.refresh(prod)

        return {
            "exito": True,
            "mensaje": f"Reserva #{id_reserva} liberada. Unidades devueltas a disponibilidad.",
            "reserva": reserva.to_dict(),
            "stock_disponible": prod.stock_disponible if prod else None,
        }

    @staticmethod
    def retirar_repuesto_reservado(
        db: Session,
        id_reserva: int,
        id_usuario: Optional[int] = None,
    ) -> Dict[str, Any]:
        from app.modules.inventario.movimientos import registrar_escaneo, retirar_reserva
        return retirar_reserva(db, id_reserva, id_usuario)

    @staticmethod
    def listar_reservas_por_registro(db: Session, id_registro: int) -> List[Dict[str, Any]]:
        reservas = (
            scoped_query(db, ReservaRepuesto)
            .filter(ReservaRepuesto.id_registro == id_registro)
            .order_by(ReservaRepuesto.fecha_reserva.desc())
            .all()
        )
        return [r.to_dict() for r in reservas]

    @staticmethod
    def listar_todas(db: Session, estado: Optional[str] = None) -> List[Dict[str, Any]]:
        query = scoped_query(db, ReservaRepuesto)
        if estado:
            query = query.filter(func.upper(ReservaRepuesto.estado) == estado.strip().upper())
        reservas = query.order_by(ReservaRepuesto.fecha_reserva.desc()).all()
        return [r.to_dict() for r in reservas]


