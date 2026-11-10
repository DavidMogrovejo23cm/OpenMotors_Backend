import logging
from datetime import datetime
from sqlalchemy.orm import Session

from app.core.database import Base, engine, SessionLocal
from app.core.security import hash_password

# Importar todos los modelos para registrar sus tablas en Base.metadata
from app.modules.roles.models import Rol, UsuarioRol  # noqa: F401
from app.modules.usuarios.models import Usuario, RecuperacionContrasena  # noqa: F401
from app.modules.motos.models import Moto  # noqa: F401
from app.modules.mantenimiento.models import (  # noqa: F401
    ParametroMantenimiento,
    MantenimientoRealizado,
    AlertaEnviada,
)
from app.modules.inventario.models import Categoria, Producto, ContactoProveedor  # noqa: F401
from app.modules.facturacion.models import Factura, DetalleFactura  # noqa: F401
from app.modules.taller.models import (  # noqa: F401
    Tipo,
    Registro,
    DiagnosticoMoto,
    DetalleDiagnostico,
)
from app.modules.combustible.models import CargaCombustible, AppConfig  # noqa: F401
from app.modules.finanzas.models import PagoEmpleado  # noqa: F401
from app.modules.rutas.models import Ruta  # noqa: F401

logger = logging.getLogger("gmotors.seeder")


def init_db_and_seed() -> None:
    """Crea todas las tablas si no existen e inicializa los datos semilla."""
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    try:
        _seed_roles(db)
        _seed_default_users(db)
        _backfill_referral_codes(db)
        _seed_service_types(db)
        _seed_maintenance_parameters(db)
        logger.info("Base de datos e información semilla verificadas correctamente.")
    except Exception as exc:
        db.rollback()
        logger.error(f"Error durante la inicialización de datos semilla: {exc}")
    finally:
        db.close()


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
    pwd_default = hash_password("123456")
    usuarios_def = [
        {
            "nombre_completo": "Open Motors Oficial",
            "nombre_usuario": "openmotors",
            "correo": "info@openmotor.com",
            "ciudad": "Quito",
            "descripcion": "Cuenta administrativa oficial de Open Motors",
            "id_rol": 1,
        },
        {
            "nombre_completo": "Administrador General",
            "nombre_usuario": "admin",
            "correo": "admin@openmotor.com",
            "ciudad": "Quito",
            "descripcion": "Administrador del sistema",
            "id_rol": 1,
        },
        {
            "nombre_completo": "Mecánico Principal",
            "nombre_usuario": "mecanico",
            "correo": "mecanico@openmotor.com",
            "ciudad": "Quito",
            "descripcion": "Especialista técnico de taller",
            "id_rol": 3,
        },
        {
            "nombre_completo": "Cliente Demo",
            "nombre_usuario": "cliente",
            "correo": "cliente@openmotor.com",
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
            descripcion="Revisión completa de 15 puntos, ajuste de cadena, frenos y lubricación",
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
            descripcion="Diagnóstico y reparación de batería, luces, estator o regulador",
            concepto_manual="Diagnóstico y mano de obra eléctrica",
            concepto_cantidad=1,
            concepto_precio_unitario=15.0,
        ),
        Tipo(
            nombre="Afinación de Motor (ABC)",
            descripcion="Calibración de válvulas, limpieza de carburador/inyector y cambio de bujía",
            concepto_manual="Mano de obra ABC de motor",
            concepto_cantidad=1,
            concepto_precio_unitario=30.0,
        ),
    ]
    db.add_all(tipos_iniciales)
    db.commit()


def _seed_maintenance_parameters(db: Session) -> None:
    if db.query(ParametroMantenimiento).count() > 0:
        return

    # 35 parámetros basados en las condiciones geográficas y climáticas de Ecuador
    rangos = [
        # (cc_min, cc_max, aceite, filtro_aire, bujia, frenos, kit_arrastre, valvulas, general)
        (100, 150, 2000, 4000, 6000, 5000, 15000, 6000, 3000),
        (151, 200, 2500, 5000, 8000, 5000, 18000, 8000, 3500),
        (201, 250, 3000, 6000, 10000, 6000, 20000, 10000, 4000),
        (251, 350, 3500, 8000, 12000, 6000, 22000, 12000, 5000),
        (351, 1200, 5000, 10000, 15000, 8000, 25000, 15000, 6000),
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
                tipo_mantenimiento="KIT_ARRASTRE",
                intervalo_km=km_ka,
                descripcion=f"Cambio de cadena, piñón y catalina {etiqueta}",
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

