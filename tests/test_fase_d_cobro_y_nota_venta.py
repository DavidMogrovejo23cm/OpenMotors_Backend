import os
import pytest
from fastapi.testclient import TestClient

os.environ["DB_URL"] = "sqlite:///./test_fase_d.sqlite"
os.environ["JWT_SECRET"] = "supersecretkeyformodulartesting12345"

from app.main import app
from app.core.database import Base, engine, SessionLocal
from app.core.seeder import init_db_and_seed
from app.modules.vehiculos.models import Vehiculo
from app.modules.taller.models import Registro, Presupuesto, ItemPresupuesto, BitacoraReparacion
from app.modules.inventario.models import Producto, Categoria


@pytest.fixture(scope="module")
def client():
    Base.metadata.drop_all(bind=engine)
    init_db_and_seed()

    db = SessionLocal()
    cat = db.query(Categoria).first()
    if not cat:
        cat = Categoria(nombre="Suspensión", descripcion="Amortiguadores y terminales")
        db.add(cat)
        db.commit()
        db.refresh(cat)

    prod = Producto(
        codigo_personal="REP-TERMINAL-01",
        codigo_barras="7865554443332",
        nombre="Terminal de Dirección Moog",
        costo=20.0,
        pvp=40.0,
        stock=4,
        stock_reservado=1,
        stock_minimo=3,  # Con la salida quedará en 3 (alerta stock mínimo)
        id_categoria=cat.id_categoria,
    )
    db.add(prod)
    db.commit()
    db.refresh(prod)

    vehiculo = Vehiculo(
        placa="PCH-4455",
        marca="Kia",
        modelo="Sportage",
        anio=2023,
        kilometraje=15000,
        id_usuario=1,
    )
    db.add(vehiculo)
    db.commit()
    db.refresh(vehiculo)

    reg = Registro(
        id_vehiculo=vehiculo.id_vehiculo,
        id_encargado=2,
        descripcion="Cambio de terminal de dirección y alineación",
        costo_total=70.0,
        estado=3,  # Estado 3: Listo para cobro tras Proceso 9
        kilometraje=15000,
    )
    db.add(reg)
    db.commit()
    db.refresh(reg)

    # Bitácora con 2 horas de trabajo del mecánico
    bit = BitacoraReparacion(
        id_registro=reg.id_registro,
        id_mecanico=2,
        horas_trabajadas=2.0,
        descripcion_trabajo="Instalación de terminal y alineación en banco",
    )
    db.add(bit)

    # Presupuesto con 1 repuesto ($40) y mano de obra ($30)
    pres = Presupuesto(
        numero_presupuesto="PRE-2026-7777",
        id_registro=reg.id_registro,
        id_vehiculo=vehiculo.id_vehiculo,
        id_usuario=1,
        estado="APROBADO_TOTAL",
        total_presupuestado=70.0,
        total_aprobado=70.0,
    )
    db.add(pres)
    db.flush()

    it_rep = ItemPresupuesto(
        id_presupuesto=pres.id_presupuesto,
        tipo_item="REPUESTO",
        id_producto=prod.id_producto,
        descripcion="Terminal de Dirección Moog",
        cantidad=1.0,
        precio_unitario=40.0,
        subtotal=40.0,
        estado_aprobacion="APROBADO",
    )
    it_mo = ItemPresupuesto(
        id_presupuesto=pres.id_presupuesto,
        tipo_item="MANO_OBRA",
        descripcion="Alineación electrónica 3D",
        cantidad=1.0,
        precio_unitario=30.0,
        subtotal=30.0,
        estado_aprobacion="APROBADO",
    )
    db.add(it_rep)
    db.add(it_mo)
    db.commit()
    db.close()

    with TestClient(app) as c:
        yield c

    engine.dispose()
    if os.path.exists("./test_fase_d.sqlite"):
        try:
            os.remove("./test_fase_d.sqlite")
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


def test_proceso_10_preparar_cobro_y_liquidacion(client: TestClient):
    """Proceso 10: Desglose de cobro, mano de obra, horas del mecánico y cálculo de margen."""
    headers = get_auth_headers(client)

    payload = {
        "id_registro": 1,
        "descuento": 5.0,
        "tarifa_hora_mecanico": 10.0,  # 2 horas * $10 = $20 pago mecánico
        "observaciones": "Descuento de $5 autorizado por cortesía de taller",
    }
    res = client.post("/api/notas-venta/preparar", json=payload, headers=headers)
    assert res.status_code == 201
    data = res.json()

    assert data["id_nota_venta"] is not None
    assert "NV-" in data["numero_nota_venta"]
    assert data["estado_pago"] == "PENDIENTE_PAGO"
    assert data["subtotal_repuestos"] == 40.0
    assert data["subtotal_mano_obra"] == 30.0
    assert data["descuento"] == 5.0
    # Total = 40 + 30 - 5 = 65.0
    assert data["total"] == 65.0
    assert data["costo_repuestos_taller"] == 20.0
    assert data["horas_mecanico"] == 2.0
    assert data["pago_mecanico"] == 20.0
    # Ganancia = 65 - 20 - 20 = 25.0
    assert data["ganancia_neta_taller"] == 25.0
    assert len(data["items"]) == 2


def test_proceso_11_1_pago_incompleto_retiene_vehiculo(client: TestClient):
    """Proceso 11.1: Pago incompleto o fallido -> Se retiene la orden y el vehículo."""
    headers = get_auth_headers(client)

    # Intentar pagar solo $50 cuando el total es $65
    payload = {
        "metodo_pago": "EFECTIVO",
        "monto_recibido": 50.0,
    }
    res = client.post("/api/notas-venta/1/confirmar-pago", json=payload, headers=headers)
    assert res.status_code == 400
    res_json = res.json()
    error_msg = res_json.get("error") or res_json.get("detail", "")
    assert "Proceso 11.1" in error_msg

    # Verificar que la orden no cambió a pagada
    reg = client.get("/api/registros/1", headers=headers).json()
    assert reg["estado"] != 7


def test_procesos_11_12_13_14_confirmar_pago_y_emision_nota_venta(client: TestClient):
    """
    Procesos 11, 12, 13 y 14:
    - Pago confirmado de $65 por Transferencia.
    - Emisión de Nota de Venta (sin SRI ni factura electrónica).
    - Orden pasa al Estado 7: PAGADO.
    - Repuestos descontados de Kardex y stock (Proceso 13).
    - Alerta de stock mínimo generada (Proceso 13.1).
    - Ganancia neta consolidada (Proceso 14).
    """
    headers = get_auth_headers(client)

    payload = {
        "metodo_pago": "TRANSFERENCIA",
        "monto_recibido": 65.0,
        "numero_referencia": "TRANSF-BANCO-778899",
        "comprobante_url": "/images/pagos/comprobante_transf.jpg",
    }
    res = client.post("/api/notas-venta/1/confirmar-pago", json=payload, headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert data["exito"] is True
    assert data["estado_pago"] == "PAGADO"
    assert data["estado_orden"] == 7  # Estado 7: PAGADO
    assert data["resumen_financiero"]["total_ingreso"] == 65.0
    assert data["resumen_financiero"]["ganancia_neta"] == 25.0

    # Verificar Proceso 13.1: Alerta de stock mínimo
    assert len(data["alertas_stock_minimo"]) >= 1

    # Verificar inventario: stock físico bajó a 3 (4 - 1 = 3) y reservado a 0
    prod = client.get("/api/productos/1", headers=headers).json()
    assert prod["stock"] == 3
    assert prod["stock_reservado"] == 0

    # Verificar salida en Kardex
    kardex_res = client.get("/api/kardex/movimientos?id_registro=1", headers=headers)
    assert kardex_res.status_code == 200
    movs = kardex_res.json()
    assert any(m["origen"] == "COBRO_NOTA_VENTA" for m in movs)

    # Verificar reporte financiero global (Proceso 14 / Fin-8)
    rep_res = client.get("/api/notas-venta/reportes/financiero", headers=headers)
    assert rep_res.status_code == 200
    rep_data = rep_res.json()
    assert rep_data["total_notas_cobradas"] >= 1
    assert rep_data["ingresos_totales"] >= 65.0
    assert rep_data["ganancia_neta_taller"] >= 25.0
