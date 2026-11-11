import os
import pytest
from fastapi.testclient import TestClient

os.environ["DB_URL"] = "sqlite:///./test_diagnostico.sqlite"
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

    db = SessionLocal()
    cliente = db.query(Usuario).filter(Usuario.nombre_usuario == "cliente").first()
    mecanico = db.query(Usuario).filter(Usuario.nombre_usuario == "mecanico").first()
    vehiculo = Vehiculo(
        placa="PBA-4567",
        marca="Chevrolet",
        modelo="Aveo Emotion",
        anio=2021,
        kilometraje=62000,
        cilindraje=1600,
        id_usuario=cliente.id_usuario,
    )
    db.add(vehiculo)
    db.commit()
    db.close()

    with TestClient(app) as c:
        yield c

    engine.dispose()
    if os.path.exists("./test_diagnostico.sqlite"):
        try:
            os.remove("./test_diagnostico.sqlite")
        except OSError:
            pass


def test_proceso_3_diagnostico_manual_escaner_y_8_sistemas(client: TestClient):
    # 1. Login con mecánico
    login_res = client.post(
        "/api/usuarios/login",
        json={"nombre_usuario": "mecanico", "contrasena": "123456"},
    )
    assert login_res.status_code == 200
    token = login_res.json()["token"]
    id_mecanico = login_res.json()["id_usuario"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Consultar plantilla de los 8 sistemas
    plantilla_res = client.get("/api/diagnosticos/plantilla-8-sistemas", headers=headers)
    assert plantilla_res.status_code == 200
    sistemas = plantilla_res.json()
    assert len(sistemas) == 8
    nombres_sistemas = [s["sistema"] for s in sistemas]
    assert "MOTOR" in nombres_sistemas
    assert "FRENOS" in nombres_sistemas
    assert "SUSPENSION" in nombres_sistemas
    assert "DIRECCION" in nombres_sistemas
    assert "TRANSMISION" in nombres_sistemas
    assert "SISTEMA_ELECTRICO" in nombres_sistemas
    assert "CLIMATIZACION" in nombres_sistemas
    assert "ESCAPE_EMISIONES" in nombres_sistemas

    # 3. Obtener el auto
    v_res = client.get("/api/vehiculos/placa/PBA-4567", headers=headers)
    assert v_res.status_code == 200
    id_vehiculo = v_res.json()["id_vehiculo"]

    # 4. Registrar el diagnóstico con la lectura manual del escáner y revisión de sistemas
    payload_diagnostico = {
        "id_vehiculo": id_vehiculo,
        "id_mecanico": id_mecanico,
        "kilometraje_ingreso": 62150,
        "escaner_utilizado": "Autel MaxiCheck MX808",
        "codigos_dtc": "P0300 (Fallo de encendido cilindros múltiples), P0420 (Eficiencia catalizador banco 1 baja)",
        "descripcion_escaner": "El escáner arrojó sensor de oxígeno banco 1 fuera de rango y pulso irregular en cilindro 2.",
        "observaciones_generales": "Vehículo presenta jalones en segunda marcha y testigo Check Engine encendido.",
        "problemas_adicionales": "Mecánico detectó fuga leve de aceite por empaque de tapa de válvulas y terminal de dirección derecho con juego excesivo.",
        "fotos_problemas": "https://storage.openauto.com/diag/fuga_tapa_valvulas.jpg,https://storage.openauto.com/diag/terminal_direccion.jpg",
        "detalles": [
            {
                "sistema": "MOTOR",
                "parte": "Bujías y cables de alta",
                "estado": "MALO",
                "observacion": "Bujía cilindro 2 carbonizada y con electrodo gastado. Requiere cambio de juego.",
                "foto_evidencia": "https://storage.openauto.com/diag/bujia_cilindro_2.jpg",
                "requiere_repuesto": True,
            },
            {
                "sistema": "FRENOS",
                "parte": "Pastillas de freno delanteras",
                "estado": "REGULAR",
                "observacion": "Pastillas al 35% de vida útil restante. Aún operativas, sugerir cambio en siguiente servicio.",
                "foto_evidencia": None,
                "requiere_repuesto": False,
            },
            {
                "sistema": "DIRECCION",
                "parte": "Terminal de dirección derecho",
                "estado": "CRITICO",
                "observacion": "Juego axial pronunciado en el terminal derecho. Riesgo de desalineación severa.",
                "foto_evidencia": "https://storage.openauto.com/diag/terminal_derecho.jpg",
                "requiere_repuesto": True,
            },
            {
                "sistema": "ESCAPE_EMISIONES",
                "parte": "Sensor de Oxígeno Superior",
                "estado": "MALO",
                "observacion": "Sensor no cicla adecuadamente según lectura del escáner.",
                "foto_evidencia": None,
                "requiere_repuesto": True,
            },
        ],
    }

    diag_res = client.post("/api/diagnosticos", json=payload_diagnostico, headers=headers)
    assert diag_res.status_code == 201
    diag_data = diag_res.json()

    assert diag_data["escaner_utilizado"] == "Autel MaxiCheck MX808"
    assert "P0300" in diag_data["codigos_dtc"]
    assert "P0420" in diag_data["codigos_dtc"]
    assert "fuga leve de aceite" in diag_data["problemas_adicionales"]
    assert len(diag_data["detalles"]) == 4
    assert len(diag_data["lista_fotos_problemas"]) == 2

    # Verificar que las partes que requieren repuestos están identificadas
    repuestos_requeridos = [d for d in diag_data["detalles"] if d["requiere_repuesto"]]
    assert len(repuestos_requeridos) == 3

    # 5. Obtener por ID y verificar integridad
    id_diag = diag_data["id_diagnostico"]
    get_res = client.get(f"/api/diagnosticos/{id_diag}", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["id_diagnostico"] == id_diag
