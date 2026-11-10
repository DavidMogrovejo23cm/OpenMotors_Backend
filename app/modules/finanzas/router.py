from typing import Optional
from datetime import date
from pydantic import BaseModel, ConfigDict, Field, AliasChoices
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.finanzas.models import PagoEmpleado


class PagoEmpleadoCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id_empleado: int = Field(..., validation_alias=AliasChoices("id_empleado", "idEmpleado"))
    fecha: Optional[str] = None
    concepto: str
    monto: float
    notas: Optional[str] = None


pagos_router = APIRouter(prefix="/api/pagos-empleado", tags=["Pagos a Empleados"])


@pagos_router.get("")
@pagos_router.get("/", include_in_schema=False)
def listar_pagos(db: Session = Depends(get_db)):
    pagos = db.query(PagoEmpleado).order_by(PagoEmpleado.fecha.desc(), PagoEmpleado.id_pago.desc()).all()
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
    fecha_parsed = date.today()
    if payload.fecha:
        try:
            fecha_parsed = date.fromisoformat(payload.fecha[:10])
        except Exception:
            fecha_parsed = date.today()

    nuevo = PagoEmpleado(
        id_empleado=payload.id_empleado,
        fecha=fecha_parsed,
        concepto=payload.concepto.strip(),
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

