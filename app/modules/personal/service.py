"""Lógica de negocio de personal mecánico, horarios, asistencia y reportes de desempeño."""
import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessValidationError, ConflictError, EntityNotFoundError
from app.modules.personal.models import PerfilLaboral, HorarioTrabajo, AsistenciaPersonal
from app.modules.roles.models import Rol, UsuarioRol
from app.modules.sistema.auditoria import registrar_auditoria
from app.modules.taller.models import BitacoraReparacion, DiagnosticoVehiculo, Registro
from app.modules.usuarios.models import Usuario


HHMM_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def _parse_hhmm_minutes(hhmm: str, etiqueta: str) -> int:
    val = (hhmm or "").strip()
    m = HHMM_RE.match(val)
    if not m:
        raise BusinessValidationError(f"La {etiqueta} debe tener formato HH:MM (ej. 08:00)")
    return int(m.group(1)) * 60 + int(m.group(2))


def _parse_date_range(fecha_inicio: Optional[str], fecha_fin: Optional[str]) -> tuple[Optional[date], Optional[date]]:
    fi: Optional[date] = None
    ff: Optional[date] = None
    if fecha_inicio:
        try:
            fi = date.fromisoformat(fecha_inicio[:10])
        except ValueError:
            raise BusinessValidationError("La fecha_inicio debe tener formato AAAA-MM-DD")
    if fecha_fin:
        try:
            ff = date.fromisoformat(fecha_fin[:10])
        except ValueError:
            raise BusinessValidationError("La fecha_fin debe tener formato AAAA-MM-DD")
    if fi and ff and fi > ff:
        raise BusinessValidationError("La fecha de inicio no puede ser mayor que la fecha final")
    return fi, ff


def _asegurar_empleado_taller(db: Session, id_usuario: int) -> Usuario:
    usuario = db.query(Usuario).filter(Usuario.id_usuario == id_usuario).first()
    if not usuario:
        raise EntityNotFoundError("Empleado", id_usuario)
    es_personal = any(
        link.estado == 1 and link.rol and link.rol.nombre.upper() in ("MECANICO", "ADMIN")
        for link in (usuario.roles or [])
    )
    if not es_personal:
        raise BusinessValidationError("El usuario seleccionado no pertenece al personal del taller")
    return usuario


class PersonalService:
    # ------------------------------------------
    # PERFIL LABORAL (RF-40 / HU-50)
    # ------------------------------------------
    @staticmethod
    def listar_personal_con_perfil(db: Session) -> List[Dict[str, Any]]:
        empleados = (
            db.query(Usuario)
            .join(UsuarioRol, Usuario.id_usuario == UsuarioRol.id_usuario)
            .join(Rol, UsuarioRol.id_rol == Rol.id_rol)
            .filter(UsuarioRol.estado == 1, func.upper(Rol.nombre).in_(["MECANICO", "ADMIN"]))
            .distinct()
            .order_by(Usuario.nombre_completo.asc())
            .all()
        )
        perfiles = {p.id_usuario: p for p in db.query(PerfilLaboral).all()}
        res = []
        for u in empleados:
            p = perfiles.get(u.id_usuario)
            roles_activos = [
                r.rol.nombre for r in (u.roles or []) if r.estado == 1 and r.rol and r.rol.nombre
            ]
            res.append({
                "id_usuario": u.id_usuario,
                "nombre_completo": u.nombre_completo,
                "nombre_usuario": u.nombre_usuario,
                "correo": u.correo,
                "telefono": u.telefono,
                "cedula": u.cedula,
                "activo": bool(u.activo if u.activo is not None else True),
                "roles": roles_activos,
                "perfil_laboral": p.to_dict() if p else None,
            })
        return res

    @staticmethod
    def obtener_perfil(db: Session, id_usuario: int) -> Dict[str, Any]:
        usuario = _asegurar_empleado_taller(db, id_usuario)
        perfil = db.query(PerfilLaboral).filter(PerfilLaboral.id_usuario == id_usuario).first()
        return {
            "id_usuario": usuario.id_usuario,
            "nombre_completo": usuario.nombre_completo,
            "perfil_laboral": perfil.to_dict() if perfil else None,
        }

    @staticmethod
    def guardar_perfil(db: Session, id_usuario: int, payload: Any, actor_id: int) -> Dict[str, Any]:
        _asegurar_empleado_taller(db, id_usuario)
        fecha_ing: Optional[date] = None
        if payload.fecha_ingreso:
            try:
                fecha_ing = date.fromisoformat(str(payload.fecha_ingreso)[:10])
            except ValueError:
                raise BusinessValidationError("La fecha_ingreso debe tener formato AAAA-MM-DD")

        perfil = db.query(PerfilLaboral).filter(PerfilLaboral.id_usuario == id_usuario).first()
        if not perfil:
            perfil = PerfilLaboral(id_usuario=id_usuario)
            db.add(perfil)

        perfil.cargo = payload.cargo.strip()
        perfil.especialidad = payload.especialidad.strip() if payload.especialidad else None
        perfil.fecha_ingreso = fecha_ing
        perfil.tipo_contrato = payload.tipo_contrato.strip() if payload.tipo_contrato else "TIEMPO_COMPLETO"
        perfil.modalidad_pago = payload.modalidad_pago
        perfil.tarifa_hora = round(float(payload.tarifa_hora or 0.0), 2)
        perfil.salario_base = round(float(payload.salario_base or 0.0), 2)
        perfil.contacto_emergencia = payload.contacto_emergencia.strip() if payload.contacto_emergencia else None
        perfil.observaciones = payload.observaciones.strip() if payload.observaciones else None
        perfil.actualizado_en = datetime.now()

        db.flush()
        registrar_auditoria(
            db,
            actor_id,
            "PERSONAL_PERFIL_ACTUALIZADO",
            "PerfilLaboral",
            perfil.id_perfil,
            f"Ficha laboral actualizada para usuario #{id_usuario} ({perfil.cargo} / {perfil.modalidad_pago})",
        )
        db.commit()
        db.refresh(perfil)
        return perfil.to_dict()

    # ------------------------------------------
    # HORARIOS DE TRABAJO (RF-41 / HU-51)
    # ------------------------------------------
    @staticmethod
    def listar_horarios(db: Session, id_usuario: Optional[int] = None) -> List[Dict[str, Any]]:
        q = db.query(HorarioTrabajo)
        if id_usuario is not None:
            q = q.filter(HorarioTrabajo.id_usuario == id_usuario)
        rows = q.order_by(HorarioTrabajo.id_usuario.asc(), HorarioTrabajo.dia_semana.asc()).all()
        return [r.to_dict() for r in rows]

    @staticmethod
    def guardar_horarios(db: Session, id_usuario: int, dias: List[Any], actor_id: int) -> List[Dict[str, Any]]:
        _asegurar_empleado_taller(db, id_usuario)
        seen_days = set()
        validated_items = []
        for d in dias:
            if d.dia_semana in seen_days:
                raise BusinessValidationError(f"Día repetido en el horario: {d.dia_semana}")
            seen_days.add(d.dia_semana)
            if d.es_laborable:
                m_in = _parse_hhmm_minutes(d.hora_entrada, "hora de entrada")
                m_out = _parse_hhmm_minutes(d.hora_salida, "hora de salida")
                if m_out <= m_in:
                    raise BusinessValidationError("La hora de salida debe ser posterior a la hora de entrada")
                duracion = m_out - m_in
                if d.minutos_descanso < 0 or d.minutos_descanso >= duracion:
                    raise BusinessValidationError("Los minutos de descanso deben ser menores a la duración del turno")
            validated_items.append(d)

        for d in validated_items:
            row = (
                db.query(HorarioTrabajo)
                .filter(HorarioTrabajo.id_usuario == id_usuario, HorarioTrabajo.dia_semana == d.dia_semana)
                .first()
            )
            if not row:
                row = HorarioTrabajo(id_usuario=id_usuario, dia_semana=d.dia_semana)
                db.add(row)
            row.es_laborable = bool(d.es_laborable)
            row.hora_entrada = d.hora_entrada if d.es_laborable else "00:00"
            row.hora_salida = d.hora_salida if d.es_laborable else "00:00"
            row.minutos_descanso = int(d.minutos_descanso if d.es_laborable else 0)
            row.turno = (d.turno or "DIURNO").strip()[:40]

        registrar_auditoria(
            db,
            actor_id,
            "PERSONAL_HORARIO_ACTUALIZADO",
            "HorarioTrabajo",
            id_usuario,
            f"Horario semanal actualizado para empleado #{id_usuario} ({len(validated_items)} día(s))",
        )
        db.commit()
        return PersonalService.listar_horarios(db, id_usuario=id_usuario)

    # ------------------------------------------
    # ASISTENCIA Y HORAS TRABAJADAS (RF-42 / HU-52)
    # ------------------------------------------
    @staticmethod
    def _calcular_horas_asistencia(
        estado: str,
        hora_entrada: Optional[str],
        hora_salida: Optional[str],
        minutos_descanso: int,
        horas_manual: Optional[float],
    ) -> float:
        if estado in ("FALTA", "PERMISO", "DESCANSO"):
            return 0.0
        if hora_entrada and hora_salida:
            m_in = _parse_hhmm_minutes(hora_entrada, "hora de entrada")
            m_out = _parse_hhmm_minutes(hora_salida, "hora de salida")
            if m_out <= m_in:
                raise BusinessValidationError("La hora de salida debe ser posterior a la hora de entrada")
            net_min = (m_out - m_in) - int(minutos_descanso or 0)
            if net_min <= 0:
                raise BusinessValidationError("El tiempo de descanso no puede igualar o superar la jornada")
            horas = round(net_min / 60.0, 2)
            if horas > 24.0:
                raise BusinessValidationError("Las horas trabajadas del día no pueden superar 24 horas")
            return horas
        if horas_manual is not None:
            val = round(float(horas_manual), 2)
            if val < 0 or val > 24:
                raise BusinessValidationError("Las horas trabajadas deben estar entre 0 y 24")
            return val
        raise BusinessValidationError("Ingresa hora de entrada y salida o el total de horas trabajadas")

    @staticmethod
    def registrar_asistencia(db: Session, payload: Any, actor_id: int) -> Dict[str, Any]:
        _asegurar_empleado_taller(db, payload.id_usuario)
        fecha_asist = date.today()
        if payload.fecha:
            try:
                fecha_asist = date.fromisoformat(str(payload.fecha)[:10])
            except ValueError:
                raise BusinessValidationError("La fecha debe tener formato AAAA-MM-DD")

        turno_norm = (payload.turno or "UNICO").strip().upper()
        existente = (
            db.query(AsistenciaPersonal)
            .filter(
                AsistenciaPersonal.id_usuario == payload.id_usuario,
                AsistenciaPersonal.fecha == fecha_asist,
                func.upper(AsistenciaPersonal.turno) == turno_norm,
            )
            .first()
        )
        if existente:
            raise ConflictError("Ya existe un registro de asistencia para este mecánico en la misma fecha y turno")

        horas = PersonalService._calcular_horas_asistencia(
            payload.estado,
            payload.hora_entrada,
            payload.hora_salida,
            payload.minutos_descanso,
            payload.horas_trabajadas,
        )

        reg = AsistenciaPersonal(
            id_usuario=payload.id_usuario,
            fecha=fecha_asist,
            turno=turno_norm,
            estado=payload.estado,
            hora_entrada=payload.hora_entrada,
            hora_salida=payload.hora_salida,
            minutos_descanso=int(payload.minutos_descanso or 0),
            horas_trabajadas=horas,
            observaciones=payload.observaciones.strip() if payload.observaciones else None,
            registrado_por=actor_id,
            actualizado_en=datetime.now(),
        )
        db.add(reg)
        db.flush()
        registrar_auditoria(
            db,
            actor_id,
            "PERSONAL_ASISTENCIA_CREADA",
            "AsistenciaPersonal",
            reg.id_asistencia,
            f"Asistencia {reg.estado} ({reg.horas_trabajadas} h) registrada para empleado #{reg.id_usuario} el {reg.fecha.isoformat()}",
        )
        db.commit()
        db.refresh(reg)
        return reg.to_dict()

    @staticmethod
    def actualizar_asistencia(db: Session, id_asistencia: int, payload: Any, actor_id: int) -> Dict[str, Any]:
        reg = db.query(AsistenciaPersonal).filter(AsistenciaPersonal.id_asistencia == id_asistencia).first()
        if not reg:
            raise EntityNotFoundError("Asistencia", id_asistencia)

        nuevo_estado = payload.estado or reg.estado
        nueva_ent = payload.hora_entrada if payload.hora_entrada is not None else reg.hora_entrada
        nueva_sal = payload.hora_salida if payload.hora_salida is not None else reg.hora_salida
        nuevo_desc = payload.minutos_descanso if payload.minutos_descanso is not None else reg.minutos_descanso
        nuevas_horas_manual = payload.horas_trabajadas if payload.horas_trabajadas is not None else (
            None if (nueva_ent and nueva_sal) else reg.horas_trabajadas
        )

        horas = PersonalService._calcular_horas_asistencia(
            nuevo_estado, nueva_ent, nueva_sal, nuevo_desc, nuevas_horas_manual
        )
        reg.estado = nuevo_estado
        reg.hora_entrada = nueva_ent
        reg.hora_salida = nueva_sal
        reg.minutos_descanso = int(nuevo_desc or 0)
        reg.horas_trabajadas = horas
        if payload.observaciones is not None:
            reg.observaciones = payload.observaciones.strip() or None
        reg.actualizado_en = datetime.now()

        registrar_auditoria(
            db,
            actor_id,
            "PERSONAL_ASISTENCIA_EDITADA",
            "AsistenciaPersonal",
            reg.id_asistencia,
            f"Asistencia #{reg.id_asistencia} corregida a {reg.estado} ({reg.horas_trabajadas} h)",
        )
        db.commit()
        db.refresh(reg)
        return reg.to_dict()

    @staticmethod
    def listar_asistencia(
        db: Session,
        fecha_inicio: Optional[str] = None,
        fecha_fin: Optional[str] = None,
        id_usuario: Optional[int] = None,
    ) -> Dict[str, Any]:
        fi, ff = _parse_date_range(fecha_inicio, fecha_fin)
        q = db.query(AsistenciaPersonal)
        if fi:
            q = q.filter(AsistenciaPersonal.fecha >= fi)
        if ff:
            q = q.filter(AsistenciaPersonal.fecha <= ff)
        if id_usuario is not None:
            q = q.filter(AsistenciaPersonal.id_usuario == id_usuario)

        rows = q.order_by(AsistenciaPersonal.fecha.desc(), AsistenciaPersonal.id_asistencia.desc()).all()
        items = [r.to_dict() for r in rows]

        total_horas = round(sum(float(r.horas_trabajadas or 0.0) for r in rows), 2)
        conteo = {"PRESENTE": 0, "TARDANZA": 0, "FALTA": 0, "PERMISO": 0, "DESCANSO": 0}
        por_empleado: Dict[int, Dict[str, Any]] = {}

        for r in rows:
            conteo[r.estado] = conteo.get(r.estado, 0) + 1
            emp = por_empleado.setdefault(
                r.id_usuario,
                {
                    "id_usuario": r.id_usuario,
                    "nombre_empleado": r.usuario.nombre_completo if r.usuario else f"Empleado #{r.id_usuario}",
                    "horas_trabajadas": 0.0,
                    "dias_presentes": 0,
                    "tardanzas": 0,
                    "faltas": 0,
                    "permisos": 0,
                },
            )
            emp["horas_trabajadas"] = round(emp["horas_trabajadas"] + float(r.horas_trabajadas or 0.0), 2)
            if r.estado == "PRESENTE":
                emp["dias_presentes"] += 1
            elif r.estado == "TARDANZA":
                emp["tardanzas"] += 1
                emp["dias_presentes"] += 1
            elif r.estado == "FALTA":
                emp["faltas"] += 1
            elif r.estado == "PERMISO":
                emp["permisos"] += 1

        return {
            "resumen": {
                "total_registros": len(items),
                "total_horas_trabajadas": total_horas,
                "conteo_estados": conteo,
                "por_empleado": list(por_empleado.values()),
            },
            "items": items,
        }

    # ------------------------------------------
    # REPORTE DE DESEMPEÑO DE MECÁNICOS (RF-58 / HU-69)
    # ------------------------------------------
    @staticmethod
    def reporte_desempeno(
        db: Session,
        fecha_inicio: Optional[str] = None,
        fecha_fin: Optional[str] = None,
        id_mecanico: Optional[int] = None,
    ) -> Dict[str, Any]:
        fi, ff = _parse_date_range(fecha_inicio, fecha_fin)

        mecs_q = (
            db.query(Usuario)
            .join(UsuarioRol, Usuario.id_usuario == UsuarioRol.id_usuario)
            .join(Rol, UsuarioRol.id_rol == Rol.id_rol)
            .filter(UsuarioRol.estado == 1, func.upper(Rol.nombre) == "MECANICO")
            .distinct()
        )
        if id_mecanico is not None:
            mecs_q = mecs_q.filter(Usuario.id_usuario == id_mecanico)
        mecanicos = mecs_q.order_by(Usuario.nombre_completo.asc()).all()

        resultados = []
        totales = {
            "ordenes_asignadas": 0,
            "ordenes_completadas": 0,
            "horas_taller": 0.0,
            "horas_asistencia": 0.0,
            "diagnosticos_realizados": 0,
        }

        for mec in mecanicos:
            reg_q = db.query(Registro).filter(Registro.id_encargado == mec.id_usuario)
            if fi:
                reg_q = reg_q.filter(Registro.fecha >= fi)
            if ff:
                reg_q = reg_q.filter(Registro.fecha <= ff)
            ordenes = reg_q.all()

            asignadas = len(ordenes)
            completadas = sum(1 for o in ordenes if o.estado in (2, 3))
            en_proceso = sum(1 for o in ordenes if o.estado == 1)
            pendientes = sum(1 for o in ordenes if o.estado == 0)

            con_plazo = [o for o in ordenes if o.fecha_entrega_estimada and o.estado in (2, 3)]
            a_tiempo = 0
            for o in con_plazo:
                fin_real = o.fecha_completado or o.fecha_entregado
                if fin_real and fin_real <= o.fecha_entrega_estimada:
                    a_tiempo += 1
            cumplimiento_pct = round((a_tiempo / len(con_plazo)) * 100, 1) if con_plazo else None

            bit_q = db.query(BitacoraReparacion).filter(BitacoraReparacion.id_mecanico == mec.id_usuario)
            if fi:
                bit_q = bit_q.filter(BitacoraReparacion.fecha >= datetime.combine(fi, datetime.min.time()))
            if ff:
                bit_q = bit_q.filter(BitacoraReparacion.fecha <= datetime.combine(ff, datetime.max.time()))
            bitacoras = bit_q.all()
            horas_taller = round(sum(float(b.horas_trabajadas or 0.0) for b in bitacoras), 2)

            diag_q = db.query(DiagnosticoVehiculo).filter(DiagnosticoVehiculo.id_mecanico == mec.id_usuario)
            if fi:
                diag_q = diag_q.filter(DiagnosticoVehiculo.fecha >= datetime.combine(fi, datetime.min.time()))
            if ff:
                diag_q = diag_q.filter(DiagnosticoVehiculo.fecha <= datetime.combine(ff, datetime.max.time()))
            diags_count = diag_q.count()

            asist_q = db.query(AsistenciaPersonal).filter(AsistenciaPersonal.id_usuario == mec.id_usuario)
            if fi:
                asist_q = asist_q.filter(AsistenciaPersonal.fecha >= fi)
            if ff:
                asist_q = asist_q.filter(AsistenciaPersonal.fecha <= ff)
            horas_asist = round(sum(float(a.horas_trabajadas or 0.0) for a in asist_q.all()), 2)

            totales["ordenes_asignadas"] += asignadas
            totales["ordenes_completadas"] += completadas
            totales["horas_taller"] = round(totales["horas_taller"] + horas_taller, 2)
            totales["horas_asistencia"] = round(totales["horas_asistencia"] + horas_asist, 2)
            totales["diagnosticos_realizados"] += diags_count

            resultados.append({
                "id_mecanico": mec.id_usuario,
                "nombre_mecanico": mec.nombre_completo,
                "ordenes_asignadas": asignadas,
                "ordenes_completadas": completadas,
                "ordenes_en_proceso": en_proceso,
                "ordenes_pendientes": pendientes,
                "tasa_finalizacion": round((completadas / asignadas) * 100, 1) if asignadas > 0 else 0.0,
                "cumplimiento_plazos_pct": cumplimiento_pct,
                "horas_taller": horas_taller,
                "horas_asistencia": horas_asist,
                "diagnosticos_realizados": diags_count,
                "trabajos_registrados": len(bitacoras),
                "detalle_actividades": [
                    {
                        "id_bitacora": b.id_bitacora,
                        "id_registro": b.id_registro,
                        "fecha": b.fecha.isoformat() if b.fecha else None,
                        "horas_trabajadas": round(float(b.horas_trabajadas or 0.0), 2),
                        "descripcion_trabajo": b.descripcion_trabajo,
                    }
                    for b in bitacoras[-10:]
                ],
            })

        return {
            "filtros": {
                "fecha_inicio": fi.isoformat() if fi else None,
                "fecha_fin": ff.isoformat() if ff else None,
                "id_mecanico": id_mecanico,
            },
            "resumen": totales,
            "mecanicos": resultados,
        }
