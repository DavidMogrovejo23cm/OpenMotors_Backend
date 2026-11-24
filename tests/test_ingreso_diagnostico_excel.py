"""RF-05/12/18/65/66: ingreso real, evidencias y diagnóstico escrito."""
import base64

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tests.test_permisos import api
from tests.test_flujo_inventario_herramientas import request_ok
from app.modules.taller.models import DiagnosticoVehiculo, Registro, RecepcionVehiculo
from app.modules.usuarios.models import Usuario

FOTOS = {
    "foto_frente": "/static/frente.png", "foto_posterior": "/static/posterior.png",
    "foto_lateral_izq": "/static/izq.png", "foto_lateral_der": "/static/der.png",
    "firma_cliente": "data:image/png;base64,firma",
}


def ingreso(client, headers, **extra):
    return request_ok(client, "POST", "/api/recepciones", headers, {
        "id_vehiculo": 1, "id_encargado": 2, "kilometraje": 1000, **FOTOS, **extra,
    })


def diagnostico(rec, **extra):
    return {"id_vehiculo": 1, "id_mecanico": 2, "id_registro": rec["id_registro"],
            "observaciones_generales": "Se detecta vibración al frenar; revisar discos.",
            "origen_diagnostico": "CRITERIO_TECNICO", **extra}


@pytest.mark.parametrize("origen,datos", [
    ("CRITERIO_TECNICO", {}),
    ("ESCANER", {"escaner_utilizado": "Autel", "codigos_dtc": "P0300", "descripcion_escaner": "Fallo de encendido múltiple observado"}),
    ("AMBOS", {"descripcion_escaner": "Sin códigos de falla; lectura de sensores dentro de rango"}),
])
def test_rf65_rf66_guarda_origen_hallazgos_fecha_responsable_y_orden(api, origen, datos):
    c, h, engine = api
    rec = ingreso(c, h[1])
    result = request_ok(c, "POST", "/api/diagnosticos", h[2], diagnostico(rec, origen_diagnostico=origen, **datos))
    assert result["origen_diagnostico"] == origen
    assert result["id_registro"] == rec["id_registro"]
    assert result["id_recepcion"] == rec["id_recepcion"]
    assert result["id_mecanico"] == 2 and result["fecha"]
    assert result["kilometraje_ingreso"] == 1000
    assert "vibración" in result["observaciones_generales"]
    for key, value in datos.items():
        assert result[key] == value
    with Session(engine) as db:
        assert db.get(Registro, rec["id_registro"]).estado == 1
    detail = request_ok(c, "GET", f"/api/registros/{rec['id_registro']}/flujo", h[4])
    assert detail["diagnosticos"][0]["id_diagnostico"] == result["id_diagnostico"]


@pytest.mark.parametrize("faltante", list(FOTOS))
def test_no_diagnostica_si_falta_cualquier_lado_o_firma(api, faltante):
    c, h, engine = api
    rec = ingreso(c, h[1], **{faltante: "   "})
    assert not rec["completa"] and faltante in rec["faltantes"]
    assert c.post("/api/diagnosticos", headers=h[2], json=diagnostico(rec)).status_code == 400
    with Session(engine) as db:
        assert db.query(DiagnosticoVehiculo).filter_by(id_registro=rec["id_registro"]).count() == 0
        assert db.get(Registro, rec["id_registro"]).estado == 0
    request_ok(c, "PUT", f"/api/recepciones/{rec['id_recepcion']}", h[1], {faltante: FOTOS[faltante]})
    request_ok(c, "POST", "/api/diagnosticos", h[2], diagnostico(rec))


@pytest.mark.parametrize("cambio", [
    {"id_registro": None},
    {"observaciones_generales": "   "},
    {"id_recepcion": 9999},
    {"id_mecanico": 9999},
    {"id_mecanico": 4},
    {"kilometraje_ingreso": 500},
    {"origen_diagnostico": "ESCANER", "escaner_utilizado": "Autel"},
    {"origen_diagnostico": "AMBOS", "codigos_dtc": "  ", "descripcion_escaner": "  "},
    {"origen_diagnostico": "AUTOMATICO"},
    {"kilometraje_ingreso": -1},
])
def test_rechaza_diagnostico_incompleto_sin_guardar_ni_avanzar(api, cambio):
    c, h, engine = api
    rec = ingreso(c, h[1])
    result = c.post("/api/diagnosticos", headers=h[1], json=diagnostico(rec, **cambio))
    assert result.status_code in (400, 404, 422), result.text
    with Session(engine) as db:
        assert db.get(Registro, rec["id_registro"]).estado == 0
        assert db.query(DiagnosticoVehiculo).filter_by(id_registro=rec["id_registro"]).count() == 0


def test_recepcion_como_vinculo_y_no_permite_otra_orden(api):
    c, h, _ = api
    rec = ingreso(c, h[1])
    other = ingreso(c, h[1])
    assert c.post("/api/diagnosticos", headers=h[1], json=diagnostico(other, id_recepcion=rec["id_recepcion"])).status_code == 400
    result = request_ok(c, "POST", "/api/diagnosticos", h[2], diagnostico(rec, id_registro=None, id_recepcion=rec["id_recepcion"]))
    assert result["id_registro"] == rec["id_registro"]


def test_recepcion_no_usa_orden_de_otro_vehiculo_y_no_se_reasigna(api):
    c, h, _ = api
    assert c.post("/api/recepciones", headers=h[1], json={"id_vehiculo": 2, "id_registro": 3, "kilometraje": 0}).status_code == 400
    rec = ingreso(c, h[1])
    assert c.put(f"/api/recepciones/{rec['id_recepcion']}", headers=h[1], json={"id_registro": 2}).status_code == 400
    assert c.post("/api/recepciones", headers=h[1], json={"id_vehiculo": 1, "id_registro": rec["id_registro"], "kilometraje": 0}).status_code == 400


def test_recepcion_inmutable_despues_del_diagnostico_y_orden_cerrada(api):
    c, h, engine = api
    rec = ingreso(c, h[1])
    request_ok(c, "POST", "/api/diagnosticos", h[2], diagnostico(rec))
    assert c.put(f"/api/recepciones/{rec['id_recepcion']}", headers=h[1], json={"foto_frente": " "}).status_code == 400
    for estado in (2, 3):
        with Session(engine) as db:
            db.get(Registro, rec["id_registro"]).estado = estado
            db.commit()
        assert c.post("/api/diagnosticos", headers=h[2], json=diagnostico(rec)).status_code == 400


def test_cliente_nuevo_vehiculo_cuatro_fotos_reales_y_diagnostico(api, monkeypatch, tmp_path):
    c, h, _ = api
    import app.shared.storage_service as storage
    monkeypatch.setattr(storage, "LOCAL_UPLOAD_ROOT", tmp_path)
    account = request_ok(c, "POST", "/api/quick-accounts/create", h[1], {
        "nombreCompleto": "Cliente de recepción", "correo": "ingreso@example.test", "cedula": "0123456789",
        "telefono": "0991234567", "placa": "ING-2026", "marca": "Kia", "modelo": "Rio", "anio": 2024, "kilometraje": 1000,
    })
    vehicle_id = account["vehiculo"]["id_vehiculo"]
    assert account["vehiculo"]["id_usuario"] == account["usuario"]["id_usuario"]
    photos = {}
    png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aXioAAAAASUVORK5CYII=")
    for key in FOTOS:
        response = c.post(f"/api/recepciones/fotos?tipo={key.removeprefix('foto_')}", headers={"Authorization": h[1]["Authorization"]}, files={"archivo": (key + '.png', png, 'image/png')})
        assert response.status_code == 200, response.text
        photos[key] = response.json()["url"]
    assert len(set(photos.values())) == 5
    assert len(list(tmp_path.rglob('*.png'))) == 5
    rec = ingreso(c, h[1], id_vehiculo=vehicle_id, **photos)
    result = request_ok(c, "POST", "/api/diagnosticos", h[2], diagnostico(rec, id_vehiculo=vehicle_id, origen_diagnostico="AMBOS", descripcion_escaner="P0300; el mecánico identifica bujía desgastada"))
    assert result["id_vehiculo"] == vehicle_id


def test_cuenta_rapida_no_mezcla_cliente_con_vehiculo_ajeno(api):
    c, h, engine = api
    with Session(engine) as db:
        total = db.scalar(select(func.count()).select_from(Usuario))
    result = c.post("/api/quick-accounts/create", headers=h[1], json={"nombreCompleto": "Otro propietario", "correo": "otro@example.test", "placa": "ABC-1001", "marca": "Kia", "modelo": "Rio"})
    assert result.status_code == 409, result.text
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(Usuario)) == total


@pytest.mark.parametrize("cambio", [{"marca": " "}, {"modelo": ""}, {"id_usuario": 99999}, {"kilometraje": -1}])
def test_rf07_rf08_no_crea_vehiculo_incompleto_o_sin_propietario(api, cambio):
    c, h, _ = api
    result = c.post("/api/vehiculos", headers=h[1], json={"placa": "NEW-2026", "marca": "Kia", "modelo": "Rio", "id_usuario": 4, **cambio})
    assert result.status_code in (400, 404, 422), result.text


@pytest.mark.parametrize("cambio", [
    {"monto": 0}, {"monto": -10}, {"concepto": "   "}, {"id_empleado": -1},
    {"id_empleado": 9999}, {"id_empleado": 4}, {"fecha": "ayer"},
])
def test_rf32_rf43_gasto_invalido_no_altera_los_movimientos(api, cambio):
    c, h, _ = api
    initial = c.get('/api/pagos-empleado', headers=h[1]).json()
    result = c.post('/api/pagos-empleado', headers=h[1], json={"id_empleado": 2, "monto": 10, "concepto": "Sueldo", **cambio})
    assert result.status_code in (400, 404), result.text
    assert c.get('/api/pagos-empleado', headers=h[1]).json() == initial


@pytest.mark.parametrize("employee", [0, 2])
def test_rf32_rf43_gasto_general_y_pago_a_mecanico_persisten(api, employee):
    c, h, _ = api
    result = request_ok(c, 'POST', '/api/pagos-empleado', h[1], {"id_empleado": employee, "monto": 25.50, "concepto": "Gasto de taller" if employee == 0 else "Sueldo"})
    assert result['monto'] == 25.50
    assert any(p['id_pago'] == result['id_pago'] for p in c.get('/api/pagos-empleado', headers=h[1]).json())


def test_rnf01_password_con_hash_y_login_invalido(api):
    c, h, engine = api
    password = 'PruebaSegura123'
    result = request_ok(c, 'POST', '/api/usuarios', h[1], {"nombre_completo": "Cliente hash", "nombre_usuario": "hash-test", "correo": "hash@example.test", "contrasena": password})
    assert 'contrasena' not in result and password not in str(result)
    from app.core.security import verify_password
    with Session(engine) as db:
        stored = db.get(Usuario, result['id_usuario']).contrasena
        assert stored != password and stored.startswith('$2')
        assert verify_password(password, stored)
    invalid = c.post('/api/usuarios/login', json={"nombre_usuario": "hash-test", "contrasena": "incorrecta"})
    assert invalid.status_code in (400, 401)
    assert 'token' not in invalid.json()


def test_no_se_puede_omitir_fotos_usando_orden_historica(api):
    c, h, _ = api
    # La orden 1 es histórica y no usa flujo_integrado; tampoco debe saltar recepción.
    result = c.post('/api/diagnosticos', headers=h[2], json={"id_vehiculo": 1, "id_registro": 1, "id_mecanico": 2, "observaciones_generales": "Revisión de frenos"})
    assert result.status_code == 400, result.text
