"""Pruebas del Bloque 1: Sesión/logout real, suspensión/restablecimiento de cuentas, auditoría y edición de clientes."""
from sqlalchemy.orm import Session

from tests.test_permisos import api
from app.core.security import hash_password
from app.modules.usuarios.models import Usuario, TokenRevocado
from app.modules.sistema.auditoria import AuditoriaOperacion


def test_rf02_logout_real_invalida_jwt_en_servidor(api):
    client, _, engine = api
    with Session(engine) as db:
        u = db.get(Usuario, 2)
        u.contrasena = hash_password("ClaveMecanico123")
        db.commit()

    login_res = client.post("/api/usuarios/login", json={"nombre_usuario": "u2", "contrasena": "ClaveMecanico123"})
    assert login_res.status_code == 200
    token = login_res.json()["token"]
    h_mech = {"Authorization": f"Bearer {token}"}

    assert client.get("/api/registros", headers=h_mech).status_code == 200

    logout_res = client.post("/api/usuarios/logout", headers=h_mech)
    assert logout_res.status_code == 200

    with Session(engine) as db:
        assert db.query(TokenRevocado).filter(TokenRevocado.id_usuario == 2).count() == 1

    # El token ya revocado debe ser rechazado por el servidor inmediatamente
    after_res = client.get("/api/registros", headers=h_mech)
    assert after_res.status_code == 401


def test_rf04_suspender_reactivar_y_proteger_admin(api):
    client, headers, engine = api
    with Session(engine) as db:
        for uid in (1, 2):
            u = db.get(Usuario, uid)
            u.contrasena = hash_password("ClaveSegura123")
        db.commit()

    # No admin no puede suspender
    assert client.patch("/api/usuarios/2/estado", json={"activo": False}, headers=headers[4]).status_code == 403
    assert client.patch("/api/usuarios/4/estado", json={"activo": False}, headers=headers[2]).status_code == 403

    # Admin no puede auto-suspenderse ni dejar el sistema sin admin activo
    self_suspend = client.patch("/api/usuarios/1/estado", json={"activo": False}, headers=headers[1])
    assert self_suspend.status_code == 400

    # Login previo del mecánico funciona
    login_mech = client.post("/api/usuarios/login", json={"nombre_usuario": "u2", "contrasena": "ClaveSegura123"})
    assert login_mech.status_code == 200
    mech_token = {"Authorization": f"Bearer {login_mech.json()['token']}"}
    assert client.get("/api/registros", headers=mech_token).status_code == 200

    # Admin suspende al mecánico
    susp_res = client.patch("/api/usuarios/2/estado", json={"activo": False}, headers=headers[1])
    assert susp_res.status_code == 200
    assert susp_res.json()["activo"] is False

    # Sesión activa del mecánico queda invalidada y login devuelve 403 claro
    assert client.get("/api/registros", headers=mech_token).status_code == 401
    blocked_login = client.post("/api/usuarios/login", json={"nombre_usuario": "u2", "contrasena": "ClaveSegura123"})
    assert blocked_login.status_code == 403
    assert "desactivada" in blocked_login.json()["error"].lower()

    # Reactivación devuelve acceso
    react_res = client.patch("/api/usuarios/2/estado", json={"activo": True}, headers=headers[1])
    assert react_res.status_code == 200
    assert react_res.json()["activo"] is True
    assert client.post("/api/usuarios/login", json={"nombre_usuario": "u2", "contrasena": "ClaveSegura123"}).status_code == 200

    # Auditoría registrada
    aud_res = client.get("/api/sistema/auditoria?entidad=Usuario", headers=headers[1])
    assert aud_res.status_code == 200
    acciones = [a["accion"] for a in aud_res.json()]
    assert "USUARIO_SUSPENDIDO" in acciones
    assert "USUARIO_REACTIVADO" in acciones


def test_rf04_admin_restablece_clave_e_invalida_sesiones_previas(api):
    client, headers, engine = api
    with Session(engine) as db:
        u = db.get(Usuario, 4)
        u.contrasena = hash_password("ClaveVieja123")
        db.commit()

    old_login = client.post("/api/usuarios/login", json={"nombre_usuario": "u4", "contrasena": "ClaveVieja123"})
    assert old_login.status_code == 200
    old_headers = {"Authorization": f"Bearer {old_login.json()['token']}"}

    # Mecánico no puede restablecer clave de otro usuario
    assert client.post("/api/usuarios/4/restablecer-clave", json={"nueva_contrasena": "NuevaClave123"}, headers=headers[2]).status_code == 403

    # Admin restablece clave de u4
    reset_res = client.post("/api/usuarios/4/restablecer-clave", json={"nueva_contrasena": "NuevaClave123"}, headers=headers[1])
    assert reset_res.status_code == 200
    assert reset_res.json()["contrasenaTemporal"] == "NuevaClave123"

    # Token viejo inválido
    assert client.get("/api/registros", headers=old_headers).status_code == 401
    # Clave vieja rechazada y nueva aceptada
    assert client.post("/api/usuarios/login", json={"nombre_usuario": "u4", "contrasena": "ClaveVieja123"}).status_code == 401
    assert client.post("/api/usuarios/login", json={"nombre_usuario": "u4", "contrasena": "NuevaClave123"}).status_code == 200


def test_rf06_edicion_cliente_por_recepcion_y_auditoria(api):
    client, headers, _ = api
    # Conceder permiso de recepción a u2
    assert client.put("/api/usuarios/2/permisos", json={"permisos": ["recepcion"]}, headers=headers[1]).status_code == 200

    # Recepcionista edita datos de contacto del cliente u4
    upd = client.put(
        "/api/usuarios/4",
        json={"nombre_completo": "Cliente Editado", "telefono": "0998887777", "cedula": "0102030405", "direccion": "Av. Loja 123"},
        headers=headers[2],
    )
    assert upd.status_code == 200, upd.text
    assert upd.json()["nombre_completo"] == "Cliente Editado"
    assert upd.json()["telefono"] == "0998887777"

    # Admin intenta asignar la misma cédula a otro cliente u5 -> 409 Conflict
    dup = client.put("/api/usuarios/5", json={"cedula": "0102030405"}, headers=headers[1])
    assert dup.status_code == 409

    # Auditoría solo accesible por ADMIN
    assert client.get("/api/sistema/auditoria", headers=headers[2]).status_code == 403
    aud = client.get("/api/sistema/auditoria?accion=USUARIO_ACTUALIZADO", headers=headers[1])
    assert aud.status_code == 200
    assert len(aud.json()) >= 1
