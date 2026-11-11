import os
import pytest
from fastapi.testclient import TestClient

os.environ["DB_URL"] = "sqlite:///./test_reserva.sqlite"
os.environ["JWT_SECRET"] = "supersecretkeyformodulartesting12345"

from app.main import app
from app.core.database import Base, engine, SessionLocal
from app.core.seeder import init_db_and_seed
from app.modules.vehiculos.models import Vehiculo
from app.modules.taller.models import Registro, Presupuesto, ItemPresupuesto
from app.modules.inventario.models import Producto, Categoria


@pytest.fixture(scope="module")
def client():
    Base.metadata.drop_all(bind=engine)
    init_db_and_seed()

    db = SessionLocal()
    # Asegurar categoría y producto
    cat = db.query(Categoria).first()
    if not cat:
        cat = Categoria(nombre="Frenos", descripcion="Sistema de frenado")
        db.add(cat)
        db.commit()
        db.refresh(cat)

    prod = Producto(
        codigo_personal="REP-PAST-01",
        codigo_barras="7861112223334",
        nombre="Pastillas de Freno Cerámicas Bosch",
        costo=25.0,
        pvp=45.0,
        stock=5,
        stock_reservado=0,
        stock_minimo=2,
        id_categoria=cat.id_categoria,
    )
    db.add(prod)
    db.commit()
    db.refresh(prod)

    vehiculo = Vehiculo(
        placa="PCM-8888",
        marca="Toyota",
        modelo="Corolla",
        anio=2021,
        kilometraje=35000,
        id_usuario=1,
    )
    db.add(vehiculo)
    db.commit()
    db.refresh(vehiculo)

    reg = Registro(
        id_vehiculo=vehiculo.id_vehiculo,
        descripcion="Mantenimiento correctivo de frenos",
        costo_total=0.0,
        estado=1,
        kilometraje=35000,
    )
    db.add(reg)
    db.commit()
    db.refresh(reg)

    # Crear presupuesto y aprobarlo (Proceso 5)
    pres = Presupuesto(
        numero_presupuesto="PRE-2026-9999",
        id_registro=reg.id_registro,
        id_vehiculo=vehiculo.id_vehiculo,
        id_usuario=1,
        estado="APROBADO_TOTAL",
        total_presupuestado=90.0,
        total_aprobado=90.0,
    )
    db.add(pres)
    db.flush()

    item_repuesto = ItemPresupuesto(
        id_presupuesto=pres.id_presupuesto,
        tipo_item="REPUESTO",
        id_producto=prod.id_producto,
        descripcion="Pastillas de Freno Cerámicas Bosch",
        cantidad=2.0,
        precio_unitario=45.0,
        subtotal=90.0,
        estado_aprobacion="APROBADO",
    )
    db.add(item_repuesto)
    db.commit()
    db.close()

    with TestClient(app) as c:
        yield c

    engine.dispose()
    if os.path.exists("./test_reserva.sqlite"):
        try:
            os.remove("./test_reserva.sqlite")
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


def test_reservar_repuestos_de_presupuesto_aprobado(client: TestClient):
    """Proceso 6 / Inv-4: Reserva automática de repuestos en bodega para la orden de taller."""
    headers = get_auth_headers(client)

    # Reservar repuestos aprobados del presupuesto #1
    res = client.post("/api/reservas/presupuesto/1", headers=headers)
    assert res.status_code == 201
    data = res.json()
    assert data["exito"] is True
    assert len(data["reservas_creadas"]) == 1

    reserva = data["reservas_creadas"][0]
    assert reserva["cantidad"] == 2
    assert reserva["estado"] == "RESERVADO"

    # Verificar que el producto actualizó stock_reservado = 2 y stock_disponible = 3 (5 - 2)
    prod_res = client.get("/api/productos/1", headers=headers)
    assert prod_res.status_code == 200
    prod_data = prod_res.json()
    assert prod_data["stock"] == 5
    assert prod_data["stock_reservado"] == 2
    assert prod_data["stock_disponible"] == 3


def test_asignar_mecanico_a_orden(client: TestClient):
    """Proceso 6: Asignar el mecánico que realizará la reparación en la orden."""
    headers = get_auth_headers(client)

    payload = {
        "id_mecanico": 2,  # Usuario mecánico o encargado existente
        "observaciones": "Asignado para cambio inmediato de pastillas delanteras",
        "fecha_entrega_estimada": "2026-11-12T17:00:00",
    }
    res = client.post("/api/reservas/asignar-mecanico/1", json=payload, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["exito"] is True
    assert data["id_encargado"] == 2
    assert data["estado_orden"] == 2  # En proceso / reparación


def test_retirar_repuesto_para_instalacion_proceso_7(client: TestClient):
    """Proceso 7: El mecánico retira el repuesto para instalarlo en el vehículo."""
    headers = get_auth_headers(client)

    res = client.post("/api/reservas/1/retirar", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["exito"] is True
    assert data["reserva"]["estado"] == "RETIRADO"

    # Verificar que el stock físico se descontó (5 - 2 = 3) y la reserva se liberó de stock_reservado
    prod_res = client.get("/api/productos/1", headers=headers)
    assert prod_res.status_code == 200
    prod_data = prod_res.json()
    assert prod_data["stock"] == 3
    assert prod_data["stock_reservado"] == 0
    assert prod_data["stock_disponible"] == 3

    # Verificar que se generó la salida en Kardex
    kardex_res = client.get("/api/kardex/movimientos?id_registro=1", headers=headers)
    assert kardex_res.status_code == 200
    movs = kardex_res.json()
    assert len(movs) >= 1
    assert movs[0]["tipo_movimiento"] == "SALIDA"
    assert movs[0]["cantidad"] == 2


def test_liberar_reserva_proceso_inv_5_1(client: TestClient):
    """Proceso Inv-5.1: Cancelación antes del retiro -> Liberar unidades reservadas."""
    headers = get_auth_headers(client)

    # Crear una nueva reserva individual
    payload_reserva = {
        "id_registro": 1,
        "id_producto": 1,
        "cantidad": 1,
    }
    crear_res = client.post("/api/reservas", json=payload_reserva, headers=headers)
    assert crear_res.status_code == 201
    id_reserva = crear_res.json()["id_reserva"]

    # Verificar que stock_reservado aumentó a 1
    prod1 = client.get("/api/productos/1", headers=headers).json()
    assert prod1["stock_reservado"] == 1
    assert prod1["stock_disponible"] == 2  # 3 - 1

    # Liberar reserva
    liberar_payload = {"motivo": "Cliente desistió del repuesto adicional"}
    lib_res = client.post(f"/api/reservas/{id_reserva}/liberar", json=liberar_payload, headers=headers)
    assert lib_res.status_code == 200
    lib_data = lib_res.json()
    assert lib_data["exito"] is True
    assert lib_data["reserva"]["estado"] == "LIBERADO"

    # Verificar que stock_reservado volvió a 0 y disponible volvió a 3
    prod2 = client.get("/api/productos/1", headers=headers).json()
    assert prod2["stock_reservado"] == 0
    assert prod2["stock_disponible"] == 3
