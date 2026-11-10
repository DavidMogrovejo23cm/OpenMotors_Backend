from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import EntityNotFoundError
from app.modules.facturacion.schemas import FacturaCreate, FacturaUpdate, DetalleFacturaCreate
from app.modules.facturacion.service import FacturaService, DetalleFacturaService

facturas_router = APIRouter(prefix="/api/facturas", tags=["Facturas"])
detalles_factura_router = APIRouter(prefix="/api/detalles-factura", tags=["Detalles de Factura"])


# ==========================================
# FACTURAS (/api/facturas)
# ==========================================

@facturas_router.post("", status_code=status.HTTP_201_CREATED)
@facturas_router.post("/", status_code=status.HTTP_201_CREATED, include_in_schema=False)
def crear_factura(payload: FacturaCreate, db: Session = Depends(get_db)):
    nueva = FacturaService.crear(db, payload)
    return nueva.to_dict()


@facturas_router.get("")
@facturas_router.get("/", include_in_schema=False)
def listar_facturas(db: Session = Depends(get_db)):
    facturas = FacturaService.listar_todas(db)
    return [f.to_dict() for f in facturas]


@facturas_router.get("/{id_factura}")
def obtener_factura(id_factura: int, db: Session = Depends(get_db)):
    try:
        f = FacturaService.obtener_por_id(db, id_factura)
        return f.to_dict()
    except EntityNotFoundError:
        return Response(status_code=status.HTTP_404_NOT_FOUND)


@facturas_router.put("/{id_factura}")
def actualizar_factura(id_factura: int, payload: FacturaUpdate, db: Session = Depends(get_db)):
    f = FacturaService.actualizar(db, id_factura, payload)
    return f.to_dict()


@facturas_router.delete("/{id_factura}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_factura(id_factura: int, db: Session = Depends(get_db)):
    FacturaService.eliminar(db, id_factura)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ==========================================
# DETALLES DE FACTURA (/api/detalles-factura)
# ==========================================

@detalles_factura_router.post("", status_code=status.HTTP_201_CREATED)
@detalles_factura_router.post("/", status_code=status.HTTP_201_CREATED, include_in_schema=False)
def crear_detalle_factura(payload: DetalleFacturaCreate, db: Session = Depends(get_db)):
    nuevo = DetalleFacturaService.crear(db, payload)
    return nuevo.to_dict()


@detalles_factura_router.get("/factura/{id_factura}")
def listar_detalles_por_factura(id_factura: int, db: Session = Depends(get_db)):
    dets = DetalleFacturaService.listar_por_factura(db, id_factura)
    return [d.to_dict() for d in dets]


@detalles_factura_router.delete("/{id_detalle}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_detalle_factura(id_detalle: int, db: Session = Depends(get_db)):
    DetalleFacturaService.eliminar(db, id_detalle)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

