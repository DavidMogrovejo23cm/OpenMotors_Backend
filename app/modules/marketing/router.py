from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field, AliasChoices
from fastapi import APIRouter, Depends
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
    titulo: Optional[str] = "¡Promoción Especial Open Motors!"
    mensaje: str
    descuento: Optional[str] = None
    validez: Optional[str] = None
    imagenUrl: Optional[str] = Field(default=None, validation_alias=AliasChoices("imagenUrl", "imagen_url"))


class OfertaMasivaRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    titulo: str = "¡Oferta Exclusiva Open Motors!"
    mensaje: str
    descuento: Optional[str] = None
    validez: Optional[str] = None
    imagenUrl: Optional[str] = Field(default=None, validation_alias=AliasChoices("imagenUrl", "imagen_url"))
    correos: Optional[List[str]] = None
    idsUsuarios: Optional[List[int]] = Field(
        default=None, validation_alias=AliasChoices("idsUsuarios", "ids_usuarios")
    )
    soloClientes: Optional[bool] = Field(default=True, validation_alias=AliasChoices("soloClientes", "solo_clientes"))


@ofertas_router.post("/enviar")
def enviar_oferta_individual(payload: OfertaIndividualRequest):
    if not payload.correo or not payload.correo.strip():
        return JSONResponse(status_code=400, content={"error": "El correo es obligatorio"})
    email_service.enviar_correo_oferta(
        destinatario=payload.correo.strip(),
        nombre_cliente=payload.nombre or "Cliente",
        titulo=payload.titulo or "¡Promoción Especial Open Motors!",
        mensaje=payload.mensaje,
        descuento=payload.descuento,
        validez=payload.validez,
    )
    return {
        "mensaje": f"Oferta enviada exitosamente a {payload.correo}",
        "enviados": 1,
    }


@ofertas_router.post("/enviar-emails")
def enviar_oferta_masiva(payload: OfertaMasivaRequest, db: Session = Depends(get_db)):
    destinatarios = []

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

    enviados = 0
    errores = 0
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
            enviados += 1
        except Exception:
            errores += 1

    return {
        "mensaje": f"Proceso completado. Enviados: {enviados}, Errores: {errores}",
        "enviados": enviados,
        "errores": errores,
        "totalDestinatarios": len(destinatarios),
    }

