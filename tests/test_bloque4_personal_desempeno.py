"""Pruebas del Bloque 4: Ficha laboral (RF-40), horarios (RF-41), asistencia (RF-42) y reporte de desempeño (RF-58)."""
from datetime import date, datetime, timedelta
from sqlalchemy.orm import Session

from tests.test_permisos import api
from app.modules.taller.models import BitacoraReparacion, Registro


def test_rf40_perfil_laboral_y_permisos(api):
    client, headers, _ = api

    assert client.get("/api/personal/perfiles", headers=headers[2]).status_code == 403
    assert client.get("/api/personal/perfiles", headers=headers[4]).status_code == 403

    # No permite asignar perfil laboral a un cliente
    bad_cli = client.put(
        "/api/personal/4/perfil-laboral",
        json={"cargo": "Mecánico", "modalidad_pago": "HORA", "tarifa_hora": 12.0},
        headers=headers[1],
    )
    assert bad_cli.status_code == 400

    # Actualizar perfil laboral del mecánico 2
    ok = client.put(
        "/api/personal/2/perfil-laboral",
        json={
            "cargo": "Mecánico Senior",
            "especialidad": "Diagnóstico electrónico y motores",
            "fecha_ingreso": "2025-03-01",
            "tipo_contrato": "TIEMPO_COMPLETO",
            "modalidad_pago": "HORA",
            "tarifa_hora": 12.5,
            "salario_base": 650.0,
        },
        headers=headers[1],
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["cargo"] == "Mecánico Senior"
    assert ok.json()["tarifa_hora"] == 12.5

    # Mecánico 2 consulta su propia ficha laboral pero no la de otro mecánico
    assert client.get("/api/personal/2/perfil-laboral", headers=headers[2]).status_code == 200
    assert client.get("/api/personal/3/perfil-laboral", headers=headers[2]).status_code == 403

    perfiles = client.get("/api/personal/perfiles", headers=headers[1]).json()
    assert any(p["id_usuario"] == 2 and p["perfil_laboral"]["cargo"] == "Mecánico Senior" for p in perfiles)


def test_rf41_horarios_validacion_y_acceso(api):
    client, headers, _ = api

    # Hora salida <= hora entrada se rechaza
    bad_hr = client.put(
        "/api/personal/horarios/2",
        json={"horarios": [{"dia_semana": 0, "es_laborable": True, "hora_entrada": "17:00", "hora_salida": "08:00"}]},
        headers=headers[1],
    )
    assert bad_hr.status_code == 400

    # Descanso mayor o igual a la jornada se rechaza
    bad_break = client.put(
        "/api/personal/horarios/2",
        json={"horarios": [{"dia_semana": 0, "es_laborable": True, "hora_entrada": "08:00", "hora_salida": "10:00", "minutos_descanso": 120}]},
        headers=headers[1],
    )
    assert bad_break.status_code == 400

    # Guardar horario semanal válido
    ok = client.put(
        "/api/personal/horarios/2",
        json={
            "horarios": [
                {"dia_semana": 0, "es_laborable": True, "hora_entrada": "08:00", "hora_salida": "17:00", "minutos_descanso": 60},
                {"dia_semana": 6, "es_laborable": False, "hora_entrada": "00:00", "hora_salida": "00:00", "minutos_descanso": 0},
            ]
        },
        headers=headers[1],
    )
    assert ok.status_code == 200, ok.text
    assert len(ok.json()) == 2

    # Mecánico solo lee su propio horario
    assert len(client.get("/api/personal/horarios", headers=headers[2]).json()) == 2
    assert client.get("/api/personal/horarios?id_usuario=3", headers=headers[2]).status_code == 403
    assert client.get("/api/personal/horarios", headers=headers[4]).status_code == 403


def test_rf42_asistencia_calculo_horas_duplicidad_y_edicion(api):
    client, headers, _ = api
    hoy = date.today().isoformat()

    # Coherencia de horas
    bad = client.post(
        "/api/personal/asistencia",
        json={"id_usuario": 2, "fecha": hoy, "estado": "PRESENTE", "hora_entrada": "18:00", "hora_salida": "09:00"},
        headers=headers[1],
    )
    assert bad.status_code == 400

    # Registro válido: 08:00 a 17:00 - 60 min descanso = 8.0 horas
    ok = client.post(
        "/api/personal/asistencia",
        json={
            "id_usuario": 2,
            "fecha": hoy,
            "turno": "UNICO",
            "estado": "PRESENTE",
            "hora_entrada": "08:00",
            "hora_salida": "17:00",
            "minutos_descanso": 60,
        },
        headers=headers[1],
    )
    assert ok.status_code == 201, ok.text
    assert ok.json()["horas_trabajadas"] == 8.0
    id_asist = ok.json()["id_asistencia"]

    # Duplicar mismo mecánico, fecha y turno -> 409 Conflict
    dup = client.post(
        "/api/personal/asistencia",
        json={
            "id_usuario": 2,
            "fecha": hoy,
            "turno": "UNICO",
            "estado": "PRESENTE",
            "hora_entrada": "08:00",
            "hora_salida": "12:00",
        },
        headers=headers[1],
    )
    assert dup.status_code == 409

    # Corrección de asistencia recalcula horas y deja auditoría
    upd = client.put(
        f"/api/personal/asistencia/{id_asist}",
        json={"estado": "TARDANZA", "hora_entrada": "08:30", "hora_salida": "17:00", "minutos_descanso": 60},
        headers=headers[1],
    )
    assert upd.status_code == 200
    assert upd.json()["horas_trabajadas"] == 7.5
    assert upd.json()["estado"] == "TARDANZA"

    # Resumen acumulado y permisos
    res = client.get(f"/api/personal/asistencia?fecha_inicio={hoy}&fecha_fin={hoy}", headers=headers[1]).json()
    assert res["resumen"]["total_horas_trabajadas"] == 7.5
    assert res["resumen"]["conteo_estados"]["TARDANZA"] == 1
    assert client.get("/api/personal/asistencia?id_usuario=3", headers=headers[2]).status_code == 403


def test_rf58_reporte_desempeno_mecanicos(api):
    client, headers, engine = api
    hoy = date.today()
    with Session(engine) as db:
        reg1 = db.get(Registro, 1)
        reg1.estado = 2
        reg1.fecha_entrega_estimada = datetime.combine(hoy + timedelta(days=1), datetime.min.time())
        reg1.fecha_completado = datetime.now()
        db.add(BitacoraReparacion(id_registro=1, id_mecanico=2, horas_trabajadas=3.5, descripcion_trabajo="Ajuste de frenos"))
        db.commit()

    assert client.post(
        "/api/personal/asistencia",
        json={"id_usuario": 2, "fecha": hoy.isoformat(), "estado": "PRESENTE", "hora_entrada": "08:00", "hora_salida": "16:00"},
        headers=headers[1],
    ).status_code == 201

    assert client.get("/api/personal/reportes/desempeno", headers=headers[2]).status_code == 403
    assert client.get("/api/personal/reportes/desempeno?fecha_inicio=2026-12-10&fecha_fin=2026-12-01", headers=headers[1]).status_code == 400

    rep = client.get("/api/personal/reportes/desempeno?id_mecanico=2", headers=headers[1])
    assert rep.status_code == 200, rep.text
    body = rep.json()
    assert len(body["mecanicos"]) == 1
    m2 = body["mecanicos"][0]
    assert m2["id_mecanico"] == 2
    assert m2["ordenes_asignadas"] == 1
    assert m2["ordenes_completadas"] == 1
    assert m2["cumplimiento_plazos_pct"] == 100.0
    assert m2["horas_taller"] == 3.5
    assert m2["horas_asistencia"] == 8.0
    assert m2["diagnosticos_realizados"] == 1
