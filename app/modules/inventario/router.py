from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form, Response, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import EntityNotFoundError
from app.modules.inventario.schemas import (
    CategoriaCreate,
    ProductoCreate,
    ProductoUpdate,
    VentaDirectaRequest,
    ComprobanteVentaRequest,
    ContactoProveedorRequest,
    EscaneoEntradaRequest,
    EscaneoSalidaRequest,
    ReservaRepuestoCreate,
    ReservaPresupuestoRequest,
    AsignarMecanicoRequest,
    LiberarReservaRequest,
)
from app.modules.inventario.service import (
    CategoriaService,
    ProductoService,
    ContactoProveedorService,
    KardexService,
    ReservaRepuestoService,
)
from app.shared.storage_service import storage_service

categorias_router = APIRouter(prefix="/api/categorias", tags=["Categorías"])
productos_router = APIRouter(prefix="/api/productos", tags=["Productos"])
proveedores_router = APIRouter(prefix="/api/proveedores-contactos", tags=["Contactos de Proveedores"])
kardex_router = APIRouter(prefix="/api/kardex", tags=["Kardex y Escaneo Móvil"])
reservas_router = APIRouter(prefix="/api/reservas", tags=["Reservas de Repuestos y Mecánicos - Proceso 6"])


# ==========================================
# CATEGORÍAS (/api/categorias)
# ==========================================

@categorias_router.post("", status_code=status.HTTP_201_CREATED)
@categorias_router.post("/", status_code=status.HTTP_201_CREATED, include_in_schema=False)
def crear_categoria(payload: CategoriaCreate, db: Session = Depends(get_db)):
    cat = CategoriaService.crear(db, payload)
    return cat.to_dict()


@categorias_router.get("")
@categorias_router.get("/", include_in_schema=False)
def listar_categorias(db: Session = Depends(get_db)):
    cats = CategoriaService.listar_todas(db)
    return [c.to_dict() for c in cats]


@categorias_router.get("/{id_categoria}")
def obtener_categoria(id_categoria: int, db: Session = Depends(get_db)):
    try:
        cat = CategoriaService.obtener_por_id(db, id_categoria)
        return cat.to_dict()
    except EntityNotFoundError:
        return Response(status_code=status.HTTP_404_NOT_FOUND)


@categorias_router.put("/{id_categoria}")
def actualizar_categoria(id_categoria: int, payload: CategoriaCreate, db: Session = Depends(get_db)):
    cat = CategoriaService.actualizar(db, id_categoria, payload)
    return cat.to_dict()


@categorias_router.delete("/{id_categoria}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_categoria(id_categoria: int, db: Session = Depends(get_db)):
    CategoriaService.eliminar(db, id_categoria)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ==========================================
# PRODUCTOS (/api/productos)
# ==========================================

@productos_router.get("")
@productos_router.get("/", include_in_schema=False)
def listar_productos(db: Session = Depends(get_db)):
    prods = ProductoService.listar_todos(db)
    return [p.to_dict() for p in prods]


@productos_router.get("/{id_producto}")
def obtener_producto(id_producto: int, db: Session = Depends(get_db)):
    try:
        prod = ProductoService.obtener_por_id(db, id_producto)
        return prod.to_dict()
    except EntityNotFoundError:
        return Response(status_code=status.HTTP_404_NOT_FOUND)


@productos_router.post("", status_code=status.HTTP_201_CREATED)
@productos_router.post("/", status_code=status.HTTP_201_CREATED, include_in_schema=False)
def crear_producto(payload: ProductoCreate, db: Session = Depends(get_db)):
    nuevo = ProductoService.crear(db, payload)
    return nuevo.to_dict()


@productos_router.put("/{id_producto}")
def actualizar_producto(id_producto: int, payload: ProductoUpdate, db: Session = Depends(get_db)):
    prod = ProductoService.actualizar(db, id_producto, payload)
    return prod.to_dict()


@productos_router.delete("/{id_producto}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_producto(id_producto: int, db: Session = Depends(get_db)):
    ProductoService.eliminar(db, id_producto)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@productos_router.post("/eliminar", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_varios_productos(ids: List[int], db: Session = Depends(get_db)):
    ProductoService.eliminar_varios(db, ids)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@productos_router.post("/upload")
def subir_imagen_producto(
    archivo: UploadFile = File(...),
    codigoPersonal: str = Form("prod"),
):
    if not archivo or not archivo.filename:
        return JSONResponse(status_code=400, content={"error": "El archivo está vacío"})
    url = storage_service.upload_file(archivo, "productos", f"prod_{codigoPersonal}")
    return {"url": url}


@productos_router.post("/venta-directa")
def registrar_venta_directa(payload: VentaDirectaRequest, db: Session = Depends(get_db)):
    return ProductoService.venta_directa(db, payload)


@productos_router.post("/venta-comprobante")
def enviar_comprobante_venta(payload: ComprobanteVentaRequest):
    ProductoService.enviar_comprobante_venta(payload)
    return {"mensaje": "Comprobante enviado al correo"}


# ==========================================
# CONTACTOS DE PROVEEDORES (/api/proveedores-contactos)
# ==========================================

@proveedores_router.get("")
@proveedores_router.get("/", include_in_schema=False)
def listar_contactos_proveedores(db: Session = Depends(get_db)):
    contactos = ContactoProveedorService.listar_todos(db)
    return [c.to_dict() for c in contactos]


@proveedores_router.put("/{codigo}")
def guardar_contacto_proveedor(
    codigo: str, payload: ContactoProveedorRequest, db: Session = Depends(get_db)
):
    c = ContactoProveedorService.guardar_o_actualizar(db, codigo, payload)
    return c.to_dict()


@proveedores_router.delete("/{codigo}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_contacto_proveedor(codigo: str, db: Session = Depends(get_db)):
    ContactoProveedorService.eliminar(db, codigo)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ==========================================
# KARDEX Y ESCANEO MÓVIL (/api/kardex)
# ==========================================

@kardex_router.get("/escanear/{codigo}")
def escanear_codigo_repuesto(codigo: str, db: Session = Depends(get_db)):
    """Consulta inmediata para celular al escanear el código de barras o QR de un repuesto."""
    return KardexService.escanear(db, codigo)


@kardex_router.post("/entrada", status_code=status.HTTP_201_CREATED)
def registrar_entrada_kardex(payload: EscaneoEntradaRequest, db: Session = Depends(get_db)):
    """
    Registra el INGRESO de stock escaneando el código de barras con el celular (Procesos Inv-1 a Inv-2).
    Suma unidades al inventario, actualiza costo y registra el comprobante de proveedor.
    """
    return KardexService.registrar_entrada(db, payload)


@kardex_router.post("/salida")
def registrar_salida_kardex(payload: EscaneoSalidaRequest, db: Session = Depends(get_db)):
    """
    Registra la SALIDA/DESPACHO de repuestos escaneando con el celular (Procesos Inv-3 a Inv-6).
    Valida stock disponible, resta unidades, vincula con orden de taller y genera alerta si cae al mínimo.
    """
    return KardexService.registrar_salida(db, payload)


@kardex_router.get("/movimientos")
def listar_movimientos_kardex(
    id_producto: Optional[int] = Query(default=None),
    tipo_movimiento: Optional[str] = Query(default=None, description="ENTRADA | SALIDA"),
    id_registro: Optional[int] = Query(default=None, description="Filtrar por orden de taller"),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Obtiene el historial de movimientos de Kardex para auditoría y control de bodega."""
    return KardexService.listar_movimientos(
        db,
        id_producto=id_producto,
        tipo_movimiento=tipo_movimiento,
        id_registro=id_registro,
        limit=limit,
    )


@kardex_router.get("/alertas-stock")
def listar_alertas_stock_minimo(db: Session = Depends(get_db)):
    """Retorna todos los repuestos que alcanzaron o están por debajo del stock mínimo (Proceso Inv-6)."""
    return KardexService.listar_alertas_stock(db)


@kardex_router.post("/subir-factura-proveedor")
def subir_factura_proveedor_movil(archivo: UploadFile = File(...)):
    """Permite subir foto o PDF de la factura del proveedor tomada desde el celular."""
    if not archivo or not archivo.filename:
        return JSONResponse(status_code=400, content={"error": "Archivo no proporcionado"})
    url = storage_service.upload_file(archivo, "compras_proveedores", "factura_prov")
    return {"url": url, "nombre_archivo": archivo.filename}


# ==========================================
# RESERVAS DE REPUESTOS Y ASIGNACIÓN DE MECÁNICO - PROCESO 6 / INV-4
# ==========================================

@reservas_router.post("", status_code=status.HTTP_201_CREATED)
@reservas_router.post("/", status_code=status.HTTP_201_CREATED, include_in_schema=False)
def reservar_repuesto_individual(payload: ReservaRepuestoCreate, db: Session = Depends(get_db)):
    """Reserva individual de un repuesto para una orden de trabajo (Proceso 6 / Inv-4)."""
    return ReservaRepuestoService.reservar_item(db, payload)


@reservas_router.post("/presupuesto/{id_presupuesto}", status_code=status.HTTP_201_CREATED)
def reservar_repuestos_de_presupuesto(
    id_presupuesto: int,
    id_usuario: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
):
    """
    Reserva en bodega todos los repuestos aprobados en el presupuesto para la orden (Proceso 6).
    Evita la sobreventa o uso en otros vehículos.
    """
    return ReservaRepuestoService.reservar_presupuesto_aprobado(db, id_presupuesto, id_usuario)


@reservas_router.post("/asignar-mecanico/{id_registro}")
def asignar_mecanico_a_orden(
    id_registro: int,
    payload: AsignarMecanicoRequest,
    db: Session = Depends(get_db),
):
    """Asigna el mecánico que realizará la reparación de la orden de taller (Proceso 6)."""
    return ReservaRepuestoService.asignar_mecanico(
        db,
        id_registro=id_registro,
        id_mecanico=payload.id_mecanico,
        observaciones=payload.observaciones,
        fecha_entrega_estimada=payload.fecha_entrega_estimada,
    )


@reservas_router.get("/registro/{id_registro}")
def listar_reservas_por_orden(id_registro: int, db: Session = Depends(get_db)):
    """Lista todos los repuestos reservados para una orden de trabajo."""
    return ReservaRepuestoService.listar_reservas_por_registro(db, id_registro)


@reservas_router.get("")
@reservas_router.get("/", include_in_schema=False)
def listar_todas_las_reservas(
    estado: Optional[str] = Query(default=None, description="RESERVADO | RETIRADO | LIBERADO"),
    db: Session = Depends(get_db),
):
    return ReservaRepuestoService.listar_todas(db, estado=estado)


@reservas_router.post("/{id_reserva}/liberar")
def liberar_reserva_repuesto(
    id_reserva: int,
    payload: Optional[LiberarReservaRequest] = None,
    db: Session = Depends(get_db),
):
    """
    Libera las unidades reservadas de un repuesto, devolviéndolas al stock disponible (Proceso Inv-5.1).
    Se usa si la orden se cancela antes del cobro o instalación.
    """
    motivo = payload.motivo if payload else None
    id_usuario = payload.id_usuario if payload else None
    return ReservaRepuestoService.liberar_reserva(db, id_reserva, motivo=motivo, id_usuario=id_usuario)


@reservas_router.post("/{id_reserva}/retirar")
def retirar_repuesto_para_instalacion(
    id_reserva: int,
    id_usuario: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
):
    """
    El mecánico retira el repuesto para instalarlo en el vehículo (Proceso 7).
    Resta del stock físico y genera la salida correspondiente en Kardex.
    """
    return ReservaRepuestoService.retirar_repuesto_reservado(db, id_reserva, id_usuario=id_usuario)


