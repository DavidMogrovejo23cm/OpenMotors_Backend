import os
import pytest
from fastapi.testclient import TestClient

os.environ["DB_URL"] = "sqlite:///./test_fase_c.sqlite"
os.environ["JWT_SECRET"] = "supersecretkeyformodulartesting12345"

from app.main import app
from app.core.database import Base, engine, SessionLocal
from app.core.seeder import init_db_and_seed
from app.modules.vehiculos.models import Vehiculo
from app.modules.taller.models import Registro


@pytest.fixture(scope="module")
def client():
    Base.metadata.drop_all(bind=engine)
    init_db_and_seed()

    db = SessionLocal()
    vehiculo = Vehiculo(
        placa="PDF-3030",
        marca="Hyundai",
        modelo="Tucson",
        anio=2022,
        kilometraje=28000,
        id_usuario=1,
    )
    db.add(vehiculo)
    db.commit()
    db.refresh(vehiculo)

    reg = Registro(
        id_vehiculo=vehiculo.id_vehiculo,
        id_encargado=2,
        descripcion="Cambio de kit de distribución y bandas",
        costo_total=180.0,
        estado=2,
        kilometraje=28000,
    )
    db.add(reg)
    db.commit()
    db.refresh(reg)
    db.close()

    with TestClient(app) as c:
        yield c

    engine.dispose()
    if os.path.exists("./test_fase_c.sqlite"):
        try:
            os.remove("./test_fase_c.sqlite")
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


def test_proceso_7_registro_bitacora_horas_y_fotos(client: TestClient):
    """Proceso 7: Anotar horas trabajadas, avance técnico y fotos de la reparación."""
    headers = get_auth_headers(client)

    payload = {
        "id_registro": 1,
        "id_mecanico": 2,
        "horas_trabajadas": 3.5,
        "descripcion_trabajo": "Desmontaje de bandas viejas e instalación de tensores nuevos",
        "fotos_evidencia": "/images/reparaciones/rep_proceso_1.jpg,/images/reparaciones/rep_proceso_2.jpg",
        "repuestos_instalados": "Kit Distribución Gates, Banda de accesorios",
    }
    res = client.post("/api/reparaciones/bitacora", json=payload, headers=headers)
    assert res.status_code == 201
    data = res.json()
    assert data["horas_trabajadas"] == 3.5
    assert len(data["lista_fotos"]) == 2
    assert "Gates" in data["repuestos_instalados"]

    # Consultar bitácora por registro
    lista_res = client.get("/api/reparaciones/bitacora/1", headers=headers)
    assert lista_res.status_code == 200
    assert len(lista_res.json()) >= 1


def test_proceso_7_1_dano_adicional_aprobado(client: TestClient):
    """Proceso 7.1: Hallazgo de daño adicional no presupuestado y aprobación del cliente."""
    headers = get_auth_headers(client)

    payload = {
        "id_registro": 1,
        "id_mecanico": 2,
        "descripcion": "Fuga severa en bomba de agua detectada tras retirar cubierta de distribución",
        "fotos_evidencia": "/images/reparaciones/fuga_bomba.jpg",
        "repuesto_sugerido": "Bomba de Agua Original Hyundai Tucson",
        "costo_estimado": 65.0,
    }
    rep_res = client.post("/api/reparaciones/danos-adicionales", json=payload, headers=headers)
    assert rep_res.status_code == 201
    dano = rep_res.json()
    assert dano["estado"] == "PENDIENTE"
    id_dano = dano["id_dano"]

    # El cliente aprueba el trabajo adicional
    decision_payload = {
        "aprobado": True,
        "observaciones_cliente": "Cliente aprueba por WhatsApp reemplazar bomba de agua para evitar recalentamiento",
    }
    dec_res = client.post(f"/api/reparaciones/danos-adicionales/{id_dano}/decision", json=decision_payload, headers=headers)
    assert dec_res.status_code == 200
    dec_data = dec_res.json()
    assert dec_data["dano"]["estado"] == "APROBADO"
    # Costo anterior era 180.0 + 65.0 = 245.0
    assert dec_data["costo_total_actualizado"] == 245.0


def test_proceso_7_1_dano_adicional_rechazado(client: TestClient):
    """Proceso 7.1: Hallazgo rechazado por el cliente no suma costo a la orden."""
    headers = get_auth_headers(client)

    payload = {
        "id_registro": 1,
        "id_mecanico": 2,
        "descripcion": "Leve fisura en plástico de tolva de motor",
        "costo_estimado": 30.0,
    }
    rep_res = client.post("/api/reparaciones/danos-adicionales", json=payload, headers=headers)
    assert rep_res.status_code == 201
    id_dano = rep_res.json()["id_dano"]

    dec_res = client.post(
        f"/api/reparaciones/danos-adicionales/{id_dano}/decision",
        json={"aprobado": False, "observaciones_cliente": "No autorizado por el momento"},
        headers=headers,
    )
    assert dec_res.status_code == 200
    dec_data = dec_res.json()
    assert dec_data["dano"]["estado"] == "RECHAZADO"

    # Verificar que el registro mantuvo el costo en 245.0
    reg = client.get("/api/registros/1", headers=headers).json()
    assert reg["costo_total"] == 245.0


def test_proceso_8_1_control_calidad_no_pasa_devuelve_al_mecanico_sin_costo(client: TestClient):
    """Proceso 8 y 8.1: Control de calidad no superado -> Se devuelve al mecánico para corregir sin cobrar extra."""
    headers = get_auth_headers(client)

    payload = {
        "id_registro": 1,
        "id_revisor": 1,
        "paso_inspeccion": False,
        "escaner_utilizado": "Launch X431 Pro",
        "codigos_dtc_detectados": "P0016 (Desfase de posición árbol de levas / cigüeñal)",
        "motivo_devolucion": "Banda fuera de punto por 1 diente. Requiere puesta a punto exacta sin costo adicional.",
    }
    qc_res = client.post("/api/reparaciones/control-calidad", json=payload, headers=headers)
    assert qc_res.status_code == 201
    qc_data = qc_res.json()
    assert qc_data["control"]["accion_tomada"] == "DEVUELTO_A_MECANICO"
    assert qc_data["estado_orden"] == 2  # Continúa en reparación / reproceso


def test_proceso_8_y_9_control_calidad_aprobado_marca_listo_para_entrega(client: TestClient):
    """Procesos 8 y 9: Control de calidad superado con escaneo limpio -> Orden pasa a estado 3 (LISTO PARA ENTREGA)."""
    headers = get_auth_headers(client)

    payload = {
        "id_registro": 1,
        "id_revisor": 1,
        "paso_inspeccion": True,
        "escaner_utilizado": "Launch X431 Pro",
        "codigos_dtc_detectados": "Sin códigos de falla. Sincronización perfecta.",
        "observaciones": "Prueba de ruta exitosa. Parámetros en rango óptimo.",
    }
    qc_res = client.post("/api/reparaciones/control-calidad", json=payload, headers=headers)
    assert qc_res.status_code == 201
    qc_data = qc_res.json()
    assert qc_data["control"]["accion_tomada"] == "APROBADO_LISTO"
    assert qc_data["estado_orden"] == 3  # Estado 3: Reparado / Listo para entrega (Proceso 9)

    reg = client.get("/api/registros/1", headers=headers).json()
    assert reg["estado"] == 3
    assert reg["fecha_completado"] is not None
