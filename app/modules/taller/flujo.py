"""Reglas del recorrido integrado y consulta completa de una orden."""
from app.core.access_scope import scoped_query
from app.core.exceptions import BusinessValidationError
from app.modules.taller.models import RecepcionVehiculo, DiagnosticoVehiculo, Presupuesto, BitacoraReparacion, ControlCalidad, DanoAdicional


def validar_etapa(db, reg, etapa):
    if not reg or not reg.flujo_integrado:
        return
    if reg.estado == 3:
        raise BusinessValidationError("La orden ya fue entregada y su trabajo está cerrado")
    rec = scoped_query(db, RecepcionVehiculo).filter_by(id_registro=reg.id_registro).order_by(RecepcionVehiculo.id_recepcion.desc()).first()
    if not rec or not rec.esta_completa:
        raise BusinessValidationError("Complete la recepción con las cuatro fotos y la firma del cliente")
    if etapa == "diagnostico": return
    diagnostic = scoped_query(db, DiagnosticoVehiculo).filter_by(id_registro=reg.id_registro).first()
    if not diagnostic:
        raise BusinessValidationError("Registre un diagnóstico vinculado a esta orden")
    if etapa == "presupuesto": return
    budget = scoped_query(db, Presupuesto).filter_by(id_registro=reg.id_registro).order_by(Presupuesto.id_presupuesto.desc()).first()
    if etapa in ("cobro", "entrega") and budget and budget.estado == "RECHAZADO": return
    if not budget or budget.estado not in ("APROBADO_TOTAL", "APROBADO_PARCIAL"):
        raise BusinessValidationError("El cliente debe aprobar el presupuesto antes de realizar el trabajo")
    if etapa == "reparacion": return
    if not scoped_query(db, BitacoraReparacion).filter_by(id_registro=reg.id_registro).first():
        raise BusinessValidationError("Registre los trabajos realizados antes del control de calidad")
    if scoped_query(db, DanoAdicional).filter_by(id_registro=reg.id_registro, estado="PENDIENTE").first():
        raise BusinessValidationError("Hay daños adicionales pendientes de respuesta del cliente")
    if etapa in ("calidad", "cobro", "entrega"):
        from app.modules.inventario.movimientos import consumo_neto
        required = {}
        for item in budget.items:
            if item.estado_aprobacion == "APROBADO" and item.id_producto:
                required[item.id_producto] = required.get(item.id_producto, 0) + item.cantidad
        for damage in scoped_query(db, DanoAdicional).filter_by(id_registro=reg.id_registro, estado="APROBADO").all():
            if damage.id_producto: required[damage.id_producto] = required.get(damage.id_producto, 0) + 1
        for product, qty in required.items():
            if consumo_neto(db, reg.id_registro, product) < qty:
                raise BusinessValidationError("Registre el consumo de los repuestos aprobados antes de finalizar calidad")
        if etapa == "calidad": return
    last = scoped_query(db, ControlCalidad).filter_by(id_registro=reg.id_registro).order_by(ControlCalidad.id_control.desc()).first()
    if not last or not last.paso_inspeccion:
        raise BusinessValidationError("Se requiere un control de calidad aprobado")
    from app.modules.inventario.models import MovimientoKardex
    if db.query(MovimientoKardex).filter(MovimientoKardex.id_registro == reg.id_registro, MovimientoKardex.fecha > last.fecha, MovimientoKardex.origen != "LEGADO_CONCILIACION").first():
        raise BusinessValidationError("Repita el control de calidad después de modificar el consumo de repuestos")
