import os
import pytest
from fastapi.testclient import TestClient

os.environ["DB_URL"] = "sqlite:///./test_recepcion.sqlite"
os.environ["JWT_SECRET"] = "supersecretkeyformodulartesting12345"

from app.main import app
from app.core.database import Base, engine, SessionLocal
from app.core.seeder import init_db_and_seed
from app.modules.vehiculos.models import Vehiculo
from app.modules.usuarios.models import Usuario


@pytest.fixture(scope="module")
def client():
    Base.metadata.drop_all(bind=engine)
    init_db_and_seed()

    # Crear vehículo de prueba asociado al cliente demo
    db = SessionLocal()
    cliente = db.query(Usuario).filter(Usuario.nombre_usuario == "cliente").first()
    vehiculo = Vehiculo(
        placa="PBC-1234",
        marca="Chevrolet",
        modelo="Sail",
        anio=2022,
        kilometraje=45000,
        cilindraje=1500,
        id_usuario=cliente.id_usuario,
    )
    db.add(vehiculo)
    db.commit()
    db.close()

    with TestClient(app) as c:
        yield c

    engine.dispose()
    if os.path.exists("./test_recepcion.sqlite"):
        try:
            os.remove("./test_recepcion.sqlite")
        except OSError:
            pass


def test_flujo_completo_hoja_recepcion(client: TestClient):
    # 0. Login con usuario administrador para obtener token
    login_res = client.post(
        "/api/usuarios/login",
        json={"nombre_usuario": "admin", "contrasena": "123456"},
    )
    assert login_res.status_code == 200
    token = login_res.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Obtener auto registrado
    vehiculo_res = client.get("/api/vehiculos/buscar/placa/PBC-1234", headers=headers)
    assert vehiculo_res.status_code == 200
    id_vehiculo = vehiculo_res.json()["id_vehiculo"]

    # 2. Registrar Hoja de Recepción (Proceso 2) solo con datos iniciales (sin fotos ni firma todavía)
    payload_incompleto = {
        "id_vehiculo": id_vehiculo,
        "kilometraje": 46500,
        "nivel_combustible": "1/2",
        "luces_tablero": "Check Engine encendido",
        "danos_previos": "Rayón leve en puerta lateral derecha",
        "observaciones": "Cliente solicita revisión de frenos y afinamiento",
        "crear_orden_automatica": True,
    }
    rec_res = client.post("/api/recepciones", json=payload_incompleto, headers=headers)
    assert rec_res.status_code == 201
    rec_data = rec_res.json()
    id_recepcion = rec_data["id_recepcion"]
    id_registro = rec_data["id_registro"]

    assert rec_data["completa"] is False
    assert "foto_frente" in rec_data["faltantes"]
    assert "foto_posterior" in rec_data["faltantes"]
    assert "foto_lateral_izq" in rec_data["faltantes"]
    assert "foto_lateral_der" in rec_data["faltantes"]
    assert "firma_cliente" in rec_data["faltantes"]

    # 3. Validar Proceso 2.1: Intentar avanzar la orden de taller a Estado 2 (Revisión) debe ser BLOQUEADO
    patch_res = client.patch(f"/api/registros/{id_registro}/estado?estado=2", headers=headers)
    assert patch_res.status_code == 400
    assert "Proceso 2.1" in patch_res.text

    # 4. Completar las 4 fotos y la firma del cliente
    payload_completar = {
        "foto_frente": "https://storage.openauto.com/recepciones/frente_123.jpg",
        "foto_posterior": "https://storage.openauto.com/recepciones/posterior_123.jpg",
        "foto_lateral_izq": "https://storage.openauto.com/recepciones/lateral_izq_123.jpg",
        "foto_lateral_der": "https://storage.openauto.com/recepciones/lateral_der_123.jpg",
        "firma_cliente": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAUA...",
    }
    update_res = client.put(f"/api/recepciones/{id_recepcion}", json=payload_completar, headers=headers)
    assert update_res.status_code == 200
    rec_actualizada = update_res.json()
    assert rec_actualizada["completa"] is True
    assert len(rec_actualizada["faltantes"]) == 0

    # 5. Validar estado vía endpoint de verificación
    validar_res = client.get(f"/api/recepciones/{id_recepcion}/validar", headers=headers)
    assert validar_res.status_code == 200
    assert validar_res.json()["completa"] is True
    assert validar_res.json()["puede_avanzar_fase_b"] is True

    # 6. Ahora que la recepción está completa, la orden SÍ debe poder avanzar a Estado 2
    patch_ok = client.patch(f"/api/registros/{id_registro}/estado?estado=2", headers=headers)
    assert patch_ok.status_code == 200
    assert patch_ok.json()["estado"] == 2
