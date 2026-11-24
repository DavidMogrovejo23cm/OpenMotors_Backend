import os
import pytest
from fastapi.testclient import TestClient

# Configurar base de datos SQLite en archivo de prueba antes de importar la app
os.environ["DB_URL"] = "sqlite:///./test_openmotors.sqlite"

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
    if os.path.exists("./test_openmotors.sqlite"):
        try:
            os.remove("./test_openmotors.sqlite")
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
        headers=headers,
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


def test_carros_and_maintenance_alerts(client: TestClient):
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

    # Crear un carro de 200cc con 1000 km
    carro_res = client.post(
        "/api/carros",
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
    assert carro_res.status_code == 201
    carro = carro_res.json()
    id_carro = carro["id_carro"]

    # Verificar que se inicializaron los mantenimientos preventivos de el carro
    mant_res = client.get(f"/api/mantenimientos/carro/{id_carro}", headers=headers)
    assert mant_res.status_code == 200
    assert len(mant_res.json()) == 7

    # Consultar estado de alertas de mantenimiento
    alertas_res = client.get(f"/api/alertas/carro/{id_carro}", headers=headers)
    assert alertas_res.status_code == 200
    estados = alertas_res.json()
    assert len(estados) == 7
    assert all(e["estado"] == "OK" for e in estados)

    # Actualizar kilometraje a 3600 km para disparar alerta VENCIDO en CAMBIO_ACEITE (intervalo 2500km en 151-200cc)
    upd_res = client.put(
        f"/api/carros/{id_carro}",
        json={"kilometraje": 3600},
        headers=headers,
    )
    assert upd_res.status_code == 200

    alertas_res2 = client.get(f"/api/alertas/carro/{id_carro}", headers=headers)
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

    carros = client.get("/api/carros", headers=headers).json()
    id_carro = carros[0]["id_carro"]
    tipos = client.get("/api/tipos", headers=headers).json()
    id_tipo = tipos[0]["id_tipo"]

    # Crear registro de taller
    reg_res = client.post(
        "/api/registros",
        json={
            "id_carro": id_carro,
            "id_tipo": id_tipo,
            "descripcion": "Mantenimiento general de 4000 km",
            "observaciones": "Revisar tensión de cadena",
            "costo_total": 25.0,
            "kilometraje": 4000,
            "estado": 0,
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

    # Los estados financieros ya no son estados del trabajo.
    invalid = client.patch(f"/api/registros/{id_reg}/estado?estado=4", headers=headers)
    assert invalid.status_code == 400
    for estado in (1, 2):
        est_res = client.patch(f"/api/registros/{id_reg}/estado?estado={estado}", headers=headers)
        assert est_res.status_code == 200
    assert est_res.json()["estado"] == 2
    assert est_res.json()["estado_pago"] == "PENDIENTE"
    assert est_res.json()["fecha_facturado"] is None


def test_combustible_finanzas_rutas_and_metrics(client: TestClient):
    login_res = client.post(
        "/api/usuarios/login",
        json={"nombre_usuario": "admin", "contrasena": "123456"},
    )
    headers = {"Authorization": f"Bearer {login_res.json()['token']}"}
    id_usuario = login_res.json()["id_usuario"]
    carros = client.get("/api/carros", headers=headers).json()
    id_carro = carros[0]["id_carro"]

    # Combustible
    precios_res = client.get("/api/combustible/precios", headers=headers)
    assert precios_res.status_code == 200
    assert "extra" in precios_res.json()

    carga_res = client.post(
        "/api/combustible",
        json={
            "id_carro": id_carro,
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
    preview_res = client.get("/api/metrics/reports/preview", headers=headers)
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
    assert qa_data["carro"]["placa"] == "IBC-999Z"
    id_carro_qa = qa_data["carro"]["id_carro"]

    rec = client.post('/api/recepciones', headers=headers, json={
        "id_vehiculo": id_carro_qa, "kilometraje": 650,
        "foto_frente": "/static/frente.jpg", "foto_posterior": "/static/posterior.jpg",
        "foto_lateral_izq": "/static/izq.jpg", "foto_lateral_der": "/static/der.jpg", "firma_cliente": "/static/firma.png",
    })
    assert rec.status_code == 201, rec.text
    # 2. Diagnóstico mecánico (/api/diagnosticos)
    diag_res = client.post(
        "/api/diagnosticos",
        json={
            "id_carro": id_carro_qa,
            "id_registro": rec.json()["id_registro"],
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

    diags_carro = client.get(f"/api/diagnosticos/carro/{id_carro_qa}", headers=headers)
    assert diags_carro.status_code == 200
    assert len(diags_carro.json()) == 1

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


def test_rf01_registro_publico_usuario(client: TestClient):
    """Verificación de RF-01: Registro público de usuarios con datos de identificación y acceso."""
    # 1. Validación de campos obligatorios faltantes (rechazo por Pydantic / validación)
    incompleto = client.post(
        "/api/usuarios/registro",
        json={"nombre_completo": "Carlos Test"},
    )
    assert incompleto.status_code in (400, 422)

    # 2. Registro exitoso con todos los campos obligatorios
    valido = {
        "nombre_completo": "Carlos Mendoza",
        "nombre_usuario": "cmendoza",
        "correo": "cmendoza@correo.com",
        "contrasena": "Password123*",
        "cedula": "1720304050",
        "telefono": "0987654321",
        "direccion": "Av. Amazonas y Colón",
        "ciudad": "Quito",
    }
    res = client.post("/api/usuarios/registro", json=valido)
    assert res.status_code == 201
    data = res.json()
    assert data["mensaje"] == "Usuario registrado exitosamente"
    usuario = data["usuario"]
    assert usuario["nombre_usuario"] == "cmendoza"
    assert usuario["correo"] == "cmendoza@correo.com"
    assert usuario["cedula"] == "1720304050"
    # Rol CLIENTE asignado automáticamente
    nombres_roles = [r["rol"]["nombre"] for r in usuario.get("roles", []) if "rol" in r]
    assert "CLIENTE" in nombres_roles

    # 3. Iniciar sesión con el usuario recién registrado
    login_res = client.post(
        "/api/usuarios/login",
        json={"nombre_usuario": "cmendoza", "contrasena": "Password123*"},
    )
    assert login_res.status_code == 200
    assert "token" in login_res.json()

    # 4. Rechazo por duplicidad de nombre de usuario
    dup_user = {**valido, "correo": "otro@correo.com", "cedula": "1720304051"}
    res_dup_u = client.post("/api/usuarios/registro", json=dup_user)
    assert res_dup_u.status_code == 409
    assert "nombre de usuario ya está en uso" in (res_dup_u.json().get("mensaje") or res_dup_u.json().get("error"))

    # 5. Rechazo por duplicidad de correo electrónico
    dup_mail = {**valido, "nombre_usuario": "cmendoza2", "cedula": "1720304052"}
    res_dup_m = client.post("/api/usuarios/registro", json=dup_mail)
    assert res_dup_m.status_code == 409
    assert "correo electrónico ya está registrado" in (res_dup_m.json().get("mensaje") or res_dup_m.json().get("error"))

    # 6. Rechazo por duplicidad de cédula
    dup_ced = {**valido, "nombre_usuario": "cmendoza3", "correo": "otro3@correo.com"}
    res_dup_c = client.post("/api/usuarios/registro", json=dup_ced)
    assert res_dup_c.status_code == 409
    assert "cédula ya está registrado" in (res_dup_c.json().get("mensaje") or res_dup_c.json().get("error"))


def test_rf02_inicio_y_cierre_de_sesion(client: TestClient):
    """Verificación de RF-02: Inicio y cierre de sesión, credenciales incorrectas y control de acceso."""
    # 1. Login exitoso usando nombre de usuario
    login_user = client.post(
        "/api/usuarios/login",
        json={"nombre_usuario": "admin", "contrasena": "123456"},
    )
    assert login_user.status_code == 200
    data_user = login_user.json()
    assert "token" in data_user
    assert data_user["nombre_usuario"] == "admin"
    token = data_user["token"]

    # 2. Login exitoso usando correo electrónico
    login_email = client.post(
        "/api/usuarios/login",
        json={"correo": "admin@openauto.com", "contrasena": "123456"},
    )
    assert login_email.status_code == 200
    assert "token" in login_email.json()

    # 3. Rechazo cuando la contraseña es incorrecta (HTTP 401)
    bad_pass = client.post(
        "/api/usuarios/login",
        json={"nombre_usuario": "admin", "contrasena": "clave_erronea_xyz"},
    )
    assert bad_pass.status_code == 401

    # 4. Rechazo cuando el usuario/correo no existe (HTTP 401)
    bad_user = client.post(
        "/api/usuarios/login",
        json={"nombre_usuario": "usuario_inexistente_999", "contrasena": "123456"},
    )
    assert bad_user.status_code == 401

    # 5. Acceso al sistema después de iniciar sesión: el token permite consumir rutas protegidas
    headers = {"Authorization": f"Bearer {token}"}
    protected_res = client.get("/api/usuarios", headers=headers)
    assert protected_res.status_code == 200

    # 6. Cierre de sesión y protección de rutas: sin token o con token alterado se deniega el acceso
    no_auth_res = client.get("/api/usuarios")
    assert no_auth_res.status_code == 401

    bad_token_res = client.get("/api/usuarios", headers={"Authorization": "Bearer token_falso_o_expirado"})
    assert bad_token_res.status_code == 401


def test_rf03_asignacion_de_roles_y_permisos(client: TestClient):
    """Verificación de RF-03: Asignación de roles y permisos, control de acceso y restricción a funciones no autorizadas."""
    # 1. Definir los roles de usuario del sistema (/api/rol)
    roles_res = client.get("/api/rol")
    assert roles_res.status_code == 200
    roles_dict = {r["nombre"]: r["id_rol"] for r in roles_res.json()}
    assert "ADMIN" in roles_dict
    assert "MECANICO" in roles_dict
    assert "CLIENTE" in roles_dict

    # 2. Login de administrador para gestionar roles y permisos
    admin_login = client.post("/api/usuarios/login", json={"nombre_usuario": "admin", "contrasena": "123456"})
    admin_token = admin_login.json()["token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 3. Crear usuario de prueba (se crea con rol CLIENTE)
    usr_data = {
        "nombre_completo": "Pedro Mecanico",
        "nombre_usuario": "pmecanico",
        "correo": "pmecanico@taller.local",
        "contrasena": "Password123*",
    }
    nuevo_usr = client.post("/api/usuarios/registro", json=usr_data).json()["usuario"]
    id_usr = nuevo_usr["id_usuario"]

    # 4. Asignar rol MECANICO al usuario usando cambiar-categoria
    cambio_res = client.put(
        "/api/usuario_rol/cambiar-categoria",
        json={
            "id_usuario": id_usr,
            "id_rol_actual": roles_dict["CLIENTE"],
            "id_rol_nuevo": roles_dict["MECANICO"],
        },
        headers=admin_headers,
    )
    assert cambio_res.status_code == 200
    assert cambio_res.json()["rol"]["nombre"] == "MECANICO"

    # Login como el nuevo mecánico
    mec_login = client.post("/api/usuarios/login", json={"nombre_usuario": "pmecanico", "contrasena": "Password123*"})
    mec_token = mec_login.json()["token"]
    mec_headers = {"Authorization": f"Bearer {mec_token}"}

    # 5. Restringir acceso: el mecánico sin permiso 'recepcion' intenta registrar un cliente
    cli_payload = {
        "nombre_completo": "Cliente Taller",
        "nombre_usuario": "clitaller",
        "correo": "clitaller@correo.com",
    }
    denegado_res = client.post("/api/usuarios/clientes", json=cli_payload, headers=mec_headers)
    assert denegado_res.status_code == 403

    # 6. Administrador asigna permiso específico 'recepcion' al mecánico
    grant_res = client.put(
        f"/api/usuarios/{id_usr}/permisos",
        json={"permisos": ["recepcion"]},
        headers=admin_headers,
    )
    assert grant_res.status_code == 200
    assert grant_res.json()["permisos"] == ["recepcion"]

    # Con el permiso concedido, el mecánico ahora sí puede registrar clientes
    permitido_res = client.post("/api/usuarios/clientes", json=cli_payload, headers=mec_headers)
    assert permitido_res.status_code == 201

    # 7. Restringir acceso nuevamente: administrador revoca los permisos
    revoke_res = client.put(
        f"/api/usuarios/{id_usr}/permisos",
        json={"permisos": []},
        headers=admin_headers,
    )
    assert revoke_res.status_code == 200
    assert revoke_res.json()["permisos"] == []

    # Tras revocar, la acción vuelve a ser rechazada con 403 Forbidden
    rechazado_res = client.post(
        "/api/usuarios/clientes",
        json={"nombre_completo": "Otro", "nombre_usuario": "otrocli", "correo": "otro@correo.com"},
        headers=mec_headers,
    )
    assert rechazado_res.status_code == 403

    # 8. Un mecánico no puede auto-asignarse permisos (solo ADMIN puede modificar permisos)
    auto_grant = client.put(
        f"/api/usuarios/{id_usr}/permisos",
        json={"permisos": ["recepcion"]},
        headers=mec_headers,
    )
    assert auto_grant.status_code == 403




