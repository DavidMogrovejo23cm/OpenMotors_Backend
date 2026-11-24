from app.core.access_scope import scoped_query
from datetime import datetime
from decimal import Decimal, InvalidOperation
from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Session
from app.core.database import Base
from app.core.exceptions import BusinessValidationError
from app.modules.taller.estados import EstadoPago

class PagoOrden(Base):
    __tablename__ = "pagos_orden"
    __table_args__ = (UniqueConstraint("id_registro", "id_operacion"),)
    id_operacion = Column(String(100), nullable=True)
    id_pago = Column(Integer, primary_key=True)
    id_registro = Column(Integer, ForeignKey("registros.id_registro"), nullable=False, index=True)
    monto = Column(Numeric(12, 2), nullable=False)
    metodo = Column(String(30), nullable=False)
    referencia = Column(String(100), nullable=True)
    id_usuario = Column(Integer, ForeignKey("usuarios.id_usuario"), nullable=False)
    fecha = Column(DateTime, nullable=False, default=datetime.now)

def registrar_abono(db: Session, reg, monto, metodo: str, actor: int, referencia=None, id_operacion=None):
    if id_operacion:
        anterior = scoped_query(db, PagoOrden).filter_by(id_registro=reg.id_registro, id_operacion=id_operacion).first()
        if anterior:
            if float(anterior.monto) != float(monto) or anterior.metodo != metodo.upper() or anterior.referencia != referencia:
                raise BusinessValidationError("La operación ya existe con otros datos de pago")
            return False
    try:
        valor = Decimal(str(monto))
    except InvalidOperation:
        raise BusinessValidationError("Monto inválido")
    if not valor.is_finite() or valor <= 0 or valor != valor.quantize(Decimal("0.01")):
        raise BusinessValidationError("El monto debe ser positivo y tener máximo dos decimales")
    metodo = metodo.upper()
    if metodo not in {"EFECTIVO", "TRANSFERENCIA", "TARJETA"}:
        raise BusinessValidationError("Método de pago inválido")
    pagado = Decimal(str(reg.monto_pagado or 0)).quantize(Decimal("0.01"))
    total = Decimal(str(reg.costo_total or 0)).quantize(Decimal("0.01"))
    if valor > total - pagado:
        raise BusinessValidationError("El monto supera el saldo pendiente")
    db.add(PagoOrden(id_registro=reg.id_registro, monto=valor, metodo=metodo, referencia=referencia, id_usuario=actor, id_operacion=id_operacion))
    reg.monto_pagado = float(pagado + valor)
    reg.estado_pago = EstadoPago.PAGADO if pagado + valor == total else EstadoPago.PARCIAL
    if reg.estado_pago == EstadoPago.PAGADO:
        reg.fecha_facturado = datetime.now()
    if metodo == "EFECTIVO":
        from app.modules.finanzas.service import CajaService
        CajaService.registrar_cobro_efectivo_si_abierta(db, reg.id_registro, float(valor), actor)

