from typing import Optional, List, Tuple
from pydantic import BaseModel, ConfigDict, Field, AliasChoices
from fastapi import APIRouter, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.usuarios.models import Usuario
from app.modules.roles.models import UsuarioRol
from app.shared.email_service import email_service

ofertas_router = APIRouter(prefix="/api/ofertas", tags=["Ofertas y Marketing"])


class OfertaIndividualRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    correo: str
    nombre: Optional[str] = "Cliente"
    titulo: Optional[str] = "¡Promoción Especial Open Auto!"
    mensaje: str
    descuento: Optional[str] = None
    validez: Optional[str] = None
    imagenUrl: Optional[str] = Field(default=None, validation_alias=AliasChoices("imagenUrl", "imagen_url"))


class OfertaMasivaRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    titulo: str = "¡Oferta Exclusiva Open Auto!"
    mensaje: str
    descuento: Optional[str] = None
    validez: Optional[str] = None
    imagenUrl: Optional[str] = Field(default=None, validation_alias=AliasChoices("imagenUrl", "imagen_url"))
    correos: Optional[List[str]] = None
    idsUsuarios: Optional[List[int]] = Field(
        default=None, validation_alias=AliasChoices("idsUsuarios", "ids_usuarios")
    )
    soloClientes: Optional[bool] = Field(default=True, validation_alias=AliasChoices("soloClientes", "solo_clientes"))


def _enviar_lote_en_segundo_plano(destinatarios: List[Tuple[str, str]], payload: OfertaMasivaRequest) -> None:
    for correo, nombre in destinatarios:
        try:
            email_service.enviar_correo_oferta(
                destinatario=correo,
                nombre_cliente=nombre,
                titulo=payload.titulo,
                mensaje=payload.mensaje,
                descuento=payload.descuento,
                validez=payload.validez,
            )
        except Exception:
            pass


@ofertas_router.post("/enviar")
def enviar_oferta_individual(payload: OfertaIndividualRequest, background_tasks: BackgroundTasks):
    if not payload.correo or not payload.correo.strip():
        return JSONResponse(status_code=400, content={"error": "El correo es obligatorio"})
    background_tasks.add_task(
        email_service.enviar_correo_oferta,
        destinatario=payload.correo.strip(),
        nombre_cliente=payload.nombre or "Cliente",
        titulo=payload.titulo or "¡Promoción Especial Open Auto!",
        mensaje=payload.mensaje,
        descuento=payload.descuento,
        validez=payload.validez,
    )
    return {
        "mensaje": f"Oferta programada para envío en segundo plano a {payload.correo}",
        "enviados": 1,
    }


@ofertas_router.post("/enviar-emails")
def enviar_oferta_masiva(
    payload: OfertaMasivaRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    destinatarios: List[Tuple[str, str]] = []

    if payload.correos:
        for c in payload.correos:
            if c and c.strip():
                destinatarios.append((c.strip(), "Cliente"))
    elif payload.idsUsuarios:
        usuarios = db.query(Usuario).filter(Usuario.id_usuario.in_(payload.idsUsuarios)).all()
        for u in usuarios:
            if u.correo:
                destinatarios.append((u.correo, u.nombre_completo))
    else:
        if payload.soloClientes:
            rels = db.query(UsuarioRol).filter(UsuarioRol.id_rol == 2, UsuarioRol.estado == 1).all()
            ids = [r.id_usuario for r in rels]
            usuarios = db.query(Usuario).filter(Usuario.id_usuario.in_(ids)).all() if ids else []
        else:
            usuarios = db.query(Usuario).all()

        for u in usuarios:
            if u.correo:
                destinatarios.append((u.correo, u.nombre_completo))

    background_tasks.add_task(_enviar_lote_en_segundo_plano, destinatarios, payload)

    return {
        "mensaje": f"Campaña enviada a cola en segundo plano para {len(destinatarios)} destinatarios",
        "enviados": len(destinatarios),
        "totalDestinatarios": len(destinatarios),
    }

