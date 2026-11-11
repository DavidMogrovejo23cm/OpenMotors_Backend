import os
import pytest
from fastapi.testclient import TestClient

os.environ["DB_URL"] = "sqlite:///./test_kardex.sqlite"
os.environ["JWT_SECRET"] = "supersecretkeyformodulartesting12345"

from app.main import app
from app.core.database import Base, engine, SessionLocal
from app.core.seeder import init_db_and_seed
from app.modules.inventario.models import Categoria


@pytest.fixture(scope="module")
def client():
    Base.metadata.drop_all(bind=engine)
    init_db_and_seed()

    # Asegurar una categoría inicial de repuestos
    db = SessionLocal()
    if not db.query(Categoria).filter(Categoria.nombre == "Repuestos Frenos").first():
        cat = Categoria(nombre="Repuestos Frenos", descripcion="Pastillas, discos y fluidos")
        db.add(cat)
        db.commit()
    db.close()

    with TestClient(app) as c:
        yield c

    engine.dispose()
    if os.path.exists("./test_kardex.sqlite"):
        try:
            os.remove("./test_kardex.sqlite")
        except OSError:
            pass


def test_flujo_escaneo_movil_entrada_y_salida(client: TestClient):
    # 0. Autenticarse como administrador o mecánico
    login_res = client.post(
        "/api/usuarios/login",
        json={"nombre_usuario": "admin", "contrasena": "123456"},
    )
    assert login_res.status_code == 200
    token = login_res.json()["token"]
    id_usuario = login_res.json()["id_usuario"]
    headers = {"Authorization": f"Bearer {token}"}

    codigo_barras_test = "7861009876543"

    # 1. Escanear con el celular un código aún no registrado
    scan_init = client.get(f"/api/kardex/escanear/{codigo_barras_test}", headers=headers)
    assert scan_init.status_code == 200
    assert scan_init.json()["encontrado"] is False

    # 2. Registrar ENTRADA (Compra a proveedor escaneando la caja del repuesto)
    payload_entrada = {
        "codigo_barras": codigo_barras_test,
        "cantidad": 10,
        "costo_unitario": 12.50,
        "precio_venta": 22.00,
        "numero_factura_proveedor": "FAC-001-9988",
        "proveedor": "Distribuidora Automotriz Andina",
        "crear_si_no_existe": True,
        "nombre": "Juego de Pastillas Delanteras Cerámicas",
        "marca": "Bosch",
        "stock_minimo": 3,
        "id_usuario": id_usuario,
        "motivo": "Compra de reposición recibida de proveedor",
    }
    in_res = client.post("/api/kardex/entrada", json=payload_entrada, headers=headers)
    assert in_res.status_code == 201
    in_data = in_res.json()
    assert in_data["exito"] is True
    assert in_data["tipo"] == "ENTRADA"
    assert in_data["stock_anterior"] == 0
    assert in_data["stock_nuevo"] == 10
    id_producto = in_data["producto"]["id_producto"]

    # 3. Escanear nuevamente con el celular: ahora debe encontrarlo inmediatamente con su stock
    scan_post = client.get(f"/api/kardex/escanear/{codigo_barras_test}", headers=headers)
    assert scan_post.status_code == 200
    assert scan_post.json()["encontrado"] is True
    prod = scan_post.json()["producto"]
    assert prod["stock"] == 10
    assert prod["marca"] == "Bosch"
    assert prod["costo"] == 12.50

    # 4. Registrar SALIDA de 7 unidades para una reparación de taller
    payload_salida = {
        "codigo_barras": codigo_barras_test,
        "cantidad": 7,
        "id_usuario": id_usuario,
        "origen": "TALLER_ORDEN",
        "motivo": "Instalación en mantenimiento de frenos orden taller",
    }
    out_res = client.post("/api/kardex/salida", json=payload_salida, headers=headers)
    assert out_res.status_code == 200
    out_data = out_res.json()
    assert out_data["exito"] is True
    assert out_data["tipo"] == "SALIDA"
    assert out_data["stock_anterior"] == 10
    assert out_data["stock_nuevo"] == 3
    # Quedaron 3 y el mínimo es 3 -> Se activa la alerta de stock mínimo
    assert out_data["alerta_stock_minimo"] is True
    assert "ALERTA DE STOCK" in out_data["mensaje_alerta"]

    # 5. Intentar retirar 5 unidades cuando solo quedan 3 -> Debe RECHAZARSE por stock insuficiente
    payload_salida_exceso = {
        "codigo_barras": codigo_barras_test,
        "cantidad": 5,
    }
    out_fail = client.post("/api/kardex/salida", json=payload_salida_exceso, headers=headers)
    assert out_fail.status_code == 400
    assert "Stock insuficiente" in out_fail.text

    # 6. Consultar repuestos en alerta de stock mínimo (Proceso Inv-6)
    alertas_res = client.get("/api/kardex/alertas-stock", headers=headers)
    assert alertas_res.status_code == 200
    alertas = alertas_res.json()
    ids_en_alerta = [p["id_producto"] for p in alertas]
    assert id_producto in ids_en_alerta

    # 7. Consultar historial de movimientos del Kardex
    movs_res = client.get(f"/api/kardex/movimientos?id_producto={id_producto}", headers=headers)
    assert movs_res.status_code == 200
    movs = movs_res.json()
    assert len(movs) == 2
    tipos = [m["tipo_movimiento"] for m in movs]
    assert "ENTRADA" in tipos
    assert "SALIDA" in tipos
