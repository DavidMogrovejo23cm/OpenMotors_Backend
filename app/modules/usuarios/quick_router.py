import secrets
from typing import Optional
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict, Field, AliasChoices
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.usuarios.models import Usuario
from app.modules.usuarios.schemas import UsuarioCreate
from app.modules.usuarios.service import UsuarioService
from app.modules.vehiculos.models import Vehiculo
from app.modules.vehiculos.schemas import VehiculoCreate
from app.modules.vehiculos.service import VehiculoService

quick_accounts_router = APIRouter(prefix="/api/quick-accounts", tags=["Cuentas Rápidas"])


class QuickAccountCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    nombre_completo: str = Field(..., validation_alias=AliasChoices("nombre_completo", "nombreCompleto"))
    correo: str
    telefono: Optional[str] = None
    cedula: Optional[str] = None
    placa: str
    marca: str
    modelo: str
    anio: int = 2024
    kilometraje: Optional[int] = 0
    cilindraje: Optional[int] = 1600


@quick_accounts_router.post("/create", status_code=status.HTTP_201_CREATED)
def crear_cuenta_rapida(payload: QuickAccountCreate, db: Session = Depends(get_db)):
    """Crea o vincula rápidamente un cliente y su vehículo en recepción."""
    correo_limpio = payload.correo.strip().lower()
    placa_limpia = payload.placa.strip().upper()

    # Buscar usuario existente por correo o cédula
    usuario = db.query(Usuario).filter(Usuario.correo == correo_limpio).first()
    if not usuario and payload.cedula:
        usuario = db.query(Usuario).filter(Usuario.cedula == payload.cedula.strip()).first()

    if not usuario:
        base_username = correo_limpio.split("@")[0].replace(".", "_")
        username_candidato = base_username
        contador = 1
        while db.query(Usuario).filter(Usuario.nombre_usuario == username_candidato).first():
            username_candidato = f"{base_username}_{contador}"
            contador += 1

        nuevo_user_data = UsuarioCreate(
            nombre_completo=payload.nombre_completo,
            nombre_usuario=username_candidato,
            correo=correo_limpio,
            contrasena=secrets.token_urlsafe(12),
            telefono=payload.telefono,
            cedula=payload.cedula,
            ciudad="Quito",
            pais="Ecuador",
            descripcion="Cliente registrado vía Quick Account en taller",
        )
        usuario = UsuarioService.registrar(db, nuevo_user_data, asignar_rol_cliente=True)

    # Buscar o crear vehículo
    vehiculo = VehiculoService.obtener_por_placa(db, placa_limpia)
    if not vehiculo:
        vehiculo_in = VehiculoCreate(
            placa=placa_limpia,
            marca=payload.marca,
            modelo=payload.modelo,
            anio=payload.anio,
            kilometraje=payload.kilometraje or 0,
            cilindraje=payload.cilindraje or 1600,
            id_usuario=usuario.id_usuario,
            nombre_vehiculo=f"{payload.marca} {payload.modelo}",
        )
        vehiculo = VehiculoService.crear(db, vehiculo_in)

    v_dict = vehiculo.to_dict()
    return {
        "usuario": usuario.to_dict(include_roles=True),
        "moto": v_dict,
        "vehiculo": v_dict,
    }
