"""Pruebas del Bloque 2: Estimación de tiempo en órdenes (RF-15) y reportes de trabajos por período (RF-54)."""
from datetime import date, timedelta
from sqlalchemy.orm import Session

from tests.test_permisos import api
from app.modules.taller.models import Registro, BitacoraReparacion


def test_rf15_estimacion_tiempo_validacion_y_actualizacion(api):
    client, headers, engine = api
    hoy = date.today()
    ayer = (hoy - timedelta(days=1)).isoformat()
    pasado_manana = (hoy + timedelta(days=2)).isoformat()

    # Fecha estimada anterior al ingreso se rechaza
    bad_date = client.post(
        "/api/registros",
        json={
            "id_vehiculo": 1,
            "fecha": hoy.isoformat(),
            "fecha_entrega_estimada": ayer,
            "horas_estimadas": 3.5,
        },
        headers=headers[1],
    )
    assert bad_date.status_code == 400

    # Horas negativas se rechazan
    bad_hours = client.post(
        "/api/registros",
        json={
            "id_vehiculo": 1,
            "fecha": hoy.isoformat(),
            "fecha_entrega_estimada": pasado_manana,
            "horas_estimadas": -2,
        },
        headers=headers[1],
    )
    assert bad_hours.status_code in (400, 422)

    # Creación válida guarda fecha estimada y horas estimadas
    ok_res = client.post(
        "/api/registros",
        json={
            "id_vehiculo": 1,
            "id_encargado": 2,
            "fecha": hoy.isoformat(),
            "fecha_entrega_estimada": pasado_manana,
            "horas_estimadas": 4.5,
            "descripcion": "Mantenimiento preventivo completo",
        },
        headers=headers[1],
    )
    assert ok_res.status_code == 201, ok_res.text
    creada = ok_res.json()
    assert creada["horas_estimadas"] == 4.5
    assert creada["fecha_entrega_estimada"].startswith(pasado_manana)
    id_orden = creada["id_registro"]

    # Cliente no puede editar estimación
    assert client.patch(
        f"/api/registros/{id_orden}/estimacion",
        json={"horas_estimadas": 6.0},
        headers=headers[4],
    ).status_code == 403

    # Mecánico asignado puede actualizar estimación coherente
    nuevo_plazo = (hoy + timedelta(days=4)).isoformat()
    upd_res = client.patch(
        f"/api/registros/{id_orden}/estimacion",
        json={"fecha_entrega_estimada": nuevo_plazo, "horas_estimadas": 6.0},
        headers=headers[2],
    )
    assert upd_res.status_code == 200, upd_res.text
    assert upd_res.json()["horas_estimadas"] == 6.0
    assert upd_res.json()["fecha_entrega_estimada"].startswith(nuevo_plazo)

    # No permite fecha anterior al ingreso al actualizar
    assert client.patch(
        f"/api/registros/{id_orden}/estimacion",
        json={"fecha_entrega_estimada": ayer},
        headers=headers[1],
    ).status_code == 400

    # Orden entregada no admite cambios de estimación
    with Session(engine) as db:
        db.get(Registro, id_orden).estado = 3
        db.commit()
    assert client.patch(
        f"/api/registros/{id_orden}/estimacion",
        json={"horas_estimadas": 8.0},
        headers=headers[1],
    ).status_code == 400


def test_rf54_reporte_trabajos_por_periodo_y_filtros(api):
    client, headers, engine = api
    with Session(engine) as db:
        db.add(BitacoraReparacion(id_registro=1, id_mecanico=2, horas_trabajadas=2.5, descripcion_trabajo="Cambio de pastillas"))
        db.commit()

    # Solo ADMIN puede generar el reporte consolidado
    assert client.get("/api/registros/reportes/trabajos", headers=headers[2]).status_code == 403
    assert client.get("/api/registros/reportes/trabajos", headers=headers[4]).status_code == 403

    # Rango invertido se rechaza
    bad_range = client.get(
        "/api/registros/reportes/trabajos?fecha_inicio=2026-12-10&fecha_fin=2026-12-01",
        headers=headers[1],
    )
    assert bad_range.status_code == 400

    # Consulta global de órdenes en pruebas (hay 3 órdenes en fixture api)
    rep = client.get("/api/registros/reportes/trabajos", headers=headers[1])
    assert rep.status_code == 200, rep.text
    body = rep.json()
    assert body["resumen"]["total_ordenes"] == 3
    assert body["resumen"]["horas_trabajadas_totales"] == 2.5
    assert body["resumen"]["conteo_por_estado"]["en_proceso"] == 3

    # Filtro por mecánico 2 devuelve solo orden 1
    rep_mec = client.get("/api/registros/reportes/trabajos?id_encargado=2", headers=headers[1])
    assert rep_mec.status_code == 200
    assert rep_mec.json()["resumen"]["total_ordenes"] == 1
    assert rep_mec.json()["items"][0]["id_registro"] == 1

    # Período futuro sin registros devuelve vacío limpio
    empty_rep = client.get(
        "/api/registros/reportes/trabajos?fecha_inicio=2099-01-01&fecha_fin=2099-01-31",
        headers=headers[1],
    )
    assert empty_rep.status_code == 200
    assert empty_rep.json()["resumen"]["total_ordenes"] == 0
    assert empty_rep.json()["items"] == []
