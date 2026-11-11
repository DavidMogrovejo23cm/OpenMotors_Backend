import os
import pytest
from fastapi.testclient import TestClient

os.environ["DB_URL"] = "sqlite:///./test_fase_e.sqlite"
os.environ["JWT_SECRET"] = "supersecretkeyformodulartesting12345"

from app.main import app
from app.core.database import Base, engine, SessionLocal
from app.core.seeder import init_db_and_seed
from app.modules.vehiculos.models import Vehiculo
from app.modules.taller.models import Registro, Presupuesto, ItemPresupuesto
from app.modules.facturacion.models import NotaDeVenta
from app.modules.mantenimiento.models import ParametroMantenimiento, MantenimientoRealizado


@pytest.fixture(scope="module")
def client():
    Base.metadata.drop_all(bind=engine)
    init_db_and_seed()

    db = SessionLocal()
    vehiculo = Vehiculo(
        placa="PCR-9090",
        marca="Mazda",
        modelo="CX-5",
        anio=2024,
        kilometraje=10000,
        cilindraje=2000,
        id_usuario=1,
    )
    db.add(vehiculo)
    db.commit()
    db.refresh(vehiculo)

    # Orden pagada lista para entrega (Estado 7)
    reg_pagado = Registro(
        id_vehiculo=vehiculo.id_vehiculo,
        id_encargado=2,
        descripcion="Cambio de aceite de motor y filtro",
        costo_total=50.0,
        estado=7,  # Estado 7: PAGADO
        kilometraje=10000,
    )
    # Orden no pagada
    reg_no_pagado = Registro(
        id_vehiculo=vehiculo.id_vehiculo,
        id_encargado=2,
        descripcion="Revisión de frenos pendiente de cobro",
        costo_total=80.0,
        estado=3,  # Estado 3 pero aún NO pagada
        kilometraje=10000,
    )
    db.add(reg_pagado)
    db.add(reg_no_pagado)
    db.commit()
    db.refresh(reg_pagado)
    db.refresh(reg_no_pagado)

    # Nota de venta pagada para la primera orden
    nv = NotaDeVenta(
        numero_nota_venta="NV-2026-9999",
        id_registro=reg_pagado.id_registro,
        cliente_nombre="Dagumo",
        total=50.0,
        estado_pago="PAGADO",
    )
    db.add(nv)

    # Presupuesto para registrar repuesto cambiado
    pres = Presupuesto(
        numero_presupuesto="PRE-2026-8888",
        id_registro=reg_pagado.id_registro,
        id_vehiculo=vehiculo.id_vehiculo,
        estado="APROBADO_TOTAL",
        total_presupuestado=50.0,
        total_aprobado=50.0,
    )
    db.add(pres)
    db.flush()

    it = ItemPresupuesto(
        id_presupuesto=pres.id_presupuesto,
        tipo_item="REPUESTO",
        descripcion="Aceite de Motor Sintético",
        cantidad=1.0,
        precio_unitario=50.0,
        subtotal=50.0,
        estado_aprobacion="APROBADO",
    )
    db.add(it)
    db.commit()
    db.close()

    with TestClient(app) as c:
        yield c

    engine.dispose()
    if os.path.exists("./test_fase_e.sqlite"):
        try:
            os.remove("./test_fase_e.sqlite")
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


def test_proceso_15_bloqueo_entrega_sin_pago(client: TestClient):
    """Proceso 11.1 / Proceso 15: No se permite entregar el vehículo si la orden no está pagada."""
    headers = get_auth_headers(client)

    payload = {
        "id_registro": 2,  # Orden no pagada
        "persona_recibe": "Cliente Apurado",
        "kilometraje_salida": 10000,
    }
    res = client.post("/api/entregas", json=payload, headers=headers)
    assert res.status_code == 400
    res_json = res.json()
    msg = res_json.get("error") or res_json.get("detail", "")
    assert "no ha sido pagada" in msg


def test_proceso_15_entrega_conforme_vehiculo_pagado(client: TestClient):
    """Proceso 15: Entrega física de orden pagada con firma y reinicio de ciclo de repuestos."""
    headers = get_auth_headers(client)

    payload = {
        "id_registro": 1,  # Orden pagada (Estado 7)
        "persona_recibe": "Dagumo",
        "cedula_recibe": "1712345678",
        "firma_cliente_entrega": "data:image/png;base64,FIRMA_CONFORME_SALIDA",
        "kilometraje_salida": 10005,
        "observaciones": "Vehículo entregado limpio y probado a satisfacción del cliente",
        "id_usuario_entrega": 1,
    }
    res = client.post("/api/entregas", json=payload, headers=headers)
    assert res.status_code == 201
    data = res.json()

    assert data["exito"] is True
    assert data["estado_orden"] == 4  # Estado 4: Entregado / Finalizado
    assert data["entrega"]["kilometraje_salida"] == 10005
    assert data["entrega"]["persona_recibe"] == "Dagumo"


def test_proceso_15_1_semaforo_verde_menor_70_porciento(client: TestClient):
    """Proceso 15.1: Desgaste < 70% -> Mantener semáforo en VERDE y seguir monitoreando."""
    headers = get_auth_headers(client)

    res = client.get("/api/alertas/vehiculo/1/semaforo", headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert data["kilometraje_actual"] == 10005
    # La pieza recién cambiada (Aceite) está en 0% de desgaste y el resto en verde
    piezas_verdes = data["piezas_en_rango_verde"]
    assert len(piezas_verdes) >= 1
    # Verificar que el mensaje indica mantener en verde (Proceso 15.1)
    aceite_estado = next((p for p in piezas_verdes if "Aceite" in p["tipo"]), None)
    if aceite_estado:
        assert aceite_estado["semaforo"] == "VERDE"
        assert aceite_estado["porcentajeDesgaste"] < 70


def test_proceso_16_semaforo_amarillo_y_aviso_predictivo(client: TestClient):
    """Proceso 16: Desgaste >= 70% -> Semáforo AMARILLO/ROJO y aviso de revisión al cliente."""
    headers = get_auth_headers(client)

    # Simular que el vehículo avanzó a 20000 km (en ciclo de 7000 km -> 6000 km recorridos = 85% de desgaste >= 70%)
    up_res = client.put("/api/vehiculos/1", json={"kilometraje": 20000}, headers=headers)
    assert up_res.status_code == 200

    res = client.get("/api/alertas/vehiculo/1/semaforo", headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert data["piezas_en_alerta"] >= 1
    alerta_item = data["piezas_alerta_o_reemplazo"][0]
    assert alerta_item["porcentajeDesgaste"] >= 70
    assert alerta_item["semaforo"] in ("AMARILLO", "ROJO")
    assert alerta_item["requiereAviso"] is True

    # Verificar endpoint de disparo de avisos
    aviso_res = client.post("/api/alertas/verificar/1", headers=headers)
    assert aviso_res.status_code == 200
    assert aviso_res.json()["mensaje"] == "Verificación completada"


def test_proceso_16_agendar_cita_preventiva(client: TestClient):
    """Proceso 16: Permitir al cliente agendar cita de mantenimiento preventivo a partir del aviso."""
    headers = get_auth_headers(client)

    payload = {
        "id_vehiculo": 1,
        "id_usuario": 1,
        "fecha_agendada": "2026-11-20T10:00:00",
        "piezas_a_revisar": "Aceite de Motor, Pastillas de Freno",
        "observaciones": "Cita agendada automáticamente tras alerta de desgaste al 90%",
    }
    res = client.post("/api/citas-mantenimiento", json=payload, headers=headers)
    assert res.status_code == 201
    data = res.json()

    assert data["exito"] is True
    assert data["cita"]["estado"] == "AGENDADA"
    assert "Aceite" in data["cita"]["piezas_a_revisar"]

    # Consultar citas agendadas
    citas_res = client.get("/api/citas-mantenimiento?id_vehiculo=1", headers=headers)
    assert citas_res.status_code == 200
    citas_lista = citas_res.json()
    assert len(citas_lista) >= 1
