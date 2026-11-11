import html
import logging
import re
import smtplib
import urllib.parse
import uuid
from datetime import date, datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional
import requests
from app.core.config import settings

logger = logging.getLogger("openauto.email")

RESEND_URL = "https://api.resend.com/emails"
SENDGRID_URL = "https://api.sendgrid.com/v3/mail/send"
BREVO_URL = "https://api.brevo.com/v3/smtp/email"
LOGO_URL = "https://backend-openmotors.onrender.com/images/gorila-logo.png"
PORTAL_URL = "https://openmotor.vercel.app"
WHATSAPP_CITAS = "593980834367"


class ItemMantenimiento:
    def __init__(
        self,
        tipo: str,
        descripcion: str,
        porcentaje: int,
        km_restante: int,
        estado: str,
    ):
        self.tipo = tipo
        self.descripcion = descripcion
        self.porcentaje = porcentaje
        self.kmRestante = km_restante
        self.estado = estado


class EmailService:
    """
    Servicio unificado de correo electrónico con cadena de respaldo automática:
    1) Brevo HTTP API
    2) SendGrid HTTP API
    3) Gmail SMTP (STARTTLS)
    4) Resend HTTP API
    """

    def enviar(self, to: str, subject: str, html_body: str) -> bool:
        if not to or not to.strip() or to.strip().endswith("@openauto.local"):
            return False
        to = to.strip()
        sender_email = (
            settings.MAIL_USERNAME.strip()
            if settings.MAIL_USERNAME and settings.MAIL_USERNAME.strip()
            else "info@openmotor.com"
        )
        from_name = settings.MAIL_FROM_NAME or "Open Auto"

        # 1) Brevo HTTP API
        if settings.BREVO_API_KEY and settings.BREVO_API_KEY.strip():
            try:
                res = requests.post(
                    BREVO_URL,
                    headers={
                        "Content-Type": "application/json",
                        "api-key": settings.BREVO_API_KEY.strip(),
                    },
                    json={
                        "sender": {"email": sender_email, "name": from_name},
                        "to": [{"email": to}],
                        "subject": subject,
                        "htmlContent": html_body,
                    },
                    timeout=12,
                )
                if 200 <= res.status_code < 300:
                    logger.info("[EMAIL] (Brevo) Enviado a %s — status %s", to, res.status_code)
                    return True
                logger.warning("[EMAIL] (Brevo) Falló (%s): %s", res.status_code, res.text)
            except Exception as exc:
                logger.warning("[EMAIL] (Brevo) Excepción enviando a %s: %s", to, exc)

        # 2) SendGrid HTTP API
        if settings.SENDGRID_API_KEY and settings.SENDGRID_API_KEY.strip():
            try:
                res = requests.post(
                    SENDGRID_URL,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {settings.SENDGRID_API_KEY.strip()}",
                    },
                    json={
                        "personalizations": [{"to": [{"email": to}]}],
                        "from": {"email": sender_email, "name": from_name},
                        "subject": subject,
                        "content": [{"type": "text/html", "value": html_body}],
                    },
                    timeout=12,
                )
                if 200 <= res.status_code < 300:
                    logger.info("[EMAIL] (SendGrid) Enviado a %s — status %s", to, res.status_code)
                    return True
                logger.warning("[EMAIL] (SendGrid) Falló (%s): %s", res.status_code, res.text)
            except Exception as exc:
                logger.warning("[EMAIL] (SendGrid) Excepción enviando a %s: %s", to, exc)

        # 3) Gmail SMTP
        if settings.MAIL_USERNAME and settings.MAIL_USERNAME.strip() and settings.MAIL_PASSWORD:
            try:
                clean_password = re.sub(r"\s+", "", settings.MAIL_PASSWORD)
                msg = MIMEMultipart("alternative")
                msg["Subject"] = subject
                msg["From"] = f"{from_name} <{settings.MAIL_USERNAME.strip()}>"
                msg["To"] = to
                msg.attach(MIMEText(html_body, "html", "utf-8"))

                with smtplib.SMTP(settings.MAIL_HOST, settings.MAIL_PORT, timeout=10) as server:
                    server.starttls()
                    server.login(settings.MAIL_USERNAME.strip(), clean_password)
                    server.sendmail(settings.MAIL_USERNAME.strip(), [to], msg.as_string())
                logger.info("[EMAIL] (SMTP) Enviado a %s", to)
                return True
            except Exception as exc:
                logger.warning("[EMAIL] (SMTP) Error enviando a %s: %s", to, exc)

        # 4) Resend HTTP API
        if settings.RESEND_API_KEY and settings.RESEND_API_KEY.strip():
            try:
                res = requests.post(
                    RESEND_URL,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {settings.RESEND_API_KEY.strip()}",
                    },
                    json={
                        "from": f"{from_name} <{settings.RESEND_FROM_EMAIL}>",
                        "to": to,
                        "subject": subject,
                        "html": html_body,
                    },
                    timeout=12,
                )
                if 200 <= res.status_code < 300:
                    logger.info("[EMAIL] (Resend) Enviado a %s — status %s", to, res.status_code)
                    return True
                logger.warning("[EMAIL] (Resend) Falló (%s): %s", res.status_code, res.text)
            except Exception as exc:
                logger.warning("[EMAIL] (Resend) Excepción enviando a %s: %s", to, exc)

        logger.info("[EMAIL] Sin proveedor activo o envío fallido para: %s", to)
        return False

    # ── 1. Recuperación de contraseña ─────────────────────────────────────────
    def enviar_email_recuperacion(
        self, correo: str, token: str, nombre: str, plataforma: str = "web"
    ) -> bool:
        enlace = (
            f"{PORTAL_URL}/restablecer?token={token}"
            if (plataforma or "").lower() == "web"
            else f"openauto://reset-password?token={token}"
        )
        html_body = self._html_base(
            "Recupera tu contraseña",
            f"Hola <strong>{self._esc(nombre)}</strong>, recibimos una solicitud para restablecer tu contraseña.",
            "Restablecer contraseña",
            enlace,
            "Este enlace expira en 1 hora. Si no solicitaste esto, ignora este correo.",
        )
        return self.enviar(correo, "Restablecer contraseña — Open Auto", html_body)

    # ── 2. Bienvenida ─────────────────────────────────────────────────────────
    def enviar_bienvenida(self, correo: str, nombre: str) -> bool:
        html_body = self._html_base(
            "¡Bienvenido a Open Auto!",
            f"Hola <strong>{self._esc(nombre)}</strong>, tu cuenta ha sido creada exitosamente. "
            "Ya puedes registrar tus vehiculos, ver tu historial de servicios y acumular puntos de fidelidad.",
            "Ir al portal",
            PORTAL_URL,
            "Ante cualquier consulta, escríbenos a info@openmotor.com",
        )
        return self.enviar(correo, "Bienvenido a Open Auto 🚗", html_body)

    # ── 3. Prueba de correo ───────────────────────────────────────────────────
    def enviar_email_prueba(self, destino: str) -> bool:
        html_body = self._html_base(
            "Prueba de Correo — Open Auto",
            "Este correo confirma que el servidor de correo en Python <strong>está funcionando correctamente</strong>.",
            "Ver portal",
            PORTAL_URL,
            "Si recibiste este mensaje, el servicio de notificaciones está activo y configurado.",
        )
        return self.enviar(
            destino,
            f"✓ Prueba Email — Open Auto ({datetime.now().isoformat(timespec='seconds')})",
            html_body,
        )

    # ── 4. Ofertas / Marketing ────────────────────────────────────────────────
    def enviar_oferta_marketing(self, correo: str, asunto: str, mensaje: str) -> bool:
        formatted = (mensaje or "").replace("\n", "<br>")
        yr = date.today().year
        html_body = (
            "<!DOCTYPE html><html><head><meta charset='UTF-8'></head><body style='"
            "margin:0;padding:0;background:#F4F4F5;font-family:Arial,sans-serif'>"
            "<table width='100%' cellpadding='0' cellspacing='0'><tr><td align='center' style='padding:40px 16px'>"
            "<table width='560' cellpadding='0' cellspacing='0' style='background:#fff;border-radius:16px;"
            "overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08)'>"
            "<tr><td style='background:#E11428;height:5px;font-size:1px'>&nbsp;</td></tr>"
            "<tr><td style='background:#0C0C10;padding:24px 36px'>"
            "<table width='100%' cellpadding='0' cellspacing='0'><tr>"
            "<td><p style='margin:0;color:#fff;font-size:22px;font-weight:900;letter-spacing:-0.5px'>"
            "Gorila <span style='color:#E11428'>Vehiculos</span></p>"
            "<p style='margin:4px 0 0;color:rgba(255,255,255,0.35);font-size:10px;letter-spacing:2px;text-transform:uppercase'>Taller Mecánico · Cuenca, Ecuador</p>"
            "</td>"
            "<td align='right'><span style='background:rgba(225,20,40,0.15);color:#E11428;font-size:9px;font-weight:800;"
            "letter-spacing:2px;text-transform:uppercase;padding:6px 12px;border-radius:8px;border:1px solid rgba(225,20,40,0.3)'>Oferta exclusiva</span></td>"
            "</tr></table></td></tr>"
            f"<tr><td style='padding:32px 36px 8px'><h2 style='margin:0 0 16px;color:#111;font-size:22px;font-weight:900'>{self._esc(asunto)}</h2></td></tr>"
            f"<tr><td style='padding:0 36px 28px'><div style='color:#444;font-size:15px;line-height:1.7'>{formatted}</div></td></tr>"
            f"<tr><td style='padding:0 36px 32px'><a href='{PORTAL_URL}' style='display:inline-block;background:#E11428;color:#fff;"
            "text-decoration:none;padding:13px 28px;border-radius:10px;font-weight:700;font-size:14px'>Ver portal Open Auto →</a></td></tr>"
            "<tr><td style='height:1px;background:#F0F0F2'></td></tr>"
            f"<tr><td style='background:#F9F9FB;padding:20px 36px'><p style='margin:0;color:#aaa;font-size:11px'>© {yr} Open Auto · Cuenca, Ecuador</p></td></tr>"
            "<tr><td style='background:#E11428;height:4px;font-size:1px'>&nbsp;</td></tr>"
            "</table></td></tr></table></body></html>"
        )
        return self.enviar(correo, f"{asunto} — Open Auto", html_body)

    # ── 5. Resumen de Mantenimiento (Alertas por Km) ──────────────────────────
    def enviar_resumen_mantenimiento(
        self,
        correo: str = "",
        nombre: str = "",
        placa: str = "",
        marca: str = "",
        modelo: str = "",
        km_actual: int = 0,
        items: Optional[List[Any]] = None,
        *,
        destinatario: Optional[str] = None,
        nombre_cliente: Optional[str] = None,
        vehiculo_desc: Optional[str] = None,
        alertas: Optional[List[Dict[str, Any]]] = None,
    ) -> bool:
        correo = destinatario or correo
        nombre = nombre_cliente or nombre
        if vehiculo_desc and not marca:
            partes = vehiculo_desc.split(" ", 1)
            marca = partes[0]
            modelo = partes[1] if len(partes) > 1 else ""
        if alertas and not items:
            items = [
                ItemMantenimiento(
                    tipo=a.get("tipo", ""),
                    descripcion=a.get("descripcion", ""),
                    porcentaje=int(a.get("porcentajeDesgaste", 0)),
                    km_restante=int(a.get("kmRestante", 0)),
                    estado=a.get("estado", "OK"),
                )
                for a in alertas
            ]
        if not correo or not items:
            return False
        sorted_items = sorted(items, key=lambda x: x.porcentaje, reverse=True)
        vencidos = sum(1 for i in sorted_items if i.estado == "VENCIDO")
        proximos = sum(1 for i in sorted_items if i.estado == "PROXIMO")

        filas = []
        for it in sorted_items:
            ven = it.estado == "VENCIDO"
            pro = it.estado == "PROXIMO"
            color = "#E11428" if ven else ("#F59E0B" if pro else "#10B981")
            estado_txt = "CAMBIAR YA" if ven else ("PRÓXIMO" if pro else "AL DÍA")
            pct = min(100, max(0, it.porcentaje))
            detalle = "Excedido" if ven else f"Faltan {max(0, it.kmRestante):,d} km"
            filas.append(
                f"<tr><td style='padding:12px;border-bottom:1px solid #1F1F2E;font-size:13px;color:#EAEAEA;font-weight:600'>"
                f"{self._tipo_label(it.tipo)}<br><span style='font-size:10.5px;color:#9CA3AF;font-weight:400'>{detalle}</span></td>"
                f"<td style='padding:12px;border-bottom:1px solid #1F1F2E;width:46%'>"
                f"<div style='background:#1F1F2E;border-radius:99px;height:8px;overflow:hidden'>"
                f"<div style='background:{color};width:{pct}%;height:8px'></div></div>"
                f"<div style='text-align:right;font-size:11px;font-weight:800;color:{color};margin-top:4px'>{it.porcentaje}%</div></td>"
                f"<td style='padding:12px;border-bottom:1px solid #1F1F2E;text-align:right'>"
                f"<span style='font-size:10px;font-weight:800;color:{color};padding:4px 9px;border-radius:6px'>{estado_txt}</span></td></tr>"
            )

        resumen = (
            f"{vencidos} componente(s) por cambiar" + (f" y {proximos} por vencer." if proximos > 0 else ".")
            if vencidos > 0
            else (f"{proximos} componente(s) próximos a vencer." if proximos > 0 else "Todo en orden.")
        )
        wa_msg = urllib.parse.quote(
            f"¡Hola Open Auto! Quiero agendar una cita para mi vehiculo {marca} {modelo} (placa {placa}). Kilometraje: {km_actual:,d} km."
        )
        wa_link = f"https://wa.me/{WHATSAPP_CITAS}?text={wa_msg}"
        yr = date.today().year

        html_body = (
            "<!DOCTYPE html><html lang='es'><head><meta charset='UTF-8'></head>"
            "<body style='margin:0;padding:0;background:#050505;font-family:Arial,sans-serif;color:#fff'>"
            "<div style='padding:40px 16px'><div style='max-width:600px;margin:0 auto;background:#0A0A0E;border:1px solid #1A1A24;border-radius:12px;overflow:hidden'>"
            "<div style='background:#15151D;padding:30px 40px;border-bottom:1px solid rgba(225,20,40,0.2)'>"
            "<h1 style='margin:0;font-size:28px;font-weight:900;color:#fff'>GORILA <span style='color:#E11428'>VEHÍCULOS</span></h1>"
            "<p style='margin:5px 0 0;color:#8B8FA8;font-size:12px;letter-spacing:3px;text-transform:uppercase'>Alerta de Mantenimiento</p></div>"
            "<div style='padding:40px'>"
            f"<h2 style='margin:0 0 20px;font-size:22px;font-weight:800;color:#fff'>{'⚠️ ' if vencidos > 0 else ''}Tu vehiculo necesita mantenimiento</h2>"
            f"<p style='color:#A1A5B5;font-size:15px;line-height:1.6'>Saludos <strong>{self._esc(nombre)}</strong>, tu <strong>{self._esc(marca)} {self._esc(modelo)}</strong> "
            f"(placa <strong>{self._esc(placa)}</strong>) con <strong>{km_actual:,d} km</strong> registra el siguiente estado técnico:</p>"
            "<div style='background:#111118;border:1px solid #1F1F2E;border-radius:10px;padding:20px;margin:20px 0'>"
            f"<p style='margin:0 0 15px;color:#EAEAEA;font-weight:700'>{resumen}</p>"
            "<table width='100%' cellpadding='0' cellspacing='0' style='border-collapse:collapse'>"
            + "".join(filas)
            + "</table></div>"
            f"<div style='text-align:center;margin:32px 0 12px'><a href='{wa_link}' style='display:inline-block;background:#E11428;color:#fff;text-decoration:none;padding:14px 32px;border-radius:8px;font-weight:800'>Agendar Cita Ahora</a></div>"
            f"</div><div style='background:#08080C;padding:20px 40px;text-align:center'><p style='margin:0;color:#666;font-size:12px'>© {yr} Open Auto</p></div></div></div></body></html>"
        )
        asunto = f"{'⚠️ ' if vencidos > 0 else ''}Mantenimiento requerido: {placa} — Open Auto"
        return self.enviar(correo, asunto, html_body)

    # ── 6. Diagnóstico mecánico ───────────────────────────────────────────────
    def enviar_diagnostico(
        self,
        correo: str,
        nombre: str,
        placa: str,
        marca: str,
        modelo: str,
        km_ingreso: int,
        observaciones: Optional[str],
        detalles: List[Any],
    ) -> bool:
        if not correo:
            return False
        malos = 0
        regulares = 0
        filas = []
        for d in detalles or []:
            est = getattr(d, "estado", None) or (d.get("estado") if isinstance(d, dict) else 1) or 1
            parte = getattr(d, "parte", None) or (d.get("parte") if isinstance(d, dict) else "Componente")
            obs = getattr(d, "observacion", None) or (d.get("observacion") if isinstance(d, dict) else None)
            if est >= 3:
                malos += 1
            elif est == 2:
                regulares += 1
            if est >= 2:
                malo = est >= 3
                est_label = "MALO — requiere cambio/reparación" if malo else "REGULAR — vigilar"
                color = "#E11428" if malo else "#F59E0B"
                obs_html = f"<br><span style='font-size:11px;color:#9CA3AF'>{self._esc(obs)}</span>" if obs else ""
                filas.append(
                    f"<tr><td style='padding:10px;border-bottom:1px solid #f3f3f3;font-size:13px;color:#111;font-weight:600'>{self._esc(parte)}{obs_html}</td>"
                    f"<td style='padding:10px;border-bottom:1px solid #f3f3f3'><span style='font-size:11px;font-weight:700;color:{color}'>{est_label}</span></td></tr>"
                )

        critico = malos > 0
        titulo = (
            "Tu vehiculo necesita atención"
            if critico
            else ("Revisión con observaciones" if regulares > 0 else "Tu vehiculo está en buen estado")
        )
        acento = "#E11428" if critico else ("#F59E0B" if regulares > 0 else "#10B981")
        resumen = (
            f"{malos} punto(s) en estado CRÍTICO" + (f" y {regulares} a vigilar." if regulares > 0 else ".")
            if critico
            else (
                f"{regulares} punto(s) a vigilar — nada crítico."
                if regulares > 0
                else "Todos los puntos revisados están en buen estado. ¡Listo para rodar!"
            )
        )
        tabla = (
            "<table style='width:100%;border-collapse:collapse;margin:8px 0'>" + "".join(filas) + "</table>"
            if filas
            else "<p style='margin:8px 0;color:#10B981;font-size:14px;font-weight:600'>✓ Sin observaciones — todo en orden.</p>"
        )
        obs_nota = (
            f"<br><br><em style='color:#666'>Nota del mecánico: {self._esc(observaciones)}</em>"
            if observaciones and observaciones.strip()
            else ""
        )
        cuerpo = (
            f"Hola <strong>{self._esc(nombre)}</strong>, realizamos el diagnóstico de tu vehiculo "
            f"<strong>{self._esc(marca)} {self._esc(modelo)}</strong> (placa <strong>{self._esc(placa)}</strong>) "
            f"con {km_ingreso or 0:,d} km.<br><br>"
            f"<span style='color:{acento};font-weight:800'>{resumen}</span>{obs_nota}<br>{tabla}"
        )
        html_body = self._html_base(
            f"{'⚠️ ' if critico else ''}{titulo}",
            cuerpo,
            "Agendar servicio",
            f"{PORTAL_URL}/mi-vehiculo",
            "Diagnóstico realizado por un técnico de Open Auto.",
        )
        asunto = (
            f"⚠️ Diagnóstico: tu vehiculo {placa} necesita atención — Open Auto"
            if critico
            else f"Diagnóstico de tu vehiculo {placa} — Open Auto"
        )
        return self.enviar(correo, asunto, html_body)

    # ── 7. Factura de Servicio de Taller ──────────────────────────────────────
    def enviar_factura_registro(self, registro: Any, detalles: List[Any]) -> bool:
        cliente = getattr(registro, "cliente", None)
        if not cliente or not getattr(cliente, "correo", None):
            return False
        correo = cliente.correo
        placa = registro.vehiculo.placa if getattr(registro, "vehiculo", None) else "No registrada"
        tipo_nombre = registro.tipo.nombre if getattr(registro, "tipo", None) else "Servicio de taller"
        total = (
            float(registro.factura.costo_total)
            if getattr(registro, "factura", None) and registro.factura.costo_total is not None
            else 0.0
        )
        if detalles:
            total = sum(float(getattr(d, "subtotal", 0) or 0) for d in detalles)
        fecha_str = str(registro.fecha) if getattr(registro, "fecha", None) else str(date.today())
        ref_num = f"ORD-{registro.id_registro:06d}" if getattr(registro, "id_registro", None) else "ORD"

        filas_det = []
        for d in detalles or []:
            desc = getattr(d, "descripcion", "Servicio") or "Servicio"
            cant = getattr(d, "cantidad", 1) or 1
            sub = float(getattr(d, "subtotal", 0) or 0)
            filas_det.append(
                f"<tr style='border-bottom:1px solid #F3F4F6'>"
                f"<td style='padding:10px 14px;font-size:13px;color:#1F2937'>{self._esc(desc)}</td>"
                f"<td style='padding:10px 14px;font-size:13px;color:#374151;text-align:center'>{cant}</td>"
                f"<td style='padding:10px 14px;font-size:13px;font-weight:700;color:#111827;text-align:right'>${sub:.2f}</td></tr>"
            )

        tabla_html = (
            "<table width='100%' cellpadding='0' cellspacing='0' style='border-collapse:collapse;margin-top:16px;border:1px solid #E5E7EB'>"
            "<tr style='background:#F9FAFB'><th style='padding:8px 14px;text-align:left;font-size:11px'>Concepto</th>"
            "<th style='padding:8px 14px;text-align:center;font-size:11px'>Cant.</th>"
            "<th style='padding:8px 14px;text-align:right;font-size:11px'>Subtotal</th></tr>"
            + "".join(filas_det)
            + "</table>"
            if filas_det
            else ""
        )

        cuerpo = (
            f"Estimado/a <strong>{self._esc(cliente.nombre_completo)}</strong>, "
            f"se ha emitido el comprobante <strong>{ref_num}</strong> para el vehículo con placa "
            f"<strong>{self._esc(placa)}</strong> ({self._esc(tipo_nombre)}) con fecha {self._esc(fecha_str)}."
            f"{tabla_html}"
            f"<div style='margin-top:18px;padding:16px;background:#1E293B;color:#fff;border-radius:8px;text-align:right'>"
            f"<span style='font-size:12px;text-transform:uppercase;color:#94A3B8'>Total Facturado: </span>"
            f"<strong style='font-size:24px;color:#fff'>${total:.2f}</strong></div>"
        )
        html_body = self._html_base(
            f"Comprobante de Servicio {ref_num}",
            cuerpo,
            "Ver en el Portal",
            PORTAL_URL,
            "Gracias por confiar en Open Auto — Cuenca, Ecuador.",
        )
        return self.enviar(correo, f"Comprobante de servicio {ref_num} — Open Auto", html_body)

    # ── 8. Comprobante de Venta Directa de Inventario ─────────────────────────
    def enviar_comprobante_inventario(
        self,
        correo_cliente: str,
        nombre_cliente: str,
        items: Optional[List[Dict[str, Any]]] = None,
        total: float = 0.0,
        fecha: Optional[str] = None,
        referencia: Optional[str] = None,
        cliente: Optional[Dict[str, Any]] = None,
        nombre_producto: Optional[str] = None,
        codigo_producto: Optional[str] = None,
        cantidad: int = 1,
        pvp: float = 0.0,
    ) -> bool:
        if not correo_cliente:
            return False
        ref = referencia or (
            f"GRM-{date.today().strftime('%y%m%d')}-{uuid.uuid4().hex[:4].upper()}"
        )
        fecha_str = fecha or str(date.today())
        if not items:
            items = [
                {
                    "nombreProducto": nombre_producto or "Producto",
                    "codigoProducto": codigo_producto or "—",
                    "cantidad": cantidad,
                    "pvp": pvp,
                    "subtotal": total or (cantidad * pvp),
                }
            ]
        filas = []
        for it in items:
            prod = self._esc(
                str(it.get("nombreProducto") or it.get("nombre") or it.get("descripcion") or "Producto")
            )
            cod = self._esc(
                str(it.get("codigoProducto") or it.get("codigo") or it.get("codigo_personal") or "—")
            )
            cant = int(it.get("cantidad") or 1)
            unit = float(it.get("pvp") or it.get("precioUnitario") or 0.0)
            sub = float(it.get("subtotal") or (cant * unit))
            filas.append(
                f"<tr><td style='padding:10px 12px;border-bottom:1px solid #eee'><strong>{prod}</strong><br><small style='color:#888'>Ref: {cod}</small></td>"
                f"<td style='padding:10px 12px;border-bottom:1px solid #eee;text-align:center'>{cant}</td>"
                f"<td style='padding:10px 12px;border-bottom:1px solid #eee;text-align:right'>${unit:.2f}</td>"
                f"<td style='padding:10px 12px;border-bottom:1px solid #eee;text-align:right;font-weight:700;color:#E11428'>${sub:.2f}</td></tr>"
            )

        cuerpo = (
            f"Estimado/a <strong>{self._esc(nombre_cliente or 'Consumidor final')}</strong>, "
            f"adjuntamos el detalle de tu comprobante de compra <strong>#{self._esc(ref)}</strong> ({self._esc(fecha_str)})."
            "<table width='100%' cellpadding='0' cellspacing='0' style='border-collapse:collapse;margin-top:16px'>"
            "<tr style='background:#FFF5F5'><th style='padding:8px 12px;text-align:left;font-size:11px'>Producto</th>"
            "<th style='padding:8px 12px;text-align:center;font-size:11px'>Cant.</th>"
            "<th style='padding:8px 12px;text-align:right;font-size:11px'>P. Unit</th>"
            "<th style='padding:8px 12px;text-align:right;font-size:11px'>Subtotal</th></tr>"
            + "".join(filas)
            + "</table>"
            f"<div style='margin-top:16px;padding:14px;background:#1E293B;color:#fff;border-radius:8px;text-align:right'>"
            f"TOTAL PAGADO: <strong style='font-size:22px'>${float(total):.2f}</strong></div>"
        )
        html_body = self._html_base(
            f"Comprobante de compra #{ref}",
            cuerpo,
            "Visitar Portal",
            PORTAL_URL,
            "Conserve este correo como comprobante oficial de su compra en Open Auto.",
        )
        return self.enviar(correo_cliente, f"Comprobante de compra #{ref} — Open Auto", html_body)

    # ── Helpers privados ──────────────────────────────────────────────────────
    def _html_base(
        self, titulo: str, cuerpo: str, btn_label: str, btn_url: str, nota: Optional[str] = None
    ) -> str:
        yr = date.today().year
        nota_html = (
            f"<p style='margin:24px 0 0;color:#888;font-size:12px;line-height:1.5'>{nota}</p>"
            if nota
            else ""
        )
        return (
            "<!DOCTYPE html><html><head><meta charset='UTF-8'></head><body style='"
            "margin:0;padding:0;background:#F4F4F5;font-family:Arial,sans-serif'>"
            "<table width='100%' cellpadding='0' cellspacing='0'><tr><td align='center' style='padding:40px 16px'>"
            "<table width='560' cellpadding='0' cellspacing='0' style='background:#fff;border-radius:16px;"
            "overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08)'>"
            "<tr><td style='background:#0C0C10;padding:28px 40px'>"
            "<p style='margin:0;color:#fff;font-size:22px;font-weight:900;letter-spacing:-0.5px'>"
            "Gorila <span style='color:#E11428'>Vehiculos</span></p>"
            "<p style='margin:4px 0 0;color:rgba(255,255,255,0.4);font-size:11px;letter-spacing:2px;text-transform:uppercase'>Sistema de gestión · Ecuador</p>"
            "</td></tr>"
            "<tr><td style='padding:36px 40px'>"
            f"<h2 style='margin:0 0 16px;color:#111;font-size:20px'>{titulo}</h2>"
            f"<div style='margin:0 0 24px;color:#555;font-size:15px;line-height:1.6'>{cuerpo}</div>"
            f"<a href='{btn_url}' style='display:inline-block;background:#E11428;color:#fff;text-decoration:none;"
            f"padding:12px 28px;border-radius:10px;font-weight:700;font-size:14px'>{btn_label}</a>"
            f"{nota_html}"
            "</td></tr>"
            "<tr><td style='background:#F9F9FB;padding:20px 40px;border-top:1px solid #eee'>"
            f"<p style='margin:0;color:#aaa;font-size:11px'>© {yr} Open Auto · Cuenca, Ecuador · "
            f"<a href='{PORTAL_URL}' style='color:#E11428'>open-auto.vercel.app</a></p>"
            "</td></tr></table></td></tr></table></body></html>"
        )

    @staticmethod
    def _tipo_label(tipo: str) -> str:
        mapping = {
            "ACEITE": "Cambio de aceite",
            "FILTRO_AIRE": "Cambio de filtro de aire",
            "BUJIA": "Cambio de bujía",
            "CADENA": "Revisión de cadena",
            "LLANTA_TRASERA": "Cambio de llanta trasera",
            "FRENOS": "Revisión de frenos",
            "REVISION_GENERAL": "Revisión general",
        }
        return mapping.get(tipo, (tipo or "").replace("_", " ").lower())

    @staticmethod
    def _esc(val: Optional[str]) -> str:
        if val is None:
            return "—"
        return html.escape(str(val))

    # ── Métodos adaptadores de alto nivel usados por los módulos ──────────────
    def enviar_correo_bienvenida(
        self, destinatario: str, nombre_completo: str, nombre_usuario: str = ""
    ) -> bool:
        return self.enviar_bienvenida(destinatario, nombre_completo or nombre_usuario)

    def enviar_correo_recuperacion(
        self, destinatario: str, nombre_usuario: str, token: str
    ) -> bool:
        return self.enviar_email_recuperacion(destinatario, token, nombre_usuario)

    def enviar_correo_prueba(self, destino: str) -> Dict[str, Any]:
        ok = self.enviar_email_prueba(destino)
        return {
            "exito": ok,
            "destinatario": destino,
            "mensaje": "Correo enviado correctamente" if ok else "No hay proveedor de correo configurado o falló el envío",
        }

    def enviar_correo_oferta(
        self,
        destinatario: str,
        nombre_cliente: str,
        titulo: str,
        mensaje: str,
        descuento: Optional[str] = None,
        validez: Optional[str] = None,
    ) -> bool:
        extra = ""
        if descuento:
            extra += f"\n\nDescuento especial: {descuento}"
        if validez:
            extra += f"\nVálido hasta: {validez}"
        return self.enviar_oferta_marketing(destinatario, titulo, f"Hola {nombre_cliente},\n\n{mensaje}{extra}")

    def enviar_comprobante_venta_directa(
        self,
        destinatario: str,
        nombre_cliente: str,
        cedula: Optional[str] = None,
        telefono: Optional[str] = None,
        direccion: Optional[str] = None,
        id_factura: Optional[int] = None,
        items: Optional[List[Dict[str, Any]]] = None,
        total: float = 0.0,
    ) -> bool:
        ref = f"FAC-{id_factura:06d}" if id_factura else None
        return self.enviar_comprobante_inventario(
            correo_cliente=destinatario,
            nombre_cliente=nombre_cliente,
            items=items,
            total=total,
            referencia=ref,
        )

    def enviar_informe_diagnostico(
        self,
        destinatario: str,
        nombre_cliente: str,
        nombre_mecanico: str,
        vehiculo_desc: str,
        placa: str,
        kilometraje: Optional[int],
        observaciones_generales: Optional[str],
        detalles: List[Dict[str, Any]],
    ) -> bool:
        partes = (vehiculo_desc or "Vehiculo").split(" ", 1)
        marca = partes[0]
        modelo = partes[1] if len(partes) > 1 else ""
        return self.enviar_diagnostico(
            correo=destinatario,
            nombre=nombre_cliente,
            placa=placa,
            marca=marca,
            modelo=modelo,
            km_ingreso=kilometraje or 0,
            observaciones=observaciones_generales,
            detalles=detalles,
        )

    def enviar_factura_mantenimiento(
        self,
        destinatario: str,
        nombre_cliente: str,
        cedula_cliente: Optional[str],
        telefono_cliente: Optional[str],
        direccion_cliente: Optional[str],
        id_factura: int,
        vehiculo_desc: str,
        placa: str,
        encargado: str,
        tipo_servicio: str,
        observaciones: Optional[str],
        detalles: List[Dict[str, Any]],
        costo_total: float,
    ) -> bool:
        return self.enviar_comprobante_inventario(
            correo_cliente=destinatario,
            nombre_cliente=nombre_cliente,
            items=[
                {
                    "nombreProducto": d.get("descripcion", "Servicio"),
                    "codigoProducto": str(d.get("id_producto") or "SRV"),
                    "cantidad": d.get("cantidad", 1),
                    "pvp": d.get("precioUnitario") or d.get("precio_unitario") or 0.0,
                    "subtotal": d.get("subtotal", 0.0),
                }
                for d in (detalles or [])
            ],
            total=costo_total,
            referencia=f"ORD-{id_factura:06d}",
        )


email_service = EmailService()
