"""Contrato de trabajo/pagos y migración; bases aisladas en memoria."""
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text, select, func
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.main import app
from app.core.database import Base, get_db
from app.core.security import create_access_token
from app.core.migrations import migrate_order_states
from app.modules.usuarios.models import Usuario
from app.modules.roles.models import Rol, UsuarioRol
from app.modules.vehiculos.models import Vehiculo
from app.modules.taller.models import Registro
from app.modules.taller.pagos import PagoOrden

@pytest.fixture
def orden():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        for i, name in [(1, "ADMIN"), (2, "CLIENTE")]:
            db.add(Rol(id_rol=i, nombre=name))
            db.add(Usuario(id_usuario=i, nombre_completo=name, nombre_usuario=name, correo=f"{name}@test.local", contrasena="unused"))
        db.flush()
        db.add_all([UsuarioRol(id_usuario=1, id_rol=1, estado=1), UsuarioRol(id_usuario=2, id_rol=2, estado=1)])
        db.add(Vehiculo(id_vehiculo=1, placa="ABC-1234", marca="Kia", modelo="Rio", anio=2025, id_usuario=2))
        db.flush()
        db.add(Registro(id_registro=1, id_vehiculo=1, costo_total=100, estado=0))
        db.commit()
    def session():
        with Session(engine) as db:
            yield db
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = session
    headers = {"Authorization": "Bearer " + create_access_token(1, "ADMIN", "ADMIN@test.local")}
    client = TestClient(app, raise_server_exceptions=True)
    try:
        yield client, headers, engine
    finally:
        client.close()
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous)
    engine.dispose()

def test_transiciones_fechas_y_pago_independiente(orden):
    client, headers, _ = orden
    def cambiar(n):
        return client.patch("/api/registros/1/estado", json={"estado": n}, headers=headers)
    assert cambiar(2).status_code == 400  # No saltar pendiente -> finalizada.
    assert cambiar(7).status_code == 400
    assert cambiar(1).json()["fecha_completado"] is None
    finalizada = cambiar(2).json()
    assert finalizada["fecha_completado"] is not None
    assert finalizada["estado_pago"] == "PENDIENTE"
    assert cambiar(3).status_code == 400  # No entregar sin pagar.
    assert cambiar(1).json()["fecha_completado"] is None  # Reproceso.
    assert cambiar(2).status_code == 200
    pago = client.post("/api/registros/1/pagos", json={"monto": 100, "id_operacion": "total"}, headers=headers)
    assert pago.status_code == 201
    assert pago.json()["estado"] == 2
    assert pago.json()["estado_pago"] == "PAGADO"
    assert cambiar(3).json()["fecha_entregado"] is not None
    assert cambiar(1).status_code == 400
    assert cambiar(3).status_code == 200  # Repetir estado no crea otra entrega.

def test_abonos_auditoria_y_reintento(orden):
    client, headers, engine = orden
    payload = {"monto": 30, "metodo_pago": "TRANSFERENCIA", "id_operacion": "abono-1"}
    for _ in range(2):
        res = client.post("/api/registros/1/pagos", json=payload, headers=headers)
        assert res.status_code == 201
        assert res.json()["monto_pagado"] == 30
        assert res.json()["estado_pago"] == "PARCIAL"
        assert res.json()["saldo_pendiente"] == 70
        assert res.json()["estado"] == 0
    collision = client.post("/api/registros/1/pagos", json={**payload, "monto": 40}, headers=headers)
    assert collision.status_code == 400
    res = client.post("/api/registros/1/pagos", json={"monto": 70, "id_operacion": "abono-2"}, headers=headers)
    assert res.json()["estado_pago"] == "PAGADO"
    assert res.json()["saldo_pendiente"] == 0
    assert len(res.json()["pagos"]) == 2
    with Session(engine) as db:
        pagos = db.scalars(select(PagoOrden)).all()
        assert sum(p.monto for p in pagos) == Decimal("100.00")
        assert all(p.id_usuario == 1 for p in pagos)

@pytest.mark.parametrize("payload", [{"monto": -1}, {"monto": 0}, {"monto": 101}, {"monto": 0.001}, {"monto": 10, "metodo_pago": "OTRO"}])
def test_rechaza_pagos_invalidos_sin_alterar_saldo(orden, payload):
    client, headers, engine = orden
    assert client.post("/api/registros/1/pagos", json=payload, headers=headers).status_code == 400
    reg = client.get("/api/registros/1", headers=headers).json()
    assert reg["monto_pagado"] == 0
    assert reg["saldo_pendiente"] == 100
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(PagoOrden)) == 0

def test_cliente_no_puede_registrar_cobros(orden):
    client, _, _ = orden
    headers = {"Authorization": "Bearer " + create_access_token(2, "CLIENTE", "CLIENTE@test.local")}
    assert client.post("/api/registros/1/pagos", json={"monto": 100}, headers=headers).status_code == 403

def test_migracion_conserva_estado_y_no_infiere_pago_de_factura():
    engine = create_engine("sqlite://")
    with engine.begin() as c:
        c.execute(text("CREATE TABLE registros (id_registro INTEGER PRIMARY KEY, estado INTEGER, costo_total FLOAT, fecha_completado TEXT, fecha_entregado TEXT)"))
        for i, state in enumerate([0, 1, 2, 3, 4, 7, 8, 99], 1):
            c.execute(text("INSERT INTO registros VALUES (:id, :estado, 100, NULL, NULL)"), {"id": i, "estado": state})
    migrate_order_states(engine)
    migrate_order_states(engine)
    with engine.connect() as c:
        rows = c.execute(text("SELECT * FROM registros ORDER BY id_registro")).mappings().all()
        assert [r["estado_legacy"] for r in rows] == [0, 1, 2, 3, 4, 7, 8, 99]
        assert all(r["estado"] in (0, 1, 2, 3) for r in rows)
        assert rows[4]["estado_pago"] == "PENDIENTE"  # Facturado no demuestra pago.
        assert rows[4]["revision_estado"]
        assert rows[5]["estado"] == 2
        assert rows[5]["estado_pago"] == "PAGADO"
        assert rows[7]["revision_estado"]
    engine.dispose()


def test_migracion_reanuda_un_esquema_incompleto():
    engine = create_engine("sqlite://")
    with engine.begin() as c:
        c.execute(text("CREATE TABLE registros (id_registro INTEGER PRIMARY KEY, estado INTEGER, costo_total FLOAT, estado_pago VARCHAR(20) DEFAULT 'PENDIENTE')"))
        c.execute(text("INSERT INTO registros (id_registro, estado, costo_total) VALUES (1, 7, 30)"))
    migrate_order_states(engine)
    migrate_order_states(engine)
    with engine.connect() as c:
        row = c.execute(text("SELECT * FROM registros")).mappings().one()
        assert row["estado_version"] == 1
        assert row["estado_legacy"] == 7
        assert row["monto_pagado"] == 30
        assert row["estado_pago"] == "PAGADO"
    engine.dispose()
