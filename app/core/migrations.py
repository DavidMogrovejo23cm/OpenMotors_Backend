"""Migraciones ligeras ejecutadas antes de crear las tablas SQLAlchemy.

Operaciones idempotentes para asegurar que la base de datos utilice el dominio de autos y vehículos.
"""

import logging

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


logger = logging.getLogger("openauto.migrations")


TABLE_RENAMES = (("motos", "vehiculos"), ("diagnostico_moto", "diagnostico_vehiculo"))

COLUMN_RENAMES = {
    "vehiculos": {
        "id_moto": "id_vehiculo",
        "nombre_moto": "nombre_vehiculo",
        "tipo_moto": "tipo_vehiculo",
        "ruta_imagen_motos": "ruta_imagen_vehiculo",
    },
    "mantenimiento_realizado": {"id_moto": "id_vehiculo"},
    "alerta_enviada": {"id_moto": "id_vehiculo"},
    "registros": {"id_moto": "id_vehiculo"},
    "diagnostico_vehiculo": {"id_moto": "id_vehiculo"},
    "carga_combustible": {"id_moto": "id_vehiculo"},
}


def migrate_vehicle_schema(engine: Engine) -> None:
    """Renombra las tablas y columnas anteriores si siguen presentes."""
    with engine.begin() as connection:
        tables = set(inspect(connection).get_table_names())
        for old_name, new_name in TABLE_RENAMES:
            if old_name in tables and new_name not in tables:
                connection.execute(text(f"ALTER TABLE {old_name} RENAME TO {new_name}"))
                logger.info("Esquema migrado: tabla %s renombrada a %s", old_name, new_name)

        for table_name, renames in COLUMN_RENAMES.items():
            tables = set(inspect(connection).get_table_names())
            if table_name not in tables:
                continue
            columns = {column["name"] for column in inspect(connection).get_columns(table_name)}
            for old_name, new_name in renames.items():
                if old_name in columns and new_name not in columns:
                    connection.execute(
                        text(f"ALTER TABLE {table_name} RENAME COLUMN {old_name} TO {new_name}")
                    )
                    logger.info(
                        "Esquema migrado: %s.%s renombrada a %s",
                        table_name,
                        old_name,
                        new_name,
                    )


def migrate_order_states(engine: Engine) -> None:
    """Preserva el código previo y marca los estados ambiguos; no deduce cobros de facturas."""
    with engine.begin() as connection:
        tables = set(inspect(connection).get_table_names())
        if "notas_de_venta" in tables:
            connection.execute(text("UPDATE notas_de_venta SET estado_pago='PENDIENTE' WHERE estado_pago='PENDIENTE_PAGO'"))
        if "registros" not in tables:
            return
        columns = {c["name"] for c in inspect(connection).get_columns("registros")}
        additions = {
            "estado_pago": "VARCHAR(20) NOT NULL DEFAULT 'PENDIENTE'",
            "monto_pagado": "FLOAT NOT NULL DEFAULT 0",
            "estado_legacy": "INTEGER",
            "revision_estado": "BOOLEAN NOT NULL DEFAULT FALSE",
            "estado_version": "INTEGER NOT NULL DEFAULT 0",
        }
        for name, definition in additions.items():
            if name not in columns:
                connection.execute(text(f"ALTER TABLE registros ADD COLUMN {name} {definition}"))
        rows = connection.execute(text("SELECT * FROM registros WHERE estado_version=0")).mappings().all()
        for row in rows:
            old = row["estado_legacy"] if row.get("estado_legacy") is not None else row["estado"]
            paid_note = None
            if "notas_de_venta" in tables:
                paid_note = connection.execute(text("SELECT total FROM notas_de_venta WHERE id_registro=:id AND estado_pago='PAGADO' ORDER BY id_nota_venta DESC LIMIT 1"), {"id": row["id_registro"]}).first()
            paid = bool(paid_note) or old == 7
            if row.get("fecha_entregado") or old == 4:
                state = 3
            elif row.get("fecha_completado") or old in (3, 7):
                state = 2
            elif old == 0:
                state = 0
            else:
                state = 1 if old in (1, 2) else 0
            ambiguous = old in (1, 2, 3, 4, 8) or old not in (0, 1, 2, 3, 4, 7, 8)
            amount = float(paid_note[0] if paid_note else row.get("costo_total") or 0) if paid else 0
            connection.execute(text("UPDATE registros SET estado_version=1, estado_legacy=:old, estado=:state, estado_pago=:payment, monto_pagado=:amount, revision_estado=:review WHERE id_registro=:id"), {"old": old, "state": state, "payment": "PAGADO" if paid else "PENDIENTE", "amount": amount, "review": ambiguous, "id": row["id_registro"]})
        logger.warning("Estados normalizados: %s registros; revisar revision_estado y estado_legacy antes de operar", len(rows))


def migrate_workshop_schema(engine: Engine) -> None:
    with engine.begin() as connection:
        tables = set(inspect(connection).get_table_names())
        additions = {
            "registros": {
                "flujo_integrado": "BOOLEAN NOT NULL DEFAULT FALSE",
                "horas_estimadas": "FLOAT",
            },
            "diagnostico_vehiculo": {"origen_diagnostico": "VARCHAR(30) NOT NULL DEFAULT 'CRITERIO_TECNICO'"},
        }
        for table, fields in additions.items():
            if table not in tables: continue
            columns = {c["name"] for c in inspect(connection).get_columns(table)}
            for name, definition in fields.items():
                if name not in columns: connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {definition}"))
        if "productos" in tables:
            duplicates = connection.execute(text("SELECT lower(codigo_barras) FROM productos WHERE codigo_barras IS NOT NULL AND trim(codigo_barras) <> '' GROUP BY lower(codigo_barras) HAVING count(*) > 1")).all()
            if not duplicates:
                connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_productos_barcode ON productos (lower(codigo_barras)) WHERE codigo_barras IS NOT NULL AND trim(codigo_barras) <> ''"))
            else:
                logger.warning("Códigos de barras duplicados pendientes de conciliación: %s", len(duplicates))


def migrate_users_security_schema(engine: Engine) -> None:
    """Agrega columnas de estado activo y versión de token a usuarios de forma idempotente."""
    with engine.begin() as connection:
        tables = set(inspect(connection).get_table_names())
        if "usuarios" not in tables:
            return
        columns = {c["name"] for c in inspect(connection).get_columns("usuarios")}
        additions = {
            "activo": "BOOLEAN NOT NULL DEFAULT TRUE",
            "token_version": "INTEGER NOT NULL DEFAULT 1",
        }
        for name, definition in additions.items():
            if name not in columns:
                connection.execute(text(f"ALTER TABLE usuarios ADD COLUMN {name} {definition}"))


def migrate_finance_schema(engine: Engine) -> None:
    """Agrega columna categoria a pagos_empleado de forma idempotente."""
    with engine.begin() as connection:
        tables = set(inspect(connection).get_table_names())
        if "pagos_empleado" not in tables:
            return
        columns = {c["name"] for c in inspect(connection).get_columns("pagos_empleado")}
        if "categoria" not in columns:
            connection.execute(text("ALTER TABLE pagos_empleado ADD COLUMN categoria VARCHAR(100)"))
