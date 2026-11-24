"""Consultas con alcance por propietario o asignación; los procesos internos no tienen actor."""
from sqlalchemy import select, or_, and_, false
from app.core.database import Base

def scoped_query(db, model):
    query = db.query(model)
    actor = db.info.get("actor")
    if not actor or "ADMIN" in actor.roles:
        return query
    tables = Base.metadata.tables
    orders, vehicles = tables["registros"], tables["vehiculos"]
    mechanic = "MECANICO" in actor.roles
    condition = orders.c.id_encargado == actor.id_usuario if mechanic else orders.c.id_vehiculo.in_(select(vehicles.c.id_vehiculo).where(vehicles.c.id_usuario == actor.id_usuario))
    order_ids = select(orders.c.id_registro).where(condition)
    work_vehicles = select(orders.c.id_vehiculo).where(condition)
    vehicle_ids = work_vehicles if mechanic else select(vehicles.c.id_vehiculo).where(vehicles.c.id_usuario == actor.id_usuario)
    table = model.__table__
    name, c = table.name, table.c
    if name == "registros":
        return query.filter(condition)
    if name == "vehiculos":
        return query if mechanic and "recepcion" in actor.permisos else query.filter(c.id_vehiculo.in_(vehicle_ids))
    if name == "usuarios":
        own = c.id_usuario == actor.id_usuario
        if mechanic and "recepcion" in actor.permisos:
            roles, links = tables["roles"], tables["usuario_rol"]
            customers = select(links.c.id_usuario).join(roles, roles.c.id_rol == links.c.id_rol).where(roles.c.nombre == "CLIENTE", links.c.estado == 1)
            return query.filter(or_(own, c.id_usuario.in_(customers)))
        owners = select(vehicles.c.id_usuario).where(vehicles.c.id_vehiculo.in_(work_vehicles))
        return query.filter(or_(own, c.id_usuario.in_(owners))) if mechanic else query.filter(own)
    if name == "facturas":
        assigned = c.id_factura.in_(select(orders.c.id_factura).where(condition))
        return query.filter(assigned if mechanic else or_(assigned, c.id_usuario == actor.id_usuario))
    if name == "detalles_factura":
        invoices = tables["facturas"]
        visible = invoices.c.id_factura.in_(select(orders.c.id_factura).where(condition))
        if not mechanic:
            visible = or_(visible, invoices.c.id_usuario == actor.id_usuario)
        return query.filter(c.id_factura.in_(select(invoices.c.id_factura).where(visible)))
    if name == "diagnostico_vehiculo":
        return query.filter(or_(c.id_registro.in_(order_ids), and_(c.id_registro.is_(None), c.id_vehiculo.in_(vehicle_ids))))
    if name == "detalle_diagnostico":
        diag = tables["diagnostico_vehiculo"]
        return query.filter(c.id_diagnostico.in_(select(diag.c.id_diagnostico).where(or_(diag.c.id_registro.in_(order_ids), and_(diag.c.id_registro.is_(None), diag.c.id_vehiculo.in_(vehicle_ids))))))
    if name in ("items_presupuesto", "items_nota_venta"):
        parent_name, key = ("presupuestos", "id_presupuesto") if name == "items_presupuesto" else ("notas_de_venta", "id_nota_venta")
        parent = tables[parent_name]
        return query.filter(c[key].in_(select(parent.c[key]).where(parent.c.id_registro.in_(order_ids))))
    if name == "movimientos_kardex":
        if mechanic and "inventario_entradas" in actor.permisos:
            return query
        return query.filter(c.id_registro.in_(order_ids))
    if name == "rutas":
        return query.filter(c.id_usuario == actor.id_usuario)
    if "id_registro" in c and name not in ("registros",):
        return query.filter(c.id_registro.in_(order_ids))
    if "id_vehiculo" in c:
        return query.filter(c.id_vehiculo.in_(vehicle_ids))
    return query
