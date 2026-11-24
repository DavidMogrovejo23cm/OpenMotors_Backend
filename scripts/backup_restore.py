"""Herramienta CLI para respaldos y restauración de OpenMotors (RNF-16 / RNF-17)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.core.database import SessionLocal  # noqa: E402
from app.core.seeder import init_db_and_seed  # noqa: E402
from app.modules.sistema.backup import BackupService  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Respaldo y recuperación de base de datos OpenMotors")
    parser.add_argument("accion", choices=["backup", "list", "verify", "restore"], help="Operación a ejecutar")
    parser.add_argument("--dir", dest="backup_dir", default=None, help="Directorio de respaldos (por defecto ./backups)")
    parser.add_argument("--id", dest="backup_id", default=None, help="Identificador del respaldo (para verify o restore)")
    parser.add_argument("--nota", dest="nota", default=None, help="Nota descriptiva del respaldo")
    args = parser.parse_args()

    init_db_and_seed()
    db = SessionLocal()
    try:
        if args.accion == "backup":
            res = BackupService.crear_respaldo(
                db,
                backup_dir=args.backup_dir,
                responsable="CLI",
                nota=args.nota,
            )
            print(json.dumps(res, ensure_ascii=False, indent=2))
            return 0

        if args.accion == "list":
            res = BackupService.listar_respaldos(backup_dir=args.backup_dir)
            print(json.dumps(res, ensure_ascii=False, indent=2))
            return 0

        if not args.backup_id:
            print("Error: debes indicar --id <backup_id> para verify o restore", file=sys.stderr)
            return 2

        if args.accion == "verify":
            res = BackupService.verificar_integridad(args.backup_id, backup_dir=args.backup_dir)
            print(json.dumps(res, ensure_ascii=False, indent=2))
            return 0 if res.get("valido") else 1

        if args.accion == "restore":
            res = BackupService.restaurar_respaldo(db, args.backup_id, backup_dir=args.backup_dir)
            print(json.dumps(res, ensure_ascii=False, indent=2))
            return 0
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
