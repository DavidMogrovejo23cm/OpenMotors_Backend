import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.core.exceptions import EntityNotFoundError
from app.modules.mantenimiento.models import (
    ParametroMantenimiento,
    MantenimientoRealizado,
    AlertaEnviada,
    CitaMantenimiento,
)
from app.shared.email_service import email_service

logger = logging.getLogger("openauto.mantenimiento")


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
    def listar_por_vehiculo(db: Session, id_vehiculo: int) -> List[MantenimientoRealizado]:
        return (
            db.query(MantenimientoRealizado)
            .filter(MantenimientoRealizado.id_vehiculo == id_vehiculo)
            .order_by(MantenimientoRealizado.fecha.desc())
            .all()
        )

    @staticmethod
    def registrar_o_actualizar(
        db: Session, id_vehiculo: int, tipo: str, km_servicio: int
    ) -> MantenimientoRealizado:
        tipo_norm = tipo.strip().upper()
        existente = (
            db.query(MantenimientoRealizado)
            .filter(
                MantenimientoRealizado.id_vehiculo == id_vehiculo,
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
            id_vehiculo=id_vehiculo,
            tipo=tipo_norm,
            km_servicio=km_servicio,
            fecha=datetime.now(),
        )
        db.add(nuevo)
        db.commit()
        db.refresh(nuevo)
        return nuevo

    @staticmethod
    def eliminar_por_vehiculo_y_tipo(db: Session, id_vehiculo: int, tipo: str) -> None:
        tipo_norm = tipo.strip().upper()
        regs = (
            db.query(MantenimientoRealizado)
            .filter(
                MantenimientoRealizado.id_vehiculo == id_vehiculo,
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
        cc_val = cc if cc and cc > 0 else 1600
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
                    ParametroMantenimiento.cc_min <= 1600,
                    ParametroMantenimiento.cc_max >= 1600,
                )
                .all()
            )
        return params

    @staticmethod
    def inicializar_mantenimientos_vehiculo(db: Session, id_vehiculo: int, cc: int, km_actual: int) -> None:
        params = AlertaMantenimientoService.obtener_parametros_para_cc(db, cc)
        for p in params:
            existe = (
                db.query(MantenimientoRealizado)
                .filter(
                    MantenimientoRealizado.id_vehiculo == id_vehiculo,
                    MantenimientoRealizado.tipo == p.tipo_mantenimiento,
                )
                .first()
            )
            if not existe:
                db.add(
                    MantenimientoRealizado(
                        id_vehiculo=id_vehiculo,
                        tipo=p.tipo_mantenimiento,
                        km_servicio=km_actual or 0,
                        fecha=datetime.now(),
                    )
                )
        db.commit()

    @staticmethod
    def calcular_estado(db: Session, vehiculo: Any) -> List[Dict[str, Any]]:
        """
        Calcula el porcentaje de desgaste y el semáforo predictivo según el diagrama:
        - VERDE (<70%): Desgaste normal (Proceso 15.1: Mantener en verde y seguir revisando).
        - AMARILLO (70% a 89%): Alerta preventiva alcanzada (Proceso 16).
        - ROJO (>=90% o vencido): Alerta urgente de reemplazo (Proceso 16).
        """
        km_actual = vehiculo.kilometraje or 0
        cc = vehiculo.cilindraje or 1600

        parametros = AlertaMantenimientoService.obtener_parametros_para_cc(db, cc)
        realizados = MantenimientoService.listar_por_vehiculo(db, vehiculo.id_vehiculo)
        mapa_ultimo_km = {r.tipo.upper(): r.km_servicio for r in realizados}

        estados: List[Dict[str, Any]] = []
        for param in parametros:
            intervalo = param.intervalo_km if param.intervalo_km and param.intervalo_km > 0 else 5000
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
                semaforo = "ROJO"
                km_restante = 0
                porcentaje = 100
                mensaje_semaforo = "Urgente: Intervalo vencido. Requiere reemplazo inmediato."
            elif porcentaje >= 90:
                estado_str = "VENCIDO"
                semaforo = "ROJO"
                mensaje_semaforo = "Crítico: Desgaste superior al 90%. Requiere reemplazo inmediato."
            elif porcentaje >= 70 or km_restante <= 500:
                estado_str = "PROXIMO"
                semaforo = "AMARILLO"
                mensaje_semaforo = "Atención: Desgaste llegó al 70% o más. Se recomienda agendar revisión preventiva (Proceso 16)."
            else:
                estado_str = "OK"
                semaforo = "VERDE"
                mensaje_semaforo = "Desgaste en rango óptimo (<70%). Mantener en verde y seguir revisando (Proceso 15.1)."

            estados.append({
                "tipo": param.tipo_mantenimiento,
                "descripcion": param.descripcion,
                "intervaloKm": intervalo,
                "kmActual": km_actual,
                "proximoCambioKm": proximo_cambio,
                "kmRestante": km_restante,
                "porcentajeDesgaste": porcentaje,
                "estado": estado_str,
                "semaforo": semaforo,
                "mensajeSemaforo": mensaje_semaforo,
                "requiereAviso": porcentaje >= 70,
            })

        return estados

    @staticmethod
    def verificar_y_enviar_alertas(db: Session, vehiculo: Any) -> List[Dict[str, Any]]:
        """
        Proceso 16: Avisar al cliente cuando el desgaste llega al 70% o más (amarillo o rojo).
        """
        estados = AlertaMantenimientoService.calcular_estado(db, vehiculo)
        if not vehiculo.id_usuario:
            return estados

        from app.modules.usuarios.models import Usuario
        dueno = db.query(Usuario).filter(Usuario.id_usuario == vehiculo.id_usuario).first()
        if not dueno or not dueno.correo:
            return estados

        alertas_activas = [e for e in estados if e["porcentajeDesgaste"] >= 70]
        if not alertas_activas:
            return estados

        debe_enviar = False
        for item in alertas_activas:
            ciclo_km = item["proximoCambioKm"]
            ya_enviada = (
                db.query(AlertaEnviada)
                .filter(
                    AlertaEnviada.id_vehiculo == vehiculo.id_vehiculo,
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
                vehiculo_desc = f"{vehiculo.marca} {vehiculo.modelo}"
                email_service.enviar_resumen_mantenimiento(
                    destinatario=dueno.correo,
                    nombre_cliente=dueno.nombre_completo,
                    vehiculo_desc=vehiculo_desc,
                    placa=vehiculo.placa,
                    km_actual=vehiculo.kilometraje or 0,
                    alertas=alertas_activas,
                )
                for item in alertas_activas:
                    ciclo_km = item["proximoCambioKm"]
                    ya_enviada = (
                        db.query(AlertaEnviada)
                        .filter(
                            AlertaEnviada.id_vehiculo == vehiculo.id_vehiculo,
                            AlertaEnviada.tipo_mantenimiento == item["tipo"],
                            AlertaEnviada.km_enviado == ciclo_km,
                        )
                        .first()
                    )
                    if not ya_enviada:
                        db.add(
                            AlertaEnviada(
                                id_vehiculo=vehiculo.id_vehiculo,
                                tipo_mantenimiento=item["tipo"],
                                km_enviado=ciclo_km,
                                fecha_envio=datetime.now(),
                            )
                        )
                db.commit()
            except Exception as exc:
                logger.warning(f"Error enviando alerta de mantenimiento para vehiculo {vehiculo.placa}: {exc}")

        return estados


class CitaMantenimientoService:
    """
    Gestión de citas preventivas agendadas por los avisos de desgaste (Proceso 16).
    """

    @staticmethod
    def agendar_cita(db: Session, payload: Any) -> Dict[str, Any]:
        from app.modules.vehiculos.models import Vehiculo
        from app.modules.usuarios.models import Usuario

        vehiculo = db.query(Vehiculo).filter(Vehiculo.id_vehiculo == payload.id_vehiculo).first()
        if not vehiculo:
            raise EntityNotFoundError("Vehículo", payload.id_vehiculo)

        id_cli = payload.id_usuario or vehiculo.id_usuario
        usuario = db.query(Usuario).filter(Usuario.id_usuario == id_cli).first() if id_cli else None

        try:
            fecha_dt = datetime.fromisoformat(payload.fecha_agendada.replace("Z", "+00:00"))
        except Exception:
            fecha_dt = datetime.now()

        cita = CitaMantenimiento(
            id_vehiculo=payload.id_vehiculo,
            id_usuario=id_cli,
            fecha_agendada=fecha_dt,
            piezas_a_revisar=payload.piezas_a_revisar,
            estado="AGENDADA",
            observaciones=payload.observaciones,
            fecha_registro=datetime.now(),
        )
        db.add(cita)
        db.commit()
        db.refresh(cita)

        return {
            "exito": True,
            "mensaje": f"Cita de mantenimiento preventivo agendada exitosamente para el vehículo placa {vehiculo.placa}.",
            "cita": cita.to_dict(),
        }

    @staticmethod
    def listar_citas(
        db: Session, id_vehiculo: Optional[int] = None, id_usuario: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        query = db.query(CitaMantenimiento)
        if id_vehiculo:
            query = query.filter(CitaMantenimiento.id_vehiculo == id_vehiculo)
        if id_usuario:
            query = query.filter(CitaMantenimiento.id_usuario == id_usuario)

        citas = query.order_by(CitaMantenimiento.fecha_agendada.asc()).all()
        return [c.to_dict() for c in citas]
