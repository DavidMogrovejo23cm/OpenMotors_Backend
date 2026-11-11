import logging
from datetime import datetime
from sqlalchemy.orm import Session

from app.core.database import Base, engine, SessionLocal
from app.core.config import settings
from app.core.migrations import migrate_vehicle_schema
from app.core.security import hash_password

# Importar todos los modelos para registrar sus tablas en Base.metadata
from app.modules.roles.models import Rol, UsuarioRol  # noqa: F401
from app.modules.usuarios.models import Usuario, RecuperacionContrasena  # noqa: F401
from app.modules.vehiculos.models import Vehiculo  # noqa: F401
from app.modules.mantenimiento.models import (  # noqa: F401
    ParametroMantenimiento,
    MantenimientoRealizado,
    AlertaEnviada,
)
from app.modules.inventario.models import Categoria, Producto, ContactoProveedor, MovimientoKardex  # noqa: F401
from app.modules.facturacion.models import Factura, DetalleFactura  # noqa: F401
from app.modules.taller.models import (  # noqa: F401
    Tipo,
    Registro,
    DiagnosticoVehiculo,
    DetalleDiagnostico,
    RecepcionVehiculo,
)
from app.modules.combustible.models import CargaCombustible, AppConfig  # noqa: F401
from app.modules.finanzas.models import PagoEmpleado  # noqa: F401
from app.modules.rutas.models import Ruta  # noqa: F401

logger = logging.getLogger("openauto.seeder")


def init_db_and_seed() -> None:
    """Crea todas las tablas si no existen e inicializa los datos semilla."""
    migrate_vehicle_schema(engine)
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    try:
        _seed_roles(db)
        _seed_default_users(db)
        _backfill_referral_codes(db)
        _seed_categories(db)
        _seed_service_types(db)
        _replace_legacy_maintenance_parameters(db)
        _seed_maintenance_parameters(db)
        logger.info("Base de datos e información semilla verificadas correctamente.")
    except Exception as exc:
        db.rollback()
        logger.error(f"Error durante la inicialización de datos semilla: {exc}")
    finally:
        db.close()


def _seed_categories(db: Session) -> None:
    if db.query(Categoria).count() > 0:
        return
    cats = [
        Categoria(nombre="Repuestos de Motor", descripcion="Bujías, correas, empaques y componentes mecánicos"),
        Categoria(nombre="Sistema de Frenos", descripcion="Pastillas, zapatas, discos y tambores"),
        Categoria(nombre="Suspensión y Dirección", descripcion="Amortiguadores, rótulas, terminales y bujes"),
        Categoria(nombre="Filtros y Fluidos", descripcion="Aceites, refrigerantes, filtros de aire, aceite y gasolina"),
        Categoria(nombre="Sistema Eléctrico", descripcion="Baterías, alternadores, bobinas y sensores"),
        Categoria(nombre="Repuestos Generales", descripcion="Misceláneos y accesorios de taller"),
    ]
    db.add_all(cats)
    db.commit()


def _seed_roles(db: Session) -> None:
    roles_def = [
        (1, "ADMIN"),
        (2, "CLIENTE"),
        (3, "MECANICO"),
    ]
    for id_rol, nombre in roles_def:
        existente = db.query(Rol).filter((Rol.id_rol == id_rol) | (Rol.nombre == nombre)).first()
        if not existente:
            db.add(Rol(id_rol=id_rol, nombre=nombre))
    db.commit()


def _seed_default_users(db: Session) -> None:
    if not settings.SEED_DEMO_DATA:
        _seed_bootstrap_admin(db)
        return

    pwd_default = hash_password("123456")
    usuarios_def = [
        {
            "nombre_completo": "Open Auto Oficial",
            "nombre_usuario": "openauto",
            "correo": "info@openauto.com",
            "ciudad": "Quito",
            "descripcion": "Cuenta administrativa oficial de Open Auto",
            "id_rol": 1,
        },
        {
            "nombre_completo": "Administrador General",
            "nombre_usuario": "admin",
            "correo": "admin@openauto.com",
            "ciudad": "Quito",
            "descripcion": "Administrador del sistema",
            "id_rol": 1,
        },
        {
            "nombre_completo": "Mecánico Principal",
            "nombre_usuario": "mecanico",
            "correo": "mecanico@openauto.com",
            "ciudad": "Quito",
            "descripcion": "Especialista técnico de taller",
            "id_rol": 3,
        },
        {
            "nombre_completo": "Cliente Demo",
            "nombre_usuario": "cliente",
            "correo": "cliente@openauto.com",
            "ciudad": "Quito",
            "descripcion": "Cliente demostrativo",
            "id_rol": 2,
        },
    ]

    for item in usuarios_def:
        u = (
            db.query(Usuario)
            .filter(
                (Usuario.correo == item["correo"])
                | (Usuario.nombre_usuario == item["nombre_usuario"])
            )
            .first()
        )
        if not u:
            u = Usuario(
                nombre_completo=item["nombre_completo"],
                nombre_usuario=item["nombre_usuario"],
                correo=item["correo"],
                contrasena=pwd_default,
                pais="Ecuador",
                ciudad=item["ciudad"],
                descripcion=item["descripcion"],
                puntos_bonus=0,
                referido_usado=False,
            )
            u.ensure_defaults()
            db.add(u)
            db.flush()

        rel = (
            db.query(UsuarioRol)
            .filter(
                UsuarioRol.id_usuario == u.id_usuario,
                UsuarioRol.id_rol == item["id_rol"],
            )
            .first()
        )
        if not rel:
            db.add(
                UsuarioRol(
                    id_usuario=u.id_usuario,
                    id_rol=item["id_rol"],
                    estado=1,
                    fecha_creacion=datetime.now(),
                )
            )
    db.commit()


def _backfill_referral_codes(db: Session) -> None:
    usuarios = db.query(Usuario).all()
    modificados = False
    for u in usuarios:
        if not u.codigo_referido or u.puntos_bonus is None:
            u.ensure_defaults()
            modificados = True
    if modificados:
        db.commit()


def _seed_bootstrap_admin(db: Session) -> None:
    """Crea el primer administrador solo si las tres credenciales vienen del entorno."""
    username = settings.BOOTSTRAP_ADMIN_USERNAME.strip()
    email = settings.BOOTSTRAP_ADMIN_EMAIL.strip().lower()
    password = settings.BOOTSTRAP_ADMIN_PASSWORD
    if not (username and email and password):
        return
    if len(password) < 12:
        logger.error("BOOTSTRAP_ADMIN_PASSWORD debe tener al menos 12 caracteres")
        return

    existe_admin = (
        db.query(UsuarioRol)
        .join(Rol, UsuarioRol.id_rol == Rol.id_rol)
        .filter(Rol.nombre == "ADMIN", UsuarioRol.estado == 1)
        .first()
    )
    if existe_admin:
        return

    usuario = (
        db.query(Usuario)
        .filter((Usuario.correo == email) | (Usuario.nombre_usuario == username))
        .first()
    )
    if not usuario:
        usuario = Usuario(
            nombre_completo="Administrador inicial",
            nombre_usuario=username,
            correo=email,
            contrasena=hash_password(password),
            pais="Ecuador",
            puntos_bonus=0,
            referido_usado=False,
        )
        usuario.ensure_defaults()
        db.add(usuario)
        db.flush()

    admin_role = db.query(Rol).filter(Rol.nombre == "ADMIN").first()
    if admin_role:
        db.add(UsuarioRol(id_usuario=usuario.id_usuario, id_rol=admin_role.id_rol, estado=1))
        db.commit()
        logger.info("Administrador inicial creado desde las variables de entorno.")


def _seed_service_types(db: Session) -> None:
    if db.query(Tipo).count() > 0:
        return
    tipos_iniciales = [
        Tipo(
            nombre="Cambio de Aceite",
            descripcion="Cambio de aceite de motor y revisión de nivel",
            concepto_manual="Mano de obra cambio de aceite",
            concepto_cantidad=1,
            concepto_precio_unitario=5.0,
        ),
        Tipo(
            nombre="Mantenimiento Preventivo General",
            descripcion="Revisión completa de frenos, fluidos, suspensión, dirección y neumáticos",
            concepto_manual="Mano de obra mantenimiento preventivo",
            concepto_cantidad=1,
            concepto_precio_unitario=25.0,
        ),
        Tipo(
            nombre="Servicio de Frenos",
            descripcion="Cambio de pastillas/zapatas y purgado de líquido de frenos",
            concepto_manual="Mano de obra sistema de frenos",
            concepto_cantidad=1,
            concepto_precio_unitario=12.0,
        ),
        Tipo(
            nombre="Sistema Eléctrico",
            descripcion="Diagnóstico y reparación de batería, alternador, luces y sensores",
            concepto_manual="Diagnóstico y mano de obra eléctrica",
            concepto_cantidad=1,
            concepto_precio_unitario=15.0,
        ),
        Tipo(
            nombre="Afinación de Motor",
            descripcion="Revisión de bujías, inyección, filtros y calibración del motor",
            concepto_manual="Mano de obra de afinación",
            concepto_cantidad=1,
            concepto_precio_unitario=30.0,
        ),
    ]
    db.add_all(tipos_iniciales)
    db.commit()


def _seed_maintenance_parameters(db: Session) -> None:
    if db.query(ParametroMantenimiento).count() > 0:
        return

    # Parámetros de mantenimiento preventivo para vehículos de pasajeros.
    rangos = [
        # (cc_min, cc_max, aceite, filtro_aire, bujia, frenos, transmision, valvulas, general)
        (800, 1600, 5000, 10000, 20000, 10000, 40000, 30000, 10000),
        (1601, 2500, 7000, 12000, 30000, 12000, 50000, 40000, 12000),
        (2501, 6000, 8000, 15000, 35000, 15000, 60000, 50000, 15000),
    ]

    parametros = []
    for cc_min, cc_max, km_ac, km_fa, km_bu, km_fr, km_ka, km_va, km_ge in rangos:
        etiqueta = f"({cc_min}-{cc_max}cc)"
        parametros.extend([
            ParametroMantenimiento(
                cc_min=cc_min,
                cc_max=cc_max,
                tipo_mantenimiento="CAMBIO_ACEITE",
                intervalo_km=km_ac,
                descripcion=f"Cambio de aceite de motor y filtro {etiqueta}",
            ),
            ParametroMantenimiento(
                cc_min=cc_min,
                cc_max=cc_max,
                tipo_mantenimiento="FILTRO_AIRE",
                intervalo_km=km_fa,
                descripcion=f"Limpieza o reemplazo de filtro de aire {etiqueta}",
            ),
            ParametroMantenimiento(
                cc_min=cc_min,
                cc_max=cc_max,
                tipo_mantenimiento="BUJIA",
                intervalo_km=km_bu,
                descripcion=f"Revisión y cambio de bujía de encendido {etiqueta}",
            ),
            ParametroMantenimiento(
                cc_min=cc_min,
                cc_max=cc_max,
                tipo_mantenimiento="FRENOS",
                intervalo_km=km_fr,
                descripcion=f"Revisión de pastillas, zapatas y líquido de frenos {etiqueta}",
            ),
            ParametroMantenimiento(
                cc_min=cc_min,
                cc_max=cc_max,
                tipo_mantenimiento="SISTEMA_TRANSMISION",
                intervalo_km=km_ka,
                descripcion=f"Revisión de transmisión, embrague y fluidos {etiqueta}",
            ),
            ParametroMantenimiento(
                cc_min=cc_min,
                cc_max=cc_max,
                tipo_mantenimiento="CALIBRACION_VALVULAS",
                intervalo_km=km_va,
                descripcion=f"Calibración de holgura de válvulas {etiqueta}",
            ),
            ParametroMantenimiento(
                cc_min=cc_min,
                cc_max=cc_max,
                tipo_mantenimiento="REVISION_GENERAL",
                intervalo_km=km_ge,
                descripcion=f"Mantenimiento preventivo e inspección general {etiqueta}",
            ),
        ])

    db.add_all(parametros)
    db.commit()


def _replace_legacy_maintenance_parameters(db: Session) -> None:
    """Reemplaza el catálogo heredado por el de autos y vehículos.

    Un catálogo personalizado nunca se toca: la detección se limita al rango
    histórico, cuyo mayor cilindraje era 1200 cc.
    """
    parametros = db.query(ParametroMantenimiento).all()
    if not parametros:
        return
    if max(param.cc_max for param in parametros) > 1200:
        return
    for parametro in parametros:
        db.delete(parametro)
    db.commit()
    logger.info("Catálogo de mantenimiento actualizado para vehículos.")

