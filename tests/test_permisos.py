"""Acceso directo a la API, aislamiento y revocación inmediata de autorizaciones."""
import os
os.environ.setdefault("JWT_SECRET", "test-permissions-secret-with-at-least-32-chars")
os.environ.setdefault("DB_URL", "sqlite://")
import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.main import app
from app.core.database import Base, get_db
from app.core.security import create_access_token
from app.core.access_policy import authorize_request
from app.modules.usuarios.models import Usuario
from app.modules.roles.models import Rol, UsuarioRol
from app.modules.vehiculos.models import Vehiculo
from app.modules.taller.models import Registro, Presupuesto, DiagnosticoVehiculo, BitacoraReparacion
from app.modules.facturacion.models import Factura, NotaDeVenta
from app.modules.inventario.models import Producto, Categoria, MovimientoKardex

@pytest.fixture
def api(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all([Rol(id_rol=1, nombre="ADMIN"), Rol(id_rol=2, nombre="CLIENTE"), Rol(id_rol=3, nombre="MECANICO")])
        for i in range(1, 6):
            db.add(Usuario(id_usuario=i, nombre_completo=f"Persona {i}", nombre_usuario=f"u{i}", correo=f"u{i}@test.local", contrasena="unused"))
        db.flush()
        for user, role in [(1,1), (2,3), (3,3), (4,2), (5,2)]:
            db.add(UsuarioRol(id_usuario=user, id_rol=role, estado=1))
        db.add_all([Vehiculo(id_vehiculo=1, placa="ABC-1001", marca="Kia", modelo="Rio", id_usuario=4), Vehiculo(id_vehiculo=2, placa="ABC-1002", marca="Kia", modelo="Rio", id_usuario=5)])
        db.add_all([Factura(id_factura=1, id_usuario=4, costo_total=50), Factura(id_factura=2, id_usuario=5, costo_total=50)])
        db.flush()
        db.add_all([Registro(id_registro=1, id_vehiculo=1, id_encargado=2, id_factura=1, estado=1, costo_total=50), Registro(id_registro=2, id_vehiculo=2, id_encargado=3, id_factura=2, estado=1, costo_total=50), Registro(id_registro=3, id_vehiculo=1, id_encargado=3, estado=1)])
        db.flush()
        for i, owner in [(1,4), (2,5)]:
            db.add(Presupuesto(id_presupuesto=i, numero_presupuesto=f"PRE-TEST-{i}", id_registro=i, id_vehiculo=i, id_usuario=owner, estado="ENVIADO", total_presupuestado=50))
            db.add(DiagnosticoVehiculo(id_diagnostico=i, id_registro=i, id_vehiculo=i, id_mecanico=i+1))
            db.add(NotaDeVenta(id_nota_venta=i, numero_nota_venta=f"NV-TEST-{i}", id_registro=i, cliente_nombre=f"Cliente {owner}", total=50, pago_mecanico=10, ganancia_neta_taller=20))
        db.add(Categoria(id_categoria=1, nombre="Repuestos"))
        db.flush()
        db.add(Producto(id_producto=1, id_categoria=1, nombre="Filtro", codigo_personal="F-1", codigo_barras="123456789", stock=10, stock_minimo=2, costo=5, pvp=10))
        db.commit()
    def session():
        with Session(engine) as db:
            yield db
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = session
    client = TestClient(app)
    headers = {i: {"Authorization": "Bearer " + create_access_token(i, f"u{i}", f"u{i}@test.local"), "Content-Type": "application/json"} for i in range(1,6)}
    from app.shared.email_service import email_service
    monkeypatch.setattr(email_service, "enviar_correo_bienvenida", lambda *args, **kwargs: True)
    try:
        yield client, headers, engine
    finally:
        client.close()
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)
        engine.dispose()

@pytest.mark.parametrize("user,expected_orders,expected_vehicles", [(1,[1,2,3],[1,2]), (2,[1],[1]), (3,[2,3],[1,2]), (4,[1,3],[1]), (5,[2],[2])])
def test_listas_se_filtran_en_servidor(api, user, expected_orders, expected_vehicles):
    client, headers, _ = api
    assert sorted(r["id_registro"] for r in client.get("/api/registros", headers=headers[user]).json()) == expected_orders
    for prefix in ("vehiculos", "carros"):
        assert sorted(v["id_vehiculo"] for v in client.get(f"/api/{prefix}", headers=headers[user]).json()) == expected_vehicles

@pytest.mark.parametrize("path", ["/api/vehiculos/2", "/api/carros/2", "/api/vehiculos/placa/ABC-1002", "/api/registros/2", "/api/diagnosticos/2", "/api/presupuestos/2", "/api/facturas/2", "/api/notas-venta/2", "/api/registros/2/detalles-factura"])
def test_cliente_no_puede_leer_recursos_ajenos(api, path):
    client, headers, _ = api
    assert client.get(path, headers=headers[4]).status_code in (403,404)

@pytest.mark.parametrize("method,path,payload", [
    ("POST", "/api/registros/1/pagos", {"monto": 10}),
    ("POST", "/api/pagos-empleado", {"id_empleado": 2, "concepto": "Sueldo", "monto": 10}),
    ("POST", "/api/productos/venta-directa", {"id_producto": 1, "cantidad": 1}),
    ("POST", "/api/usuario_rol/asignar", {"id_usuario": 2, "id_rol": 1}),
    ("POST", "/api/reservas/asignar-mecanico/1", {"id_mecanico": 3}),
    ("POST", "/api/presupuestos/1/decision", {"decision": "APROBADO_TOTAL"}),
])
def test_mecanico_no_realiza_acciones_del_dueno_o_cliente(api, method, path, payload):
    client, headers, engine = api
    assert client.request(method, path, json=payload, headers=headers[2]).status_code == 403
    with Session(engine) as db:
        assert db.get(Producto, 1).stock == 10
        assert db.get(Registro, 1).monto_pagado == 0
        assert db.get(Registro, 1).id_encargado == 2

@pytest.mark.parametrize("path", ["/api/pagos-empleado", "/api/notas-venta/reportes/financiero", "/api/metrics/reports/preview", "/api/health/email-test?to=test@test.local"])
def test_datos_financieros_y_operacion_solo_administrador(api, path):
    client, headers, _ = api
    for user in (2,4):
        assert client.get(path, headers=headers[user]).status_code == 403
    assert client.get(path).status_code == 401

def test_mecanico_solo_modifica_trabajo_asignado_y_no_suplanta_autor(api):
    client, headers, engine = api
    for payload in [{"id_registro": 2, "descripcion_trabajo": "Ajeno"}, {"id_registro": 1, "id_mecanico": 3, "descripcion_trabajo": "Autor falso"}]:
        assert client.post("/api/reparaciones/bitacora", json=payload, headers=headers[2]).status_code in (403,404)
    response = client.post("/api/reparaciones/bitacora", json={"id_registro": 1, "descripcion_trabajo": "Trabajo autorizado", "horas_trabajadas": 1}, headers=headers[2])
    assert response.status_code == 201
    with Session(engine) as db:
        assert len(db.scalars(select(BitacoraReparacion)).unique().all()) == 1
        assert db.scalars(select(BitacoraReparacion)).unique().one().id_mecanico == 2
    assert client.patch("/api/registros/3/estado", json={"estado": 2}, headers=headers[2]).status_code == 404
    assert client.patch("/api/registros/1/estado", json={"estado": 3}, headers=headers[2]).status_code == 403

def test_cliente_solo_responde_su_presupuesto_disponible(api):
    client, headers, _ = api
    assert client.post("/api/presupuestos/2/decision", json={"decision": "APROBADO_TOTAL"}, headers=headers[4]).status_code == 404
    assert client.post("/api/presupuestos/1/decision", json={"decision": "APROBADO_TOTAL"}, headers=headers[4]).status_code == 200
    assert client.post("/api/presupuestos/1/decision", json={"decision": "RECHAZADO"}, headers=headers[4]).status_code == 403

def test_autorizacion_adicional_y_revocacion_con_el_mismo_token(api):
    client, headers, engine = api
    payload = {"codigo_barras": "123456789", "cantidad": 2, "id_registro": 1, "id_usuario": 3}
    assert client.post("/api/kardex/salida", json=payload, headers=headers[2]).status_code == 403
    grant = client.put("/api/usuarios/2/permisos", json={"permisos": ["inventario_consumos"]}, headers=headers[1])
    assert grant.status_code == 200
    assert client.post("/api/kardex/salida", json={**payload, "id_registro": 2}, headers=headers[2]).status_code == 404
    assert client.post("/api/kardex/salida", json=payload, headers=headers[2]).status_code == 200
    with Session(engine) as db:
        assert db.get(Producto, 1).stock == 8
        assert db.scalars(select(MovimientoKardex)).unique().one().id_usuario == 2
    assert client.put("/api/usuarios/2/permisos", json={"permisos": []}, headers=headers[1]).status_code == 200
    assert client.post("/api/kardex/salida", json=payload, headers=headers[2]).status_code == 403

def test_no_se_puede_autoconceder_permisos_ni_modificar_otra_cuenta(api):
    client, headers, _ = api
    assert client.put("/api/usuarios/2/permisos", json={"permisos": ["recepcion"]}, headers=headers[2]).status_code == 403
    assert client.put("/api/usuarios/2", json={"descripcion": "PERMISOS:contabilidad,recepcion"}, headers=headers[2]).status_code == 200
    assert client.post("/api/usuarios/clientes", json={"nombre_completo": "No autorizado", "nombre_usuario": "nuevo", "correo": "nuevo@test.local"}, headers=headers[2]).status_code == 403
    assert client.put("/api/usuarios/4", json={"correo": "usurpado@test.local"}, headers=headers[2]).status_code == 403

def test_recepcionista_puede_registrar_cliente_pero_no_administrar_personal(api):
    client, headers, _ = api
    assert client.put("/api/usuarios/2/permisos", json={"permisos": ["recepcion"]}, headers=headers[1]).status_code == 200
    response = client.post("/api/usuarios/clientes", json={"nombre_completo": "Nuevo Cliente", "nombre_usuario": "nuevo", "correo": "nuevo@test.local"}, headers=headers[2])
    assert response.status_code == 201
    assert client.put("/api/usuarios/3", json={"telefono": "0999999999"}, headers=headers[2]).status_code == 403
    assert client.post("/api/quick-accounts/create", json={"nombre_completo": "Admin", "correo": "u1@test.local", "placa": "ABC-2000", "marca": "Kia", "modelo": "Rio"}, headers=headers[2]).status_code == 403

def test_recibo_propio_no_expone_margen_ni_pagos_del_mecanico(api):
    client, headers, _ = api
    data = client.get("/api/notas-venta/1", headers=headers[4]).json()
    assert data["total"] == 50
    assert "ganancia_neta_taller" not in data
    assert "pago_mecanico" not in data
    assert "ganancia_neta_taller" in client.get("/api/notas-venta/1", headers=headers[1]).json()

def test_rol_suspendido_no_conserva_acceso_por_el_jwt(api):
    client, headers, engine = api
    with Session(engine) as db:
        relation = db.get(UsuarioRol, (2,3))
        relation.estado = 0
        db.commit()
    assert client.get("/api/registros", headers=headers[2]).status_code == 403

def test_registro_de_cuentas_requiere_administrador(api):
    client, headers, _ = api
    payload = {"nombre_completo": "Nuevo", "nombre_usuario": "otro", "correo": "otro@test.local", "contrasena": "Password12345"}
    assert client.post("/api/usuarios", json=payload).status_code == 401
    assert client.post("/api/usuarios", json=payload, headers=headers[4]).status_code == 403

def test_todas_las_rutas_del_api_tienen_politica_incluidas_las_alias():
    routes = []
    for route in app.routes:
        if isinstance(route, APIRoute):
            routes.append(route)
        elif hasattr(route, "effective_route_contexts"):
            routes.extend(route.effective_route_contexts())
    routes = [r for r in routes if r.path.startswith("/api/")]
    assert routes
    for route in routes:
        assert any(d.call is authorize_request for d in route.dependant.dependencies), route.path


def test_un_rol_sin_politica_no_recibe_acceso_por_defecto(api):
    client, headers, engine = api
    with Session(engine) as db:
        db.add(Rol(id_rol=4, nombre="INVITADO"))
        db.get(UsuarioRol, (4,2)).estado = 0
        db.flush()
        db.add(UsuarioRol(id_usuario=4, id_rol=4, estado=1))
        db.commit()
    assert client.get("/api/registros", headers=headers[4]).status_code == 403

def test_los_costos_internos_no_aparecen_en_detalles_del_cliente(api):
    from app.modules.facturacion.models import DetalleFactura
    client, headers, engine = api
    with Session(engine) as db:
        db.add(DetalleFactura(id_factura=1, descripcion="[REP|nuevo|COSTO:5.00] Filtro", cantidad=1, precio_unitario=10, subtotal=10))
        db.commit()
    response = client.get("/api/detalles-factura/factura/1", headers=headers[4])
    assert response.status_code == 200
    assert "COSTO:" not in response.json()[0]["descripcion"]
    assert "COSTO:5.00" in client.get("/api/detalles-factura/factura/1", headers=headers[1]).json()[0]["descripcion"]
