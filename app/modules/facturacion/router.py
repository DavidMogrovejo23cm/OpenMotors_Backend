from typing import Optional
from fastapi import APIRouter, Depends, Response, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import EntityNotFoundError
from app.modules.facturacion.schemas import (
    FacturaCreate,
    FacturaUpdate,
    DetalleFacturaCreate,
    PrepararCobroRequest,
    ConfirmarPagoRequest,
)
from app.modules.facturacion.service import (
    FacturaService,
    DetalleFacturaService,
    NotaDeVentaService,
)

facturas_router = APIRouter(prefix="/api/facturas", tags=["Facturas"])
detalles_factura_router = APIRouter(prefix="/api/detalles-factura", tags=["Detalles de Factura"])
notas_venta_router = APIRouter(prefix="/api/notas-venta", tags=["Fase D: Notas de Venta y Cobro"])


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


# ==========================================
# NOTAS DE VENTA Y COBRO - PROCESOS 10, 11, 11.1, 12, 13 Y 14
# ==========================================

@notas_venta_router.post("/preparar", status_code=status.HTTP_201_CREATED)
def preparar_cobro_orden(payload: PrepararCobroRequest, db: Session = Depends(get_db)):
    """
    Proceso 10 / Fin-1: Prepara el cobro de la orden de taller.
    Desglosa repuestos usados, mano de obra, horas del mecánico, descuento y ganancia estimada.
    """
    return NotaDeVentaService.preparar_cobro(db, payload)


@notas_venta_router.post("/{id_nota_venta}/confirmar-pago")
def confirmar_pago_nota_venta(
    id_nota_venta: int, payload: ConfirmarPagoRequest, db: Session = Depends(get_db)
):
    """
    Procesos 11, 11.1, 12, 13, 13.1 y 14:
    - Confirma pago en Efectivo, Transferencia o Tarjeta.
    - Si el monto está incompleto, retiene la orden y el auto (Proceso 11.1).
    - Emite la Nota de Venta numerada [Estado 7: PAGADO] (Proceso 12).
    - Descuenta del inventario los repuestos usados y genera Kardex (Proceso 13 y 13.1).
    - Cierra la contabilidad de la orden calculando la ganancia neta (Proceso 14).
    """
    return NotaDeVentaService.confirmar_pago(db, id_nota_venta, payload)


@notas_venta_router.get("/reportes/financiero")
def obtener_reporte_financiero_global(db: Session = Depends(get_db)):
    """Proceso 14 / Fin-8: Reporte global de ingresos, costo de repuestos, pagos a mecánicos y ganancia neta."""
    return NotaDeVentaService.reporte_financiero_global(db)


@notas_venta_router.get("/{id_nota_venta}")
def obtener_nota_venta_por_id(id_nota_venta: int, db: Session = Depends(get_db)):
    try:
        return NotaDeVentaService.obtener_por_id(db, id_nota_venta)
    except EntityNotFoundError:
        return Response(status_code=status.HTTP_404_NOT_FOUND)


@notas_venta_router.get("/registro/{id_registro}")
def obtener_nota_venta_por_registro(id_registro: int, db: Session = Depends(get_db)):
    nv = NotaDeVentaService.obtener_por_registro(db, id_registro)
    if not nv:
        return Response(status_code=status.HTTP_404_NOT_FOUND)
    return nv


@notas_venta_router.get("")
@notas_venta_router.get("/", include_in_schema=False)
def listar_notas_de_venta(
    estado_pago: Optional[str] = Query(default=None, description="PENDIENTE_PAGO | PAGADO"),
    db: Session = Depends(get_db),
):
    return NotaDeVentaService.listar_todas(db, estado_pago=estado_pago)


