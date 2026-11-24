"""Pruebas del Bloque 3: Catálogo financiero (RF-33), deudas por cliente (RF-36), caja y arqueo (RF-37), y resumen por período (RF-38)."""
from datetime import date
from tests.test_permisos import api


def test_rf33_catalogo_categorias_y_filtrado_gastos(api):
    client, headers, _ = api

    # Solo ADMIN accede al catálogo
    assert client.get("/api/finanzas/categorias", headers=headers[2]).status_code == 403
    cats = client.get("/api/finanzas/categorias?tipo=EGRESO", headers=headers[1])
    assert cats.status_code == 200
    nombres = [c["nombre"] for c in cats.json()]
    assert "Alquiler" in nombres
    assert "Sueldo" in nombres

    # Crear categoría nueva y rechazar duplicada
    new_cat = client.post(
        "/api/finanzas/categorias",
        json={"nombre": "Publicidad", "tipo": "EGRESO", "descripcion": "Pauta y volantes"},
        headers=headers[1],
    )
    assert new_cat.status_code == 201
    assert client.post(
        "/api/finanzas/categorias",
        json={"nombre": "publicidad", "tipo": "EGRESO"},
        headers=headers[1],
    ).status_code == 409

    # Categoría explícita inexistente rechazada
    bad_exp = client.post(
        "/api/pagos-empleado",
        json={"id_empleado": 0, "concepto": "Gasto raro", "categoria": "Categoria Inventada", "monto": 20},
        headers=headers[1],
    )
    assert bad_exp.status_code == 400

    # Registrar gasto con categoría válida y filtrar por categoría
    ok_exp = client.post(
        "/api/pagos-empleado",
        json={"id_empleado": 0, "concepto": "Volantes mayo", "categoria": "Publicidad", "monto": 35.5},
        headers=headers[1],
    )
    assert ok_exp.status_code == 201
    assert ok_exp.json()["categoria"] == "Publicidad"

    filtrados = client.get("/api/pagos-empleado?categoria=Publicidad", headers=headers[1])
    assert filtrados.status_code == 200
    assert len(filtrados.json()) == 1
    assert filtrados.json()[0]["monto"] == 35.5


def test_rf37_flujo_completo_caja_y_auditoria(api):
    client, headers, _ = api

    # Mecánico y cliente bloqueados
    assert client.get("/api/caja/resumen", headers=headers[2]).status_code == 403
    assert client.post("/api/caja/apertura", json={"monto_inicial": 100}, headers=headers[4]).status_code == 403

    # Abrir caja con $100
    ap = client.post("/api/caja/apertura", json={"monto_inicial": 100, "observaciones": "Turno mañana"}, headers=headers[1])
    assert ap.status_code == 201, ap.text
    assert ap.json()["estado"] == "ABIERTA"
    assert ap.json()["saldo_esperado"] == 100.0

    # No permite abrir segunda caja mientras esté abierta
    assert client.post("/api/caja/apertura", json={"monto_inicial": 50}, headers=headers[1]).status_code == 400

    # Ingreso manual $40 -> saldo 140
    ing = client.post(
        "/api/caja/movimientos",
        json={"tipo": "INGRESO", "monto": 40, "motivo": "Fondo adicional de cambio"},
        headers=headers[1],
    )
    assert ing.status_code == 201
    assert ing.json()["saldo_resultante"] == 140.0

    # Retiro mayor al saldo -> 400 sin alterar saldo
    bad_ret = client.post(
        "/api/caja/movimientos",
        json={"tipo": "RETIRO", "monto": 200, "motivo": "Compra urgente"},
        headers=headers[1],
    )
    assert bad_ret.status_code == 400
    assert client.get("/api/caja/resumen", headers=headers[1]).json()["saldo_actual"] == 140.0

    # Retiro válido de $25 -> saldo 115
    ret = client.post(
        "/api/caja/movimientos",
        json={"tipo": "RETIRO", "monto": 25, "motivo": "Compra de agua y café"},
        headers=headers[1],
    )
    assert ret.status_code == 201
    assert ret.json()["saldo_resultante"] == 115.0

    # Un cobro en efectivo en orden 1 con caja abierta se refleja automáticamente en caja (+30 -> 145)
    pago_res = client.post(
        "/api/registros/1/pagos",
        json={"monto_recibido": 30, "metodo_pago": "EFECTIVO"},
        headers=headers[1],
    )
    assert pago_res.status_code == 201
    assert client.get("/api/caja/resumen", headers=headers[1]).json()["saldo_actual"] == 145.0

    # Cierre / Arqueo de caja con conteo físico $143 (diferencia -2)
    cierre = client.post(
        "/api/caja/cierre",
        json={"monto_fisico_contado": 143, "observaciones": "Faltante menor por monedas"},
        headers=headers[1],
    )
    assert cierre.status_code == 200
    assert cierre.json()["estado"] == "CERRADA"
    assert cierre.json()["saldo_esperado"] == 145.0
    assert cierre.json()["diferencia"] == -2.0

    # Auditoría de caja registrada
    aud = client.get("/api/sistema/auditoria", headers=headers[1]).json()
    acciones = {a["accion"] for a in aud}
    assert {"CAJA_APERTURA", "CAJA_INGRESO", "CAJA_RETIRO", "CAJA_CIERRE"}.issubset(acciones)


def test_rf36_rf38_deudas_por_cliente_y_resumen_periodo(api):
    client, headers, _ = api

    # En el fixture api: cliente 4 tiene orden 1 ($50) y cliente 5 tiene orden 2 ($50)
    deudas = client.get("/api/finanzas/deudas", headers=headers[1])
    assert deudas.status_code == 200
    body = deudas.json()
    assert body["total_clientes_con_deuda"] == 2
    assert body["total_cartera_pendiente"] == 100.0

    # Abono parcial de $20 a orden 1 del cliente 4 -> deuda cliente 4 baja a $30
    assert client.post("/api/registros/1/pagos", json={"monto_recibido": 20, "metodo_pago": "TRANSFERENCIA"}, headers=headers[1]).status_code == 201
    deuda_c4 = client.get("/api/finanzas/deudas?id_cliente=4", headers=headers[1]).json()
    assert deuda_c4["total_cartera_pendiente"] == 30.0
    assert deuda_c4["clientes"][0]["total_abonado"] == 20.0

    # Liquidar saldo restante de orden 1 ($30) -> cliente 4 sin deudas
    assert client.post("/api/registros/1/pagos", json={"monto_recibido": 30, "metodo_pago": "EFECTIVO"}, headers=headers[1]).status_code == 201
    sin_deuda_c4 = client.get("/api/finanzas/deudas?id_cliente=4", headers=headers[1]).json()
    assert sin_deuda_c4["total_clientes_con_deuda"] == 0
    assert sin_deuda_c4["clientes"] == []

    # Resumen por período
    hoy = date.today().isoformat()
    assert client.get("/api/finanzas/resumen-periodo?fecha_inicio=2026-12-10&fecha_fin=2026-12-01", headers=headers[1]).status_code == 400
    resumen = client.get(f"/api/finanzas/resumen-periodo?fecha_inicio={hoy}&fecha_fin={hoy}", headers=headers[1])
    assert resumen.status_code == 200
    r_data = resumen.json()
    assert r_data["ingresos_servicios"] == 50.0
    assert r_data["desglose_metodos"]["TRANSFERENCIA"] == 20.0
    assert r_data["desglose_metodos"]["EFECTIVO"] == 30.0

    # Reporte de notas de venta soporta rango de fechas y rechaza fechas invertidas
    assert client.get("/api/notas-venta/reportes/financiero?fecha_inicio=2026-12-10&fecha_fin=2026-12-01", headers=headers[1]).status_code == 400
    assert client.get(f"/api/notas-venta/reportes/financiero?fecha_inicio=2099-01-01&fecha_fin=2099-01-31", headers=headers[1]).json()["total_notas_cobradas"] == 0
