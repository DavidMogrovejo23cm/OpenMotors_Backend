"""Pruebas del Bloque 5: Respaldos/recuperación (RNF-16, RNF-17) y validación de imágenes (RNF-08)."""
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base
from app.core.exceptions import BusinessValidationError
from app.modules.inventario.models import Categoria, Producto
from app.modules.roles.models import Rol, UsuarioRol
from app.modules.sistema.backup import BackupService
from app.modules.usuarios.models import Usuario
from app.modules.vehiculos.models import Vehiculo
from tests.test_permisos import api


def test_rnf16_rnf17_respaldo_y_restauracion_api(api, tmp_path, monkeypatch):
    client, headers, engine = api
    backup_dir = tmp_path / "backups_api"
    monkeypatch.setenv("OPENMOTORS_BACKUP_DIR", str(backup_dir))

    # Seguridad de acceso: solo ADMIN
    assert client.get("/api/sistema/respaldos").status_code == 401
    assert client.post("/api/sistema/respaldos", json={}).status_code == 401
    assert client.get("/api/sistema/respaldos", headers=headers[2]).status_code == 403
    assert client.get("/api/sistema/respaldos", headers=headers[4]).status_code == 403
    assert client.post("/api/sistema/respaldos", json={}, headers=headers[2]).status_code == 403

    # Crear datos reales antes del respaldo
    with Session(engine) as db:
        cat = Categoria(nombre="Motor")
        db.add(cat)
        db.flush()
        db.add(Vehiculo(placa="PQR-987", marca="Toyota", modelo="Hilux", anio=2022, kilometraje=35000, id_usuario=4))
        db.add(
            Producto(
                codigo_personal="FILT-001",
                nombre="Filtro de aceite",
                id_categoria=cat.id_categoria,
                stock=15,
                costo=10.0,
                pvp=18.5,
            )
        )
        db.commit()

    resp = client.post(
        "/api/sistema/respaldos",
        json={"nota": "Respaldo previo a mantenimiento"},
        headers=headers[1],
    )
    assert resp.status_code == 201, resp.text
    manifiesto = resp.json()
    backup_id = manifiesto["backupId"]
    assert manifiesto["totalRegistros"] >= 6
    assert len(manifiesto["sha256Json"]) == 64

    listado = client.get("/api/sistema/respaldos", headers=headers[1])
    assert listado.status_code == 200
    assert any(item["backupId"] == backup_id and item["disponible"] is True for item in listado.json())

    verif = client.get(f"/api/sistema/respaldos/{backup_id}/verificar", headers=headers[1])
    assert verif.status_code == 200
    assert verif.json()["valido"] is True

    # Auditoría registra CREATE inmediatamente al generar respaldo
    aud_create = client.get("/api/sistema/auditoria?entidad=SistemaRespaldo", headers=headers[1])
    assert aud_create.status_code == 200
    assert "CREATE" in {item["accion"] for item in aud_create.json()}

    # Simular pérdida accidental de datos críticos
    with Session(engine) as db:
        db.execute(delete(Vehiculo).where(Vehiculo.placa == "PQR-987"))
        db.execute(delete(Producto).where(Producto.codigo_personal == "FILT-001"))
        db.commit()
        assert db.query(Vehiculo).filter(Vehiculo.placa == "PQR-987").first() is None
        assert db.query(Producto).filter(Producto.codigo_personal == "FILT-001").first() is None

    # Restaurar desde el respaldo
    rest = client.post(f"/api/sistema/respaldos/{backup_id}/restaurar", headers=headers[1])
    assert rest.status_code == 200, rest.text
    assert rest.json()["restaurado"] is True
    assert rest.json()["registrosRestaurados"] >= 6

    with Session(engine) as db:
        v = db.query(Vehiculo).filter(Vehiculo.placa == "PQR-987").first()
        p = db.query(Producto).filter(Producto.codigo_personal == "FILT-001").first()
        assert v is not None and v.marca == "Toyota" and v.modelo == "Hilux"
        assert p is not None and p.stock == 15 and p.pvp == 18.5

    # Auditoría registra RESTORE después de restaurar la BD
    aud = client.get("/api/sistema/auditoria?entidad=SistemaRespaldo", headers=headers[1])
    assert aud.status_code == 200
    acciones = {item["accion"] for item in aud.json()}
    assert "RESTORE" in acciones

    # Path traversal rechazado
    bad = client.get("/api/sistema/respaldos/..%2Fetc/verificar", headers=headers[1])
    assert bad.status_code in (400, 404)


def test_rnf16_rnf17_respaldo_fisico_sqlite_y_deteccion_corrupcion(tmp_path):
    db_file = tmp_path / "openmotors_prod.sqlite"
    backup_dir = tmp_path / "backups_sqlite"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    with SessionLocal() as db:
        rol = Rol(nombre="ADMIN")
        db.add(rol)
        db.flush()
        u = Usuario(
            nombre_usuario="admin_prod",
            contrasena="hash_seguro",
            nombre_completo="Admin Taller",
            correo="admin@taller.test",
        )
        db.add(u)
        db.flush()
        db.add(UsuarioRol(id_usuario=u.id_usuario, id_rol=rol.id_rol, estado=1))
        db.add(Vehiculo(placa="XYZ-321", marca="Chevrolet", modelo="D-Max", anio=2021, id_usuario=u.id_usuario))
        db.commit()

        manifiesto = BackupService.crear_respaldo(
            db,
            backup_dir=backup_dir,
            responsable="ADMIN_TEST",
            nota="Cierre físico diario",
        )
        assert manifiesto["tipo"] == "SQLITE+JSON"
        assert manifiesto["archivoSqlite"] is not None

        verif = BackupService.verificar_integridad(manifiesto["backupId"], backup_dir=backup_dir)
        assert verif["valido"] is True
        assert verif["sqliteIntegrity"] == "ok"

        # Verificar restauración física de archivo .sqlite a nueva ruta
        destino_sqlite = tmp_path / "restaurada.sqlite"
        res_fisico = BackupService.restaurar_archivo_sqlite(
            backup_dir / manifiesto["archivoSqlite"],
            destino_sqlite,
        )
        assert res_fisico["restaurado"] is True
        conn = sqlite3.connect(str(destino_sqlite))
        try:
            placas = [r[0] for r in conn.execute("SELECT placa FROM vehiculos").fetchall()]
            assert "XYZ-321" in placas
        finally:
            conn.close()

        # Simular corrupción del respaldo JSON -> verificación falla y restauración se bloquea
        ruta_json = backup_dir / manifiesto["archivoJson"]
        ruta_json.write_text(ruta_json.read_text(encoding="utf-8") + "\n ", encoding="utf-8")
        verif_corrupta = BackupService.verificar_integridad(manifiesto["backupId"], backup_dir=backup_dir)
        assert verif_corrupta["valido"] is False
        assert verif_corrupta["jsonValido"] is False

        with pytest.raises(BusinessValidationError):
            BackupService.restaurar_respaldo(db, manifiesto["backupId"], backup_dir=backup_dir)


def test_cli_backup_restore_end_to_end(tmp_path):
    backend_root = Path(__file__).resolve().parent.parent
    db_file = tmp_path / "cli_taller.sqlite"
    backup_dir = tmp_path / "cli_backups"
    env = dict(os.environ)
    env["DB_URL"] = f"sqlite:///{db_file}"
    env["OPENMOTORS_BACKUP_DIR"] = str(backup_dir)

    p_backup = subprocess.run(
        [sys.executable, "scripts/backup_restore.py", "backup", "--nota", "Respaldo CLI"],
        cwd=str(backend_root),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert p_backup.returncode == 0, p_backup.stderr

    manifiestos = list(backup_dir.glob("*.manifest.json"))
    assert len(manifiestos) == 1
    backup_id = manifiestos[0].name.removesuffix(".manifest.json")

    p_verify = subprocess.run(
        [sys.executable, "scripts/backup_restore.py", "verify", "--id", backup_id],
        cwd=str(backend_root),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert p_verify.returncode == 0, p_verify.stderr


def test_rnf08_validacion_imagenes_tamano_y_formato(api, tmp_path, monkeypatch):
    client, headers, _ = api
    monkeypatch.setattr("app.shared.storage_service.LOCAL_UPLOAD_ROOT", tmp_path / "uploads")
    monkeypatch.setattr("app.shared.storage_service.storage_service._supabase_configured", lambda: False)
    auth_only = {"Authorization": headers[1]["Authorization"]}

    # Formato no permitido
    r_ext = client.post(
        "/api/vehiculos/upload",
        data={"placa": "AAA-111"},
        files={"archivo": ("virus.exe", b"MZ-not-an-image", "application/octet-stream")},
        headers=auth_only,
    )
    assert r_ext.status_code == 400

    # Archivo vacío
    r_empty = client.post(
        "/api/vehiculos/upload",
        data={"placa": "AAA-111"},
        files={"archivo": ("vacio.jpg", b"", "image/jpeg")},
        headers=auth_only,
    )
    assert r_empty.status_code == 400

    # Archivo mayor a 5MB
    grande = b"x" * (5 * 1024 * 1024 + 64)
    r_big = client.post(
        "/api/vehiculos/upload",
        data={"placa": "AAA-111"},
        files={"archivo": ("pesada.jpg", grande, "image/jpeg")},
        headers=auth_only,
    )
    assert r_big.status_code == 400
    assert "5MB" in r_big.text

    # Imagen válida dentro del límite
    r_ok = client.post(
        "/api/vehiculos/upload",
        data={"placa": "AAA-111"},
        files={"archivo": ("frente.jpg", b"\xff\xd8\xff\xe0valid-jpeg-bytes", "image/jpeg")},
        headers=auth_only,
    )
    assert r_ok.status_code == 200, r_ok.text
    assert "url" in r_ok.json() or "urlImagen" in r_ok.json()
