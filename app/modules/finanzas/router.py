from typing import Optional
from datetime import date
from pydantic import BaseModel, ConfigDict, Field, AliasChoices
from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.authorization import CurrentUser, require_roles
from app.core.database import get_db
from app.core.exceptions import BusinessValidationError, EntityNotFoundError
from app.modules.finanzas.models import PagoEmpleado
from app.modules.finanzas.service import FinanzasService, CajaService, _parse_date_range
from app.modules.usuarios.models import Usuario


class PagoEmpleadoCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore", str_strip_whitespace=True)

    id_empleado: int = Field(..., ge=0, validation_alias=AliasChoices("id_empleado", "idEmpleado"))
    fecha: Optional[str] = None
    concepto: str = Field(..., min_length=1)
    categoria: Optional[str] = None
    monto: float = Field(..., gt=0, allow_inf_nan=False)
    notas: Optional[str] = None


class CategoriaMovimientoCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore", str_strip_whitespace=True)

    nombre: str = Field(..., min_length=2, max_length=100)
    tipo: str = Field(default="EGRESO")
    descripcion: Optional[str] = Field(default=None, max_length=255)
    es_personal: bool = Field(default=False, validation_alias=AliasChoices("es_personal", "esPersonal"))


class CajaAperturaRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    monto_inicial: float = Field(default=0.0, ge=0.0, allow_inf_nan=False, validation_alias=AliasChoices("monto_inicial", "montoInicial"))
    observaciones: Optional[str] = None


class CajaMovimientoCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore", str_strip_whitespace=True)

    tipo: str  # INGRESO | RETIRO
    monto: float = Field(..., gt=0.0, allow_inf_nan=False)
    motivo: str = Field(..., min_length=3, max_length=255)
    referencia: Optional[str] = Field(default=None, max_length=100)
    observaciones: Optional[str] = Field(default=None, max_length=500)


class CajaCierreRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    monto_fisico_contado: float = Field(..., ge=0.0, allow_inf_nan=False, validation_alias=AliasChoices("monto_fisico_contado", "montoFisicoContado"))
    observaciones: Optional[str] = None


admin_dep = [Depends(require_roles("ADMIN"))]
pagos_router = APIRouter(prefix="/api/pagos-empleado", tags=["Pagos a Empleados"], dependencies=admin_dep)
finanzas_router = APIRouter(prefix="/api/finanzas", tags=["Gestión Financiera"], dependencies=admin_dep)
caja_router = APIRouter(prefix="/api/caja", tags=["Caja y Efectivo"], dependencies=admin_dep)


# ==========================================
# PAGOS A EMPLEADOS Y EGRESOS (/api/pagos-empleado)
# ==========================================

@pagos_router.get("")
@pagos_router.get("/", include_in_schema=False)
def listar_pagos(
    fecha_inicio: Optional[str] = Query(default=None),
    fecha_fin: Optional[str] = Query(default=None),
    categoria: Optional[str] = Query(default=None),
    id_empleado: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
):
    fi, ff = _parse_date_range(fecha_inicio, fecha_fin)
    q = db.query(PagoEmpleado)
    if fi:
        q = q.filter(PagoEmpleado.fecha >= fi)
    if ff:
        q = q.filter(PagoEmpleado.fecha <= ff)
    if id_empleado is not None:
        q = q.filter(PagoEmpleado.id_empleado == id_empleado)
    if categoria:
        cat_norm = categoria.strip().lower()
        q = q.filter(
            (func.lower(PagoEmpleado.categoria) == cat_norm)
            | (func.lower(PagoEmpleado.concepto) == cat_norm)
        )
    pagos = q.order_by(PagoEmpleado.fecha.desc(), PagoEmpleado.id_pago.desc()).all()
    return [p.to_dict() for p in pagos]


@pagos_router.get("/{id_empleado}")
def listar_pagos_por_empleado(id_empleado: int, db: Session = Depends(get_db)):
    pagos = (
        db.query(PagoEmpleado)
        .filter(PagoEmpleado.id_empleado == id_empleado)
        .order_by(PagoEmpleado.fecha.desc(), PagoEmpleado.id_pago.desc())
        .all()
    )
    return [p.to_dict() for p in pagos]


@pagos_router.post("", status_code=status.HTTP_201_CREATED)
@pagos_router.post("/", status_code=status.HTTP_201_CREATED, include_in_schema=False)
def registrar_pago(payload: PagoEmpleadoCreate, db: Session = Depends(get_db)):
    # id_empleado=0 representa los gastos generales en la interfaz de contabilidad.
    if payload.id_empleado:
        empleado = db.get(Usuario, payload.id_empleado)
        if not empleado:
            raise EntityNotFoundError("Empleado", payload.id_empleado)
        if not any(link.estado == 1 and link.rol and link.rol.nombre in ("MECANICO", "ADMIN") for link in empleado.roles):
            raise BusinessValidationError("Seleccione un empleado activo del taller")
    fecha_parsed = date.today()
    if payload.fecha:
        try:
            fecha_parsed = date.fromisoformat(payload.fecha[:10])
        except ValueError:
            raise BusinessValidationError("La fecha del gasto debe tener formato AAAA-MM-DD")

    categoria_validada = FinanzasService.validar_categoria_egreso(db, payload.categoria, payload.concepto)

    nuevo = PagoEmpleado(
        id_empleado=payload.id_empleado,
        fecha=fecha_parsed,
        concepto=payload.concepto.strip(),
        categoria=categoria_validada,
        monto=float(payload.monto),
        notas=payload.notas,
    )
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return nuevo.to_dict()


@pagos_router.delete("/{id_pago}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_pago(id_pago: int, db: Session = Depends(get_db)):
    pago = db.query(PagoEmpleado).filter(PagoEmpleado.id_pago == id_pago).first()
    if pago:
        db.delete(pago)
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ==========================================
# GESTIÓN FINANCIERA (/api/finanzas)
# ==========================================

@finanzas_router.get("/categorias")
def listar_categorias_financieras(
    tipo: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    """RF-33 / HU-43: Catálogo oficial de clasificación financiera."""
    return FinanzasService.listar_categorias(db, tipo=tipo)


@finanzas_router.post("/categorias", status_code=status.HTTP_201_CREATED)
def crear_categoria_financiera(
    payload: CategoriaMovimientoCreate,
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_roles("ADMIN")),
):
    return FinanzasService.crear_categoria(
        db,
        nombre=payload.nombre,
        tipo=payload.tipo,
        descripcion=payload.descripcion,
        es_personal=payload.es_personal,
        actor_id=actor.id_usuario,
    )


@finanzas_router.get("/deudas")
def consultar_deudas_clientes(
    id_cliente: Optional[int] = Query(default=None),
    q: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    """RF-36 / HU-46: Consulta consolidada de deudas y cuentas por cobrar agrupadas por cliente."""
    return FinanzasService.consultar_deudas_clientes(db, id_cliente=id_cliente, q=q)


@finanzas_router.get("/resumen-periodo")
def obtener_resumen_financiero_periodo(
    fecha_inicio: Optional[str] = Query(default=None),
    fecha_fin: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    """RF-38 / HU-48: Resumen financiero de ingresos, egresos y saldo neto por período."""
    return FinanzasService.resumen_financiero_periodo(db, fecha_inicio=fecha_inicio, fecha_fin=fecha_fin)


# ==========================================
# CAJA Y EFECTIVO (/api/caja)
# ==========================================

@caja_router.get("/resumen")
def obtener_resumen_caja(db: Session = Depends(get_db)):
    """RF-37 / HU-47: Estado actual, saldo disponible y resumen del día de caja."""
    return CajaService.resumen(db)


@caja_router.get("/movimientos")
def listar_movimientos_caja(
    fecha_inicio: Optional[str] = Query(default=None),
    fecha_fin: Optional[str] = Query(default=None),
    tipo: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    return CajaService.listar_movimientos(db, fecha_inicio=fecha_inicio, fecha_fin=fecha_fin, tipo=tipo)


@caja_router.get("/cierres")
def listar_cierres_caja(db: Session = Depends(get_db)):
    return CajaService.listar_cierres(db)


@caja_router.post("/apertura", status_code=status.HTTP_201_CREATED)
def abrir_caja(
    payload: CajaAperturaRequest,
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_roles("ADMIN")),
):
    return CajaService.abrir_caja(db, payload.monto_inicial, payload.observaciones, actor.id_usuario)


@caja_router.post("/movimientos", status_code=status.HTTP_201_CREATED)
def registrar_movimiento_caja(
    payload: CajaMovimientoCreate,
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_roles("ADMIN")),
):
    return CajaService.registrar_movimiento(
        db,
        tipo=payload.tipo,
        monto_raw=payload.monto,
        motivo=payload.motivo,
        referencia=payload.referencia,
        observaciones=payload.observaciones,
        actor_id=actor.id_usuario,
    )


@caja_router.post("/cierre", status_code=status.HTTP_200_OK)
def cerrar_caja(
    payload: CajaCierreRequest,
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_roles("ADMIN")),
):
    return CajaService.cerrar_caja(db, payload.monto_fisico_contado, payload.observaciones, actor.id_usuario)
