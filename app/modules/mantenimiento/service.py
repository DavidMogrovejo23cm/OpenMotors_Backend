import logging
from datetime import datetime
from typing import List, Dict, Any
from sqlalchemy.orm import Session

from app.core.exceptions import EntityNotFoundError
from app.modules.mantenimiento.models import (
    ParametroMantenimiento,
    MantenimientoRealizado,
    AlertaEnviada,
)
from app.shared.email_service import email_service

logger = logging.getLogger("gmotors.mantenimiento")


class MantenimientoService:
    @staticmethod
    def listar_parametros(db: Session) -> List[ParametroMantenimiento]:
        return db.query(ParametroMantenimiento).order_by(ParametroMantenimiento.id_parametro.asc()).all()

    @staticmethod
    def actualizar_parametro(
        db: Session, id_parametro: int, intervalo_km: int, descripcion: str = None
    ) -> ParametroMantenimiento:
        param = (
            db.query(ParametroMantenimiento)
            .filter(ParametroMantenimiento.id_parametro == id_parametro)
            .first()
        )
        if not param:
            raise EntityNotFoundError("Parámetro de mantenimiento", id_parametro)
        param.intervalo_km = intervalo_km
        if descripcion is not None:
            param.descripcion = descripcion
        db.commit()
        db.refresh(param)
        return param

    @staticmethod
    def listar_por_moto(db: Session, id_moto: int) -> List[MantenimientoRealizado]:
        return (
            db.query(MantenimientoRealizado)
            .filter(MantenimientoRealizado.id_moto == id_moto)
            .order_by(MantenimientoRealizado.fecha.desc())
            .all()
        )

    @staticmethod
    def registrar_o_actualizar(
        db: Session, id_moto: int, tipo: str, km_servicio: int
    ) -> MantenimientoRealizado:
        tipo_norm = tipo.strip().upper()
        existente = (
            db.query(MantenimientoRealizado)
            .filter(
                MantenimientoRealizado.id_moto == id_moto,
                MantenimientoRealizado.tipo == tipo_norm,
            )
            .first()
        )
        if existente:
            existente.km_servicio = km_servicio
            existente.fecha = datetime.now()
            db.commit()
            db.refresh(existente)
            return existente

        nuevo = MantenimientoRealizado(
            id_moto=id_moto,
            tipo=tipo_norm,
            km_servicio=km_servicio,
            fecha=datetime.now(),
        )
        db.add(nuevo)
        db.commit()
        db.refresh(nuevo)
        return nuevo

    @staticmethod
    def eliminar_por_moto_y_tipo(db: Session, id_moto: int, tipo: str) -> None:
        tipo_norm = tipo.strip().upper()
        regs = (
            db.query(MantenimientoRealizado)
            .filter(
                MantenimientoRealizado.id_moto == id_moto,
                MantenimientoRealizado.tipo == tipo_norm,
            )
            .all()
        )
        for r in regs:
            db.delete(r)
        db.commit()


class AlertaMantenimientoService:
    @staticmethod
    def obtener_parametros_para_cc(db: Session, cc: int) -> List[ParametroMantenimiento]:
        cc_val = cc if cc and cc > 0 else 150
        params = (
            db.query(ParametroMantenimiento)
            .filter(
                ParametroMantenimiento.cc_min <= cc_val,
                ParametroMantenimiento.cc_max >= cc_val,
            )
            .all()
        )
        if not params:
            params = (
                db.query(ParametroMantenimiento)
                .filter(
                    ParametroMantenimiento.cc_min <= 150,
                    ParametroMantenimiento.cc_max >= 150,
                )
                .all()
            )
        return params

    @staticmethod
    def inicializar_mantenimientos_moto(db: Session, id_moto: int, cc: int, km_actual: int) -> None:
        params = AlertaMantenimientoService.obtener_parametros_para_cc(db, cc)
        for p in params:
            existe = (
                db.query(MantenimientoRealizado)
                .filter(
                    MantenimientoRealizado.id_moto == id_moto,
                    MantenimientoRealizado.tipo == p.tipo_mantenimiento,
                )
                .first()
            )
            if not existe:
                db.add(
                    MantenimientoRealizado(
                        id_moto=id_moto,
                        tipo=p.tipo_mantenimiento,
                        km_servicio=km_actual or 0,
                        fecha=datetime.now(),
                    )
                )
        db.commit()

    @staticmethod
    def calcular_estado(db: Session, moto: Any) -> List[Dict[str, Any]]:
        km_actual = moto.kilometraje or 0
        cc = moto.cilindraje or 150

        parametros = AlertaMantenimientoService.obtener_parametros_para_cc(db, cc)
        realizados = MantenimientoService.listar_por_moto(db, moto.id_moto)
        mapa_ultimo_km = {r.tipo.upper(): r.km_servicio for r in realizados}

        estados: List[Dict[str, Any]] = []
        for param in parametros:
            intervalo = param.intervalo_km if param.intervalo_km and param.intervalo_km > 0 else 3000
            tipo_key = param.tipo_mantenimiento.upper()

            if tipo_key in mapa_ultimo_km:
                ultimo_cambio = mapa_ultimo_km[tipo_key]
                proximo_cambio = ultimo_cambio + intervalo
                km_recorridos = max(0, km_actual - ultimo_cambio)
                km_restante = proximo_cambio - km_actual
                porcentaje = min(100, int((km_recorridos * 100.0) / intervalo))
            else:
                ciclo_actual = km_actual // intervalo
                proximo_cambio = (ciclo_actual + 1) * intervalo
                km_en_ciclo = km_actual % intervalo
                km_restante = intervalo - km_en_ciclo
                porcentaje = int((km_en_ciclo * 100.0) / intervalo)

            if km_restante <= 0:
                estado_str = "VENCIDO"
                km_restante = 0
                porcentaje = 100
            elif porcentaje >= 80 or km_restante <= 500:
                estado_str = "PROXIMO"
            else:
                estado_str = "OK"

            estados.append({
                "tipo": param.tipo_mantenimiento,
                "descripcion": param.descripcion,
                "intervaloKm": intervalo,
                "kmActual": km_actual,
                "proximoCambioKm": proximo_cambio,
                "kmRestante": km_restante,
                "porcentajeDesgaste": porcentaje,
                "estado": estado_str,
            })

        return estados

    @staticmethod
    def verificar_y_enviar_alertas(db: Session, moto: Any) -> List[Dict[str, Any]]:
        estados = AlertaMantenimientoService.calcular_estado(db, moto)
        if not moto.id_usuario:
            return estados

        from app.modules.usuarios.models import Usuario
        dueno = db.query(Usuario).filter(Usuario.id_usuario == moto.id_usuario).first()
        if not dueno or not dueno.correo:
            return estados

        alertas_activas = [e for e in estados if e["estado"] in ("PROXIMO", "VENCIDO")]
        if not alertas_activas:
            return estados

        debe_enviar = False
        for item in alertas_activas:
            ciclo_km = item["proximoCambioKm"]
            ya_enviada = (
                db.query(AlertaEnviada)
                .filter(
                    AlertaEnviada.id_moto == moto.id_moto,
                    AlertaEnviada.tipo_mantenimiento == item["tipo"],
                    AlertaEnviada.km_enviado == ciclo_km,
                )
                .first()
            )
            if not ya_enviada:
                debe_enviar = True
                break

        if debe_enviar:
            try:
                moto_desc = f"{moto.marca} {moto.modelo}"
                email_service.enviar_resumen_mantenimiento(
                    destinatario=dueno.correo,
                    nombre_cliente=dueno.nombre_completo,
                    moto_desc=moto_desc,
                    placa=moto.placa,
                    km_actual=moto.kilometraje or 0,
                    alertas=alertas_activas,
                )
                for item in alertas_activas:
                    ciclo_km = item["proximoCambioKm"]
                    ya_enviada = (
                        db.query(AlertaEnviada)
                        .filter(
                            AlertaEnviada.id_moto == moto.id_moto,
                            AlertaEnviada.tipo_mantenimiento == item["tipo"],
                            AlertaEnviada.km_enviado == ciclo_km,
                        )
                        .first()
                    )
                    if not ya_enviada:
                        db.add(
                            AlertaEnviada(
                                id_moto=moto.id_moto,
                                tipo_mantenimiento=item["tipo"],
                                km_enviado=ciclo_km,
                                fecha_envio=datetime.now(),
                            )
                        )
                db.commit()
            except Exception as exc:
                logger.warning(f"Error enviando alerta de mantenimiento para moto {moto.placa}: {exc}")

        return estados

