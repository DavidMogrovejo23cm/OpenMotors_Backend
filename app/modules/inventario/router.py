from typing import List
from fastapi import APIRouter, Depends, UploadFile, File, Form, Response, status
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
)
from app.modules.inventario.service import (
    CategoriaService,
    ProductoService,
    ContactoProveedorService,
)
from app.shared.storage_service import storage_service

categorias_router = APIRouter(prefix="/api/categorias", tags=["Categorías"])
productos_router = APIRouter(prefix="/api/productos", tags=["Productos"])
proveedores_router = APIRouter(prefix="/api/proveedores-contactos", tags=["Contactos de Proveedores"])


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

