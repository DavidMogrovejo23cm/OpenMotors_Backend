import os
import pytest
from fastapi.testclient import TestClient

# Configurar base de datos SQLite en archivo de prueba antes de importar la app
os.environ["DB_URL"] = "sqlite:///./test_gmotors.sqlite"

from app.main import app  # noqa: E402
from app.core.database import Base, engine  # noqa: E402
from app.core.seeder import init_db_and_seed  # noqa: E402


@pytest.fixture(scope="module")
def client():
    Base.metadata.drop_all(bind=engine)
    init_db_and_seed()
    with TestClient(app) as c:
        yield c
    engine.dispose()
    if os.path.exists("./test_gmotors.sqlite"):
        try:
            os.remove("./test_gmotors.sqlite")
        except OSError:
            pass


def test_health_and_seed(client: TestClient):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "UP"

    # Verificar que los roles iniciales fueron creados
    roles_res = client.get("/api/rol")
    assert roles_res.status_code == 200
    nombres_roles = [r["nombre"] for r in roles_res.json()]
    assert "ADMIN" in nombres_roles
    assert "CLIENTE" in nombres_roles
    assert "MECANICO" in nombres_roles


def test_auth_and_users(client: TestClient):
    # Login con usuario semilla admin
    login_res = client.post(
        "/api/usuarios/login",
        json={"nombre_usuario": "admin", "contrasena": "123456"},
    )
    assert login_res.status_code == 200
    admin_data = login_res.json()
    assert "token" in admin_data
    token = admin_data["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Registro de nuevo cliente (público) -> debe asignar automáticamente rol CLIENTE (id_rol=2)
    reg_res = client.post(
        "/api/usuarios",
        json={
            "nombre_completo": "Juan Pérez",
            "nombre_usuario": "juanperez",
            "correo": "juan@test.com",
            "contrasena": "Password123",
            "telefono": "0991234567",
            "cedula": "1712345678",
        },
    )
    assert reg_res.status_code == 201
    nuevo_user = reg_res.json()
    assert nuevo_user["nombre_usuario"] == "juanperez"
    assert len(nuevo_user["roles"]) >= 1
    assert any(r["idRol"] == 2 for r in nuevo_user["roles"])
    assert nuevo_user["codigoReferido"].startswith("GM-")

    # Probar sistema de código de referido entre admin y nuevo usuario
    ref_res = client.post(
        f"/api/usuarios/{nuevo_user['id_usuario']}/usar-referido",
        json={"codigo": admin_data["codigoReferido"]},
        headers=headers,
    )
    assert ref_res.status_code == 200
    assert ref_res.json()["nuevosPuntos"] == 50


def test_motos_and_maintenance_alerts(client: TestClient):
    login_res = client.post(
        "/api/usuarios/login",
        json={"nombre_usuario": "admin", "contrasena": "123456"},
    )
    headers = {"Authorization": f"Bearer {login_res.json()['token']}"}
    id_usuario = login_res.json()["id_usuario"]

    # Verificar los parámetros de mantenimiento semilla
    params_res = client.get("/api/mantenimiento-parametros", headers=headers)
    assert params_res.status_code == 200
    assert len(params_res.json()) in (21, 28, 35)

    # Crear una moto de 200cc con 1000 km
    moto_res = client.post(
        "/api/motos",
        json={
            "placa": "IAA-123A",
            "anio": 2024,
            "marca": "Yamaha",
            "modelo": "FZ 2.0",
            "kilometraje": 1000,
            "cilindraje": 200,
            "id_usuario": id_usuario,
        },
        headers=headers,
    )
    assert moto_res.status_code == 201
    moto = moto_res.json()
    id_moto = moto["id_moto"]

    # Verificar que se inicializaron los mantenimientos preventivos de la moto
    mant_res = client.get(f"/api/mantenimientos/moto/{id_moto}", headers=headers)
    assert mant_res.status_code == 200
    assert len(mant_res.json()) == 7

    # Consultar estado de alertas de mantenimiento
    alertas_res = client.get(f"/api/alertas/moto/{id_moto}", headers=headers)
    assert alertas_res.status_code == 200
    estados = alertas_res.json()
    assert len(estados) == 7
    assert all(e["estado"] == "OK" for e in estados)

    # Actualizar kilometraje a 3600 km para disparar alerta VENCIDO en CAMBIO_ACEITE (intervalo 2500km en 151-200cc)
    upd_res = client.put(
        f"/api/motos/{id_moto}",
        json={"kilometraje": 3600},
        headers=headers,
    )
    assert upd_res.status_code == 200

    alertas_res2 = client.get(f"/api/alertas/moto/{id_moto}", headers=headers)
    estados2 = alertas_res2.json()
    aceite_st = next(e for e in estados2 if e["tipo"] == "CAMBIO_ACEITE")
    assert aceite_st["estado"] == "VENCIDO"


def test_inventory_and_direct_sales(client: TestClient):
    login_res = client.post(
        "/api/usuarios/login",
        json={"nombre_usuario": "admin", "contrasena": "123456"},
    )
    headers = {"Authorization": f"Bearer {login_res.json()['token']}"}

    # Crear categoría
    cat_res = client.post(
        "/api/categorias",
        json={"nombre": "Lubricantes", "descripcion": "Aceites sintéticos y minerales"},
        headers=headers,
    )
    assert cat_res.status_code == 201
    id_cat = cat_res.json()["id_categoria"]

    # Crear producto con stock 10
    prod_res = client.post(
        "/api/productos",
        json={
            "codigo_proveedor": "MOT-01",
            "codigo_distribuidor": "DIST-EC",
            "codigo_personal": "ACE-7100",
            "nombre": "Motul 7100 10W40",
            "descripcion": "Aceite 100% sintético 1L",
            "costo": 11.50,
            "pvp": 16.00,
            "stock": 10,
            "id_categoria": id_cat,
        },
        headers=headers,
    )
    assert prod_res.status_code == 201
    id_prod = prod_res.json()["id_producto"]

    # Venta directa de 2 unidades -> stock debe bajar a 8 y crear factura
    venta_res = client.post(
        "/api/productos/venta-directa",
        json={
            "id_producto": id_prod,
            "cantidad": 2,
            "cliente_nombre": "Carlos Cliente",
            "cliente_cedula": "1799999999",
        },
        headers=headers,
    )
    assert venta_res.status_code == 200
    venta_data = venta_res.json()
    assert venta_data["producto"]["stock"] == 8
    assert venta_data["total"] == 32.0
    assert venta_data["id_factura"] is not None


def test_workshop_records_and_invoicing(client: TestClient):
    login_res = client.post(
        "/api/usuarios/login",
        json={"nombre_usuario": "admin", "contrasena": "123456"},
    )
    headers = {"Authorization": f"Bearer {login_res.json()['token']}"}

    motos = client.get("/api/motos", headers=headers).json()
    id_moto = motos[0]["id_moto"]
    tipos = client.get("/api/tipos", headers=headers).json()
    id_tipo = tipos[0]["id_tipo"]

    # Crear registro de taller
    reg_res = client.post(
        "/api/registros",
        json={
            "id_moto": id_moto,
            "id_tipo": id_tipo,
            "descripcion": "Mantenimiento general de 4000 km",
            "observaciones": "Revisar tensión de cadena",
            "costo_total": 25.0,
            "kilometraje": 4000,
            "estado": 1,
        },
        headers=headers,
    )
    assert reg_res.status_code == 201
    id_reg = reg_res.json()["id_registro"]

    # Crear factura para el registro y agregar detalle
    fac_res = client.post(
        "/api/facturas",
        json={"costo_total": 0.0, "cliente_nombre": "Admin Test", "origen_venta": "TALLER"},
        headers=headers,
    )
    assert fac_res.status_code == 201
    id_fac = fac_res.json()["id_factura"]

    det_res = client.post(
        "/api/detalles-factura",
        json={
            "id_factura": id_fac,
            "descripcion": "Mano de obra afinación",
            "cantidad": 1,
            "precio_unitario": 25.0,
            "subtotal": 25.0,
        },
        headers=headers,
    )
    assert det_res.status_code == 201

    # Asociar factura al registro
    asoc_res = client.put(
        f"/api/registros/{id_reg}/factura",
        json={"idFactura": id_fac},
        headers=headers,
    )
    assert asoc_res.status_code == 200
    assert asoc_res.json()["id_factura"] == id_fac
    assert asoc_res.json()["costo_total"] == 25.0

    # Cambiar estado del registro a 4 (Facturado)
    est_res = client.patch(
        f"/api/registros/{id_reg}/estado?estado=4",
        headers=headers,
    )
    assert est_res.status_code == 200
    assert est_res.json()["estado"] == 4
    assert est_res.json()["fecha_facturado"] is not None


def test_combustible_finanzas_rutas_and_metrics(client: TestClient):
    login_res = client.post(
        "/api/usuarios/login",
        json={"nombre_usuario": "admin", "contrasena": "123456"},
    )
    headers = {"Authorization": f"Bearer {login_res.json()['token']}"}
    id_usuario = login_res.json()["id_usuario"]
    motos = client.get("/api/motos", headers=headers).json()
    id_moto = motos[0]["id_moto"]

    # Combustible
    precios_res = client.get("/api/combustible/precios", headers=headers)
    assert precios_res.status_code == 200
    assert "extra" in precios_res.json()

    carga_res = client.post(
        "/api/combustible",
        json={
            "id_moto": id_moto,
            "litros": 8.5,
            "costo_total": 5.50,
            "km_actual": 4150,
            "km_anterior": 4000,
            "notas": "Tanque lleno Extra",
        },
        headers=headers,
    )
    assert carga_res.status_code == 201

    # Pagos a empleados
    pago_res = client.post(
        "/api/pagos-empleado",
        json={
            "id_empleado": id_usuario,
            "concepto": "Comisión semanal taller",
            "monto": 120.0,
            "notas": "Pagado por transferencia",
        },
        headers=headers,
    )
    assert pago_res.status_code == 201

    # Rutas GPS
    ruta_res = client.post(
        "/api/rutas",
        json={
            "id_usuario": id_usuario,
            "nombre_ruta": "Quito - Papallacta",
            "descripcion": "Ruta de fin de semana",
            "origen_lat": -0.1807,
            "origen_lng": -78.4678,
            "destino_lat": -0.3772,
            "destino_lng": -78.1419,
            "distancia_km": 65.4,
            "duracion_minutos": 75,
        },
        headers=headers,
    )
    assert ruta_res.status_code == 201
    assert len(client.get("/api/rutas", headers=headers).json()) >= 1

    # Métricas
    preview_res = client.get("/api/metrics/reports/preview")
    assert preview_res.status_code == 200
    assert preview_res.json()["httpMetrics"]["totalRequests"] > 0


def test_quick_accounts_diagnosticos_proveedores_and_stock_restore(client: TestClient):
    login_res = client.post(
        "/api/usuarios/login",
        json={"nombre_usuario": "admin", "contrasena": "123456"},
    )
    headers = {"Authorization": f"Bearer {login_res.json()['token']}"}
    id_admin = login_res.json()["id_usuario"]

    # 1. Quick account creation (/api/quick-accounts/create)
    qa_res = client.post(
        "/api/quick-accounts/create",
        json={
            "nombreCompleto": "María Rápida",
            "correo": "maria.rapida@test.com",
            "telefono": "0987654321",
            "cedula": "0102030405",
            "placa": "IBC-999Z",
            "marca": "Honda",
            "modelo": "CB 190R",
            "anio": 2025,
            "kilometraje": 500,
            "cilindraje": 190,
        },
        headers=headers,
    )
    assert qa_res.status_code == 201
    qa_data = qa_res.json()
    assert qa_data["usuario"]["correo"] == "maria.rapida@test.com"
    assert qa_data["moto"]["placa"] == "IBC-999Z"
    id_moto_qa = qa_data["moto"]["id_moto"]

    # 2. Diagnóstico mecánico (/api/diagnosticos)
    diag_res = client.post(
        "/api/diagnosticos",
        json={
            "id_moto": id_moto_qa,
            "id_mecanico": id_admin,
            "kilometraje_ingreso": 650,
            "observaciones_generales": "Frenos delanteros requieren ajuste pronto",
            "detalles": [
                {"parte": "Freno delantero", "estado": "2", "observacion": "Desgaste medio"},
                {"parte": "Luces", "estado": "1", "observacion": "Todo operativo"},
            ],
        },
        headers=headers,
    )
    assert diag_res.status_code == 201
    assert len(diag_res.json()["detalles"]) == 2

    diags_moto = client.get(f"/api/diagnosticos/moto/{id_moto_qa}", headers=headers)
    assert diags_moto.status_code == 200
    assert len(diags_moto.json()) == 1

    # 3. Contactos de proveedores (/api/proveedores-contactos)
    prov_put = client.put(
        "/api/proveedores-contactos/MOT-01",
        json={
            "nombre": "Importadora Motul Ecuador",
            "telefono": "0990001122",
            "email": "ventas@motul.ec",
            "producto": "Aceites y Lubricantes",
        },
        headers=headers,
    )
    assert prov_put.status_code == 200
    provs = client.get("/api/proveedores-contactos", headers=headers).json()
    assert any(p["codigo"] == "MOT-01" for p in provs)

    # 4. Restauración de stock al eliminar detalle de factura
    prods = client.get("/api/productos", headers=headers).json()
    prod = prods[0]
    stock_inicial = prod["stock"]

    fac = client.post(
        "/api/facturas",
        json={"costo_total": 0.0, "cliente_nombre": "Prueba Stock"},
        headers=headers,
    ).json()

    det = client.post(
        "/api/detalles-factura",
        json={
            "id_factura": fac["id_factura"],
            "id_producto": prod["id_producto"],
            "cantidad": 3,
        },
        headers=headers,
    ).json()

    prod_despues = client.get(f"/api/productos/{prod['id_producto']}", headers=headers).json()
    assert prod_despues["stock"] == stock_inicial - 3

    # Eliminar el detalle de factura -> debe restaurar las 3 unidades al stock
    del_det = client.delete(f"/api/detalles-factura/{det['id_detalle']}", headers=headers)
    assert del_det.status_code == 204

    prod_restaurado = client.get(f"/api/productos/{prod['id_producto']}", headers=headers).json()
    assert prod_restaurado["stock"] == stock_inicial

    # 5. Recuperación de contraseña (/api/usuarios/recuperacion/solicitar)
    rec_sol = client.post(
        "/api/usuarios/recuperacion/solicitar",
        json={"correo": "maria.rapida@test.com"},
    )
    assert rec_sol.status_code == 200
    assert rec_sol.json()["exito"] is True

