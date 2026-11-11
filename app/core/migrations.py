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
