import os
import pytest
from fastapi.testclient import TestClient

os.environ["DB_URL"] = "sqlite:///./test_presupuesto.sqlite"
os.environ["JWT_SECRET"] = "supersecretkeyformodulartesting12345"

from app.main import app
from app.core.database import Base, engine, SessionLocal
from app.core.seeder import init_db_and_seed
from app.modules.vehiculos.models import Vehiculo
from app.modules.taller.models import Registro, DiagnosticoVehiculo


@pytest.fixture(scope="module")
def client():
    Base.metadata.drop_all(bind=engine)
    init_db_and_seed()

    # Sembrar un vehículo de prueba y una orden de trabajo
    db = SessionLocal()
    vehiculo = Vehiculo(
        placa="PBX-5050",
        marca="Chevrolet",
        modelo="Cruze",
        anio=2020,
        kilometraje=45000,
        id_usuario=1,
    )
    db.add(vehiculo)
    db.commit()
    db.refresh(vehiculo)

    reg = Registro(
        id_vehiculo=vehiculo.id_vehiculo,
        id_encargado=2,
        descripcion="Revisión general de frenos y suspensión",
        costo_total=0.0,
        estado=1,
        kilometraje=45000,
    )
    db.add(reg)
    db.commit()
    db.refresh(reg)

    diag = DiagnosticoVehiculo(
        id_vehiculo=vehiculo.id_vehiculo,
        id_mecanico=2,
        id_registro=reg.id_registro,
        kilometraje_ingreso=45000,
        escaner_utilizado="Autel MaxiSys",
        codigos_dtc="C0035 (Sensor de velocidad)",
        observaciones_generales="Discos desgastados y sensor averiado",
    )
    db.add(diag)
    db.commit()
    db.refresh(diag)
    db.close()

    with TestClient(app) as c:
        yield c

    engine.dispose()
    if os.path.exists("./test_presupuesto.sqlite"):
        try:
            os.remove("./test_presupuesto.sqlite")
        except OSError:
            pass


def get_auth_headers(client: TestClient):
    login_res = client.post(
        "/api/usuarios/login",
        json={"nombre_usuario": "admin", "contrasena": "123456"},
    )
    assert login_res.status_code == 200
    token = login_res.json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_creacion_presupuesto(client: TestClient):
    headers = get_auth_headers(client)

    payload = {
        "id_registro": 1,
        "id_vehiculo": 1,
        "id_diagnostico": 1,
        "id_usuario": 1,
        "descuento": 10.0,
        "costo_diagnostico": 35.0,
        "observaciones": "Presupuesto inicial para cambio de pastillas y sensor OBD2",
        "items": [
            {
                "tipo_item": "REPUESTO",
                "descripcion": "Juego de Pastillas de Freno Delanteras Bosch",
                "cantidad": 1.0,
                "precio_unitario": 45.0,
                "es_adicional": False,
            },
            {
                "tipo_item": "REPUESTO",
                "descripcion": "Sensor de Velocidad ABS Chevrolet Cruze",
                "cantidad": 1.0,
                "precio_unitario": 30.0,
                "es_adicional": False,
            },
            {
                "tipo_item": "MANO_OBRA",
                "descripcion": "Mano de obra cambio de pastillas y purgado",
                "cantidad": 2.0,
                "precio_unitario": 20.0,
                "es_adicional": False,
            },
        ],
    }

    res = client.post("/api/presupuestos", json=payload, headers=headers)
    assert res.status_code == 201
    data = res.json()

    assert data["id_presupuesto"] is not None
    assert "PRE-" in data["numero_presupuesto"]
    assert data["estado"] == "BORRADOR"
    assert data["subtotal_repuestos"] == 75.0  # 45 + 30
    assert data["subtotal_mano_obra"] == 40.0   # 2 * 20
    assert data["descuento"] == 10.0
    # Total = 75 + 40 - 10 = 105.0
    assert data["total_presupuestado"] == 105.0
    assert len(data["items"]) == 3


def test_enviar_presupuesto_al_cliente(client: TestClient):
    headers = get_auth_headers(client)

    res = client.post("/api/presupuestos/1/enviar", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["estado"] == "ENVIADO"


def test_aprobacion_total_presupuesto(client: TestClient):
    headers = get_auth_headers(client)

    decision_payload = {
        "decision": "APROBADO_TOTAL",
        "motivo": "Cliente autorizó todo el trabajo por llamada telefónica",
    }
    res = client.post("/api/presupuestos/1/decision", json=decision_payload, headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert data["estado"] == "APROBADO_TOTAL"
    assert data["total_aprobado"] == 105.0
    for item in data["items"]:
        assert item["estado_aprobacion"] == "APROBADO"

    # Verificar que el registro (orden de trabajo) actualizó su costo total y estado
    reg_res = client.get("/api/registros/1", headers=headers)
    assert reg_res.status_code == 200
    reg_data = reg_res.json()
    assert reg_data["costo_total"] == 105.0
    assert reg_data["estado"] == 2  # En proceso / reparación


def test_aprobacion_parcial_proceso_5_1(client: TestClient):
    """Proceso 5.1: Ajuste de presupuesto (aprobación solo de ciertos repuestos/mano de obra)."""
    headers = get_auth_headers(client)

    # Crear segundo presupuesto para probar ajuste parcial
    payload = {
        "id_registro": 1,
        "id_vehiculo": 1,
        "descuento": 0.0,
        "costo_diagnostico": 30.0,
        "observaciones": "Presupuesto complementario",
        "items": [
            {
                "tipo_item": "REPUESTO",
                "descripcion": "Amortiguador delantero",
                "cantidad": 2.0,
                "precio_unitario": 80.0,
            },
            {
                "tipo_item": "MANO_OBRA",
                "descripcion": "Instalación y alineación",
                "cantidad": 1.0,
                "precio_unitario": 50.0,
            },
            {
                "tipo_item": "REPUESTO",
                "descripcion": "Filtro de cabina",
                "cantidad": 1.0,
                "precio_unitario": 25.0,
            },
        ],
    }
    create_res = client.post("/api/presupuestos", json=payload, headers=headers)
    assert create_res.status_code == 201
    p2 = create_res.json()
    p2_id = p2["id_presupuesto"]
    items = p2["items"]
    # Ítem 1 (Amortiguadores: 160) e Ítem 2 (Mano de obra: 50) aprobados, Ítem 3 (Filtro: 25) postergado
    id_amort = items[0]["id_item"]
    id_mo = items[1]["id_item"]

    decision_payload = {
        "decision": "APROBADO_PARCIAL",
        "items_aprobados_ids": [id_amort, id_mo],
        "motivo": "Cliente prefiere postergar el cambio de filtro de cabina para el próximo mes",
    }
    dec_res = client.post(f"/api/presupuestos/{p2_id}/decision", json=decision_payload, headers=headers)
    assert dec_res.status_code == 200
    data = dec_res.json()

    assert data["estado"] == "APROBADO_PARCIAL"
    assert data["total_aprobado"] == 210.0  # 160 + 50
    items_dict = {it["id_item"]: it["estado_aprobacion"] for it in data["items"]}
    assert items_dict[id_amort] == "APROBADO"
    assert items_dict[id_mo] == "APROBADO"
    assert items_dict[items[2]["id_item"]] == "POSTERGADO"


def test_rechazo_presupuesto_con_cobro_diagnostico_proceso_5_2(client: TestClient):
    """Proceso 5.2: Rechazo con cobro de diagnóstico -> Registro pasa a estado 8 y costo = diagnóstico."""
    headers = get_auth_headers(client)

    # Crear tercer presupuesto
    payload = {
        "id_registro": 1,
        "id_vehiculo": 1,
        "costo_diagnostico": 40.0,
        "items": [
            {
                "tipo_item": "REPUESTO",
                "descripcion": "Kit de Embrague Completo",
                "cantidad": 1.0,
                "precio_unitario": 350.0,
            }
        ],
    }
    create_res = client.post("/api/presupuestos", json=payload, headers=headers)
    assert create_res.status_code == 201
    p3_id = create_res.json()["id_presupuesto"]

    decision_payload = {
        "decision": "RECHAZADO",
        "cobrar_solo_diagnostico": True,
        "motivo": "Costo de repuesto excede el presupuesto del cliente por el momento",
    }
    dec_res = client.post(f"/api/presupuestos/{p3_id}/decision", json=decision_payload, headers=headers)
    assert dec_res.status_code == 200
    data = dec_res.json()

    assert data["estado"] == "RECHAZADO"
    assert data["cobrar_solo_diagnostico"] is True
    assert data["total_aprobado"] == 40.0

    # Verificar que el registro pasó a estado 8 (Entregado sin reparación) con costo = 40.0
    reg_res = client.get("/api/registros/1", headers=headers)
    assert reg_res.status_code == 200
    reg_data = reg_res.json()
    assert reg_data["estado"] == 8
    assert reg_data["costo_total"] == 40.0
