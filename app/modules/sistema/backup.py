"""Servicio de respaldo y recuperación de base de datos (RNF-16 / RNF-17)."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import uuid
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import Date, DateTime, Numeric, Time, delete, select, text
from sqlalchemy.orm import Session

from app.core.database import Base
from app.core.exceptions import BusinessValidationError, EntityNotFoundError


_BACKUP_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


def obtener_directorio_respaldos(backup_dir: Optional[str | Path] = None) -> Path:
    """Devuelve y crea (si no existe) el directorio configurado para respaldos."""
    ruta = Path(backup_dir) if backup_dir is not None else Path(os.getenv("OPENMOTORS_BACKUP_DIR", "backups"))
    ruta.mkdir(parents=True, exist_ok=True)
    return ruta


def _validar_backup_id(backup_id: str) -> str:
    limpio = (backup_id or "").strip()
    if not limpio or ".." in limpio or not _BACKUP_ID_RE.match(limpio):
        raise BusinessValidationError("Identificador de respaldo inválido")
    return limpio


def _serializar_valor(valor: Any) -> Any:
    if isinstance(valor, datetime):
        return {"__tipo__": "datetime", "valor": valor.isoformat()}
    if isinstance(valor, date):
        return {"__tipo__": "date", "valor": valor.isoformat()}
    if isinstance(valor, time):
        return {"__tipo__": "time", "valor": valor.isoformat()}
    if isinstance(valor, Decimal):
        return {"__tipo__": "decimal", "valor": str(valor)}
    if isinstance(valor, (bytes, bytearray)):
        return {"__tipo__": "bytes", "valor": bytes(valor).hex()}
    return valor


def _deserializar_valor(valor: Any, columna: Any) -> Any:
    if valor is None:
        return None
    if isinstance(valor, dict) and "__tipo__" in valor:
        tipo = valor["__tipo__"]
        bruto = valor["valor"]
        if tipo == "datetime":
            return datetime.fromisoformat(bruto)
        if tipo == "date":
            return date.fromisoformat(bruto)
        if tipo == "time":
            return time.fromisoformat(bruto)
        if tipo == "decimal":
            return Decimal(bruto)
        if tipo == "bytes":
            return bytes.fromhex(bruto)
    if isinstance(valor, str):
        if isinstance(columna.type, DateTime):
            return datetime.fromisoformat(valor)
        if isinstance(columna.type, Date):
            return date.fromisoformat(valor[:10])
        if isinstance(columna.type, Time):
            return time.fromisoformat(valor)
        if isinstance(columna.type, Numeric):
            return Decimal(valor)
    return valor


def _sha256_archivo(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as f:
        for bloque in iter(lambda: f.read(65536), b""):
            h.update(bloque)
    return h.hexdigest()


class BackupService:
    """Gestiona respaldos lógicos (JSON verificable) y físicos (SQLite) con restauración segura."""

    @staticmethod
    def _resolver_sqlite_origen(db: Session, sqlite_path: Optional[str | Path] = None) -> Optional[Path]:
        if sqlite_path is not None:
            p = Path(sqlite_path)
            return p if p.exists() and p.is_file() else None
        bind = db.get_bind()
        if bind is None or bind.dialect.name != "sqlite":
            return None
        db_name = getattr(bind.url, "database", None)
        if not db_name or db_name == ":memory:":
            return None
        p = Path(db_name)
        return p if p.exists() and p.is_file() else None

    @classmethod
    def crear_respaldo(
        cls,
        db: Session,
        *,
        backup_dir: Optional[str | Path] = None,
        sqlite_path: Optional[str | Path] = None,
        responsable: str = "SYSTEM",
        nota: Optional[str] = None,
    ) -> dict[str, Any]:
        """Genera un respaldo consistente JSON (y copia física SQLite si aplica) con manifiesto SHA-256."""
        directorio = obtener_directorio_respaldos(backup_dir)
        ahora = datetime.now()
        stamp = f"{ahora.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        backup_id = f"backup_{stamp}"

        tablas_datos: dict[str, list[dict[str, Any]]] = {}
        conteos: dict[str, int] = {}
        total_registros = 0

        for tabla in Base.metadata.sorted_tables:
            filas = db.execute(select(tabla)).mappings().all()
            serializadas = [
                {col: _serializar_valor(val) for col, val in dict(fila).items()}
                for fila in filas
            ]
            tablas_datos[tabla.name] = serializadas
            conteos[tabla.name] = len(serializadas)
            total_registros += len(serializadas)

        archivo_json = directorio / f"{backup_id}.json"
        paquete = {
            "backupId": backup_id,
            "creadoEn": ahora.isoformat(),
            "responsable": responsable,
            "nota": (nota or "").strip() or None,
            "tablas": tablas_datos,
        }
        archivo_json.write_text(
            json.dumps(paquete, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        sha256_json = _sha256_archivo(archivo_json)

        archivo_sqlite_nombre: Optional[str] = None
        sha256_sqlite: Optional[str] = None
        origen_sqlite = cls._resolver_sqlite_origen(db, sqlite_path=sqlite_path)
        if origen_sqlite is not None:
            archivo_sqlite = directorio / f"{backup_id}.sqlite"
            src_conn = sqlite3.connect(str(origen_sqlite))
            dst_conn = sqlite3.connect(str(archivo_sqlite))
            try:
                src_conn.backup(dst_conn)
            finally:
                dst_conn.close()
                src_conn.close()
            archivo_sqlite_nombre = archivo_sqlite.name
            sha256_sqlite = _sha256_archivo(archivo_sqlite)

        manifiesto = {
            "backupId": backup_id,
            "creadoEn": ahora.isoformat(),
            "responsable": responsable,
            "nota": (nota or "").strip() or None,
            "tipo": "SQLITE+JSON" if archivo_sqlite_nombre else "JSON",
            "archivoJson": archivo_json.name,
            "tamanoJsonBytes": archivo_json.stat().st_size,
            "sha256Json": sha256_json,
            "archivoSqlite": archivo_sqlite_nombre,
            "sha256Sqlite": sha256_sqlite,
            "totalTablas": len(conteos),
            "totalRegistros": total_registros,
            "conteos": conteos,
        }
        archivo_manifiesto = directorio / f"{backup_id}.manifest.json"
        archivo_manifiesto.write_text(
            json.dumps(manifiesto, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return manifiesto

    @staticmethod
    def listar_respaldos(backup_dir: Optional[str | Path] = None) -> list[dict[str, Any]]:
        """Lista los respaldos registrados desde el más reciente al más antiguo."""
        directorio = obtener_directorio_respaldos(backup_dir)
        resultados: list[dict[str, Any]] = []
        for ruta in sorted(directorio.glob("*.manifest.json"), reverse=True):
            try:
                info = json.loads(ruta.read_text(encoding="utf-8"))
                archivo_json = info.get("archivoJson")
                info["disponible"] = bool(archivo_json and (directorio / archivo_json).exists())
                resultados.append(info)
            except Exception:
                continue
        resultados.sort(key=lambda r: r.get("creadoEn") or "", reverse=True)
        return resultados

    @classmethod
    def _cargar_manifiesto(cls, backup_id: str, backup_dir: Optional[str | Path] = None) -> tuple[Path, dict[str, Any]]:
        limpio = _validar_backup_id(backup_id)
        directorio = obtener_directorio_respaldos(backup_dir)
        ruta_manifiesto = directorio / f"{limpio}.manifest.json"
        if not ruta_manifiesto.exists():
            raise EntityNotFoundError(f"Respaldo '{limpio}' no encontrado")
        manifiesto = json.loads(ruta_manifiesto.read_text(encoding="utf-8"))
        return directorio, manifiesto

    @classmethod
    def verificar_integridad(
        cls,
        backup_id: str,
        backup_dir: Optional[str | Path] = None,
    ) -> dict[str, Any]:
        """Comprueba presencia física y hash SHA-256 del respaldo (y PRAGMA integrity_check si hay SQLite)."""
        directorio, manifiesto = cls._cargar_manifiesto(backup_id, backup_dir=backup_dir)
        archivo_json = directorio / str(manifiesto.get("archivoJson") or "")
        if not archivo_json.exists():
            raise EntityNotFoundError("El archivo de respaldo JSON no existe en disco")

        sha_actual_json = _sha256_archivo(archivo_json)
        json_valido = sha_actual_json == manifiesto.get("sha256Json")

        sqlite_integrity: Optional[str] = None
        sqlite_valido = True
        nombre_sqlite = manifiesto.get("archivoSqlite")
        if nombre_sqlite:
            archivo_sqlite = directorio / str(nombre_sqlite)
            if not archivo_sqlite.exists():
                sqlite_valido = False
                sqlite_integrity = "missing"
            else:
                sha_actual_sqlite = _sha256_archivo(archivo_sqlite)
                if sha_actual_sqlite != manifiesto.get("sha256Sqlite"):
                    sqlite_valido = False
                    sqlite_integrity = "checksum_mismatch"
                else:
                    conn = sqlite3.connect(str(archivo_sqlite))
                    try:
                        res = conn.execute("PRAGMA integrity_check").fetchone()
                        sqlite_integrity = str(res[0]) if res else "unknown"
                        sqlite_valido = sqlite_integrity == "ok"
                    finally:
                        conn.close()

        return {
            "backupId": manifiesto["backupId"],
            "valido": bool(json_valido and sqlite_valido),
            "jsonValido": json_valido,
            "sha256Esperado": manifiesto.get("sha256Json"),
            "sha256Actual": sha_actual_json,
            "sqliteValido": sqlite_valido,
            "sqliteIntegrity": sqlite_integrity,
            "totalRegistros": manifiesto.get("totalRegistros", 0),
            "totalTablas": manifiesto.get("totalTablas", 0),
        }

    @classmethod
    def restaurar_respaldo(
        cls,
        db: Session,
        backup_id: str,
        *,
        backup_dir: Optional[str | Path] = None,
    ) -> dict[str, Any]:
        """Restaura todas las tablas desde el respaldo JSON tras validar integridad SHA-256."""
        verif = cls.verificar_integridad(backup_id, backup_dir=backup_dir)
        if not verif["jsonValido"]:
            raise BusinessValidationError(
                "El archivo de respaldo está corrupto o fue alterado (falló verificación SHA-256)"
            )

        directorio, _ = cls._cargar_manifiesto(backup_id, backup_dir=backup_dir)
        paquete = json.loads((directorio / f"{verif['backupId']}.json").read_text(encoding="utf-8"))
        tablas_datos: dict[str, list[dict[str, Any]]] = paquete.get("tablas") or {}

        bind = db.get_bind()
        es_sqlite = bind is not None and bind.dialect.name == "sqlite"
        tablas_restauradas = 0
        registros_restaurados = 0

        try:
            if es_sqlite:
                db.execute(text("PRAGMA foreign_keys = OFF"))

            for tabla in reversed(Base.metadata.sorted_tables):
                if tabla.name in tablas_datos:
                    db.execute(delete(tabla))

            for tabla in Base.metadata.sorted_tables:
                filas = tablas_datos.get(tabla.name)
                if filas is None:
                    continue
                tablas_restauradas += 1
                if not filas:
                    continue
                cols = {c.name: c for c in tabla.columns}
                filas_tipadas = [
                    {
                        col: _deserializar_valor(val, cols[col])
                        for col, val in fila.items()
                        if col in cols
                    }
                    for fila in filas
                ]
                db.execute(tabla.insert(), filas_tipadas)
                registros_restaurados += len(filas_tipadas)

            db.commit()
            db.expire_all()
        except Exception:
            db.rollback()
            raise
        finally:
            if es_sqlite:
                try:
                    db.execute(text("PRAGMA foreign_keys = ON"))
                    db.commit()
                except Exception:
                    pass

        return {
            "backupId": verif["backupId"],
            "restaurado": True,
            "tablasRestauradas": tablas_restauradas,
            "registrosRestaurados": registros_restaurados,
            "restauradoEn": datetime.now().isoformat(),
        }

    @staticmethod
    def restaurar_archivo_sqlite(origen_sqlite: str | Path, destino_sqlite: str | Path) -> dict[str, Any]:
        """Restaura una copia física SQLite verificando previamente PRAGMA integrity_check."""
        origen = Path(origen_sqlite)
        destino = Path(destino_sqlite)
        if not origen.exists():
            raise EntityNotFoundError(f"Archivo SQLite no encontrado: {origen}")

        check_conn = sqlite3.connect(str(origen))
        try:
            res = check_conn.execute("PRAGMA integrity_check").fetchone()
            if not res or str(res[0]) != "ok":
                raise BusinessValidationError("El archivo SQLite de respaldo falló PRAGMA integrity_check")
        finally:
            check_conn.close()

        destino.parent.mkdir(parents=True, exist_ok=True)
        src_conn = sqlite3.connect(str(origen))
        dst_conn = sqlite3.connect(str(destino))
        try:
            src_conn.backup(dst_conn)
        finally:
            dst_conn.close()
            src_conn.close()

        return {
            "restaurado": True,
            "origen": str(origen),
            "destino": str(destino),
        }
