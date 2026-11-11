from datetime import date, datetime
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.modules.inventario.models import Producto  # noqa: F401


class Tipo(Base):
    __tablename__ = "tipo"

    id_tipo = Column("id_tipo", Integer, primary_key=True, index=True, autoincrement=True)
    nombre = Column("nombre", String(100), nullable=False)
    descripcion = Column("descripcion", String(500), nullable=True)
    id_producto = Column("id_producto", Integer, ForeignKey("productos.id_producto", ondelete="SET NULL"), nullable=True)
    concepto_manual = Column("concepto_manual", String(255), nullable=True)
    concepto_cantidad = Column("concepto_cantidad", Integer, nullable=True, default=1)
    concepto_precio_unitario = Column("concepto_precio_unitario", Float, nullable=True, default=0.0)

    producto = relationship("Producto", lazy="joined")

    def to_dict(self) -> dict:
        prod_dict = self.producto.to_dict() if self.producto else None
        return {
            "id_tipo": self.id_tipo,
            "nombre": self.nombre,
            "descripcion": self.descripcion,
            "id_producto": self.id_producto,
            "producto": prod_dict,
            "productoPvp": prod_dict["pvp"] if prod_dict else None,
            "concepto_manual": self.concepto_manual,
            "concepto_cantidad": self.concepto_cantidad if self.concepto_cantidad is not None else 1,
            "concepto_precio_unitario": (
                round(float(self.concepto_precio_unitario), 2)
                if self.concepto_precio_unitario is not None
                else 0.0
            ),
        }


class Registro(Base):
    __tablename__ = "registros"

    id_registro = Column("id_registro", Integer, primary_key=True, index=True, autoincrement=True)
    fecha = Column("fecha", Date, nullable=False, default=date.today)
    fecha_entrega_estimada = Column("fecha_entrega_estimada", DateTime, nullable=True)
    fecha_completado = Column("fecha_completado", DateTime, nullable=True)
    fecha_entregado = Column("fecha_entregado", DateTime, nullable=True)
    fecha_facturado = Column("fecha_facturado", DateTime, nullable=True)
    descripcion = Column("descripcion", String(1000), nullable=True)
    observaciones = Column("observaciones", String(1000), nullable=True)
    costo_total = Column("costo_total", Float, nullable=False, default=0.0)
    id_vehiculo = Column("id_vehiculo", Integer, ForeignKey("vehiculos.id_vehiculo", ondelete="CASCADE"), nullable=False, index=True)
    id_encargado = Column("id_encargado", Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True, index=True)
    id_tipo = Column("id_tipo", Integer, ForeignKey("tipo.id_tipo", ondelete="SET NULL"), nullable=True)
    id_factura = Column("id_factura", Integer, ForeignKey("facturas.id_factura", ondelete="SET NULL"), nullable=True, index=True)
    kilometraje = Column("kilometraje", Integer, nullable=True)
    estado = Column("estado", Integer, nullable=False, default=1)

    vehiculo = relationship("Vehiculo", lazy="joined")
    encargado = relationship("Usuario", foreign_keys=[id_encargado], lazy="joined")
    tipo = relationship("Tipo", lazy="joined")
    factura = relationship("Factura", lazy="joined")

    def to_raw_dict(self) -> dict:
        return {
            "id_registro": self.id_registro,
            "fecha": self.fecha.isoformat() if self.fecha else date.today().isoformat(),
            "fecha_entrega_estimada": self.fecha_entrega_estimada.isoformat() if self.fecha_entrega_estimada else None,
            "fecha_completado": self.fecha_completado.isoformat() if self.fecha_completado else None,
            "fecha_entregado": self.fecha_entregado.isoformat() if self.fecha_entregado else None,
            "fecha_facturado": self.fecha_facturado.isoformat() if self.fecha_facturado else None,
            "descripcion": self.descripcion,
            "observaciones": self.observaciones,
            "costo_total": round(float(self.costo_total or 0.0), 2),
            "id_vehiculo": self.id_vehiculo,
            "id_encargado": self.id_encargado,
            "id_tipo": self.id_tipo,
            "id_factura": self.id_factura,
            "kilometraje": self.kilometraje if self.kilometraje is not None else (self.vehiculo.kilometraje if self.vehiculo else 0),
            "estado": self.estado if self.estado is not None else 1,
        }


class DiagnosticoVehiculo(Base):
    __tablename__ = "diagnostico_vehiculo"

    id_diagnostico = Column("id_diagnostico", Integer, primary_key=True, index=True, autoincrement=True)
    id_vehiculo = Column("id_vehiculo", Integer, ForeignKey("vehiculos.id_vehiculo", ondelete="CASCADE"), nullable=False, index=True)
    id_mecanico = Column("id_mecanico", Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=False, index=True)
    id_registro = Column("id_registro", Integer, ForeignKey("registros.id_registro", ondelete="SET NULL"), nullable=True, index=True)
    id_recepcion = Column("id_recepcion", Integer, ForeignKey("recepciones_vehiculo.id_recepcion", ondelete="SET NULL"), nullable=True, index=True)
    fecha = Column("fecha", DateTime, nullable=False, default=datetime.now)
    kilometraje_ingreso = Column("kilometraje_ingreso", Integer, nullable=True)
    escaner_utilizado = Column("escaner_utilizado", String(150), nullable=True)
    codigos_dtc = Column("codigos_dtc", String(2000), nullable=True)
    descripcion_escaner = Column("descripcion_escaner", String(2000), nullable=True)
    observaciones_generales = Column("observaciones_generales", String(1000), nullable=True)
    problemas_adicionales = Column("problemas_adicionales", String(2000), nullable=True)
    fotos_problemas = Column("fotos_problemas", String(3000), nullable=True)

    vehiculo = relationship("Vehiculo", lazy="joined")
    mecanico = relationship("Usuario", foreign_keys=[id_mecanico], lazy="joined")
    registro = relationship("Registro", foreign_keys=[id_registro], lazy="joined")
    recepcion = relationship("RecepcionVehiculo", foreign_keys=[id_recepcion], lazy="joined")

    detalles = relationship(
        "DetalleDiagnostico",
        back_populates="diagnostico",
        cascade="all, delete-orphan",
        lazy="joined",
    )

    def to_dict(self) -> dict:
        fotos_list = [f.strip() for f in (self.fotos_problemas or "").split(",") if f.strip()]
        return {
            "id_diagnostico": self.id_diagnostico,
            "id_vehiculo": self.id_vehiculo,
            "id_mecanico": self.id_mecanico,
            "nombre_mecanico": self.mecanico.nombre_completo if self.mecanico else None,
            "id_registro": self.id_registro,
            "id_recepcion": self.id_recepcion,
            "fecha": self.fecha.isoformat() if self.fecha else datetime.now().isoformat(),
            "kilometraje_ingreso": self.kilometraje_ingreso,
            "escaner_utilizado": self.escaner_utilizado,
            "codigos_dtc": self.codigos_dtc,
            "descripcion_escaner": self.descripcion_escaner,
            "observaciones_generales": self.observaciones_generales,
            "problemas_adicionales": self.problemas_adicionales,
            "fotos_problemas": self.fotos_problemas,
            "lista_fotos_problemas": fotos_list,
            "detalles": [d.to_dict() for d in (self.detalles or [])],
        }


class DetalleDiagnostico(Base):
    __tablename__ = "detalle_diagnostico"

    id_detalle = Column("id_detalle", Integer, primary_key=True, index=True, autoincrement=True)
    id_diagnostico = Column("id_diagnostico", Integer, ForeignKey("diagnostico_vehiculo.id_diagnostico", ondelete="CASCADE"), nullable=False)
    sistema = Column("sistema", String(100), nullable=False, default="GENERAL")
    parte = Column("parte", String(150), nullable=False)
    estado = Column("estado", String(50), nullable=False, default="BUENO")
    observacion = Column("observacion", String(1000), nullable=True)
    foto_evidencia = Column("foto_evidencia", String(500), nullable=True)
    requiere_repuesto = Column("requiere_repuesto", Boolean, nullable=False, default=False)

    diagnostico = relationship("DiagnosticoVehiculo", back_populates="detalles")

    def to_dict(self) -> dict:
        return {
            "id_detalle": self.id_detalle,
            "id_diagnostico": self.id_diagnostico,
            "sistema": self.sistema,
            "parte": self.parte,
            "estado": self.estado,
            "observacion": self.observacion,
            "foto_evidencia": self.foto_evidencia,
            "requiere_repuesto": bool(self.requiere_repuesto),
        }


class RecepcionVehiculo(Base):
    """
    Hoja de Recepción / Check-in del Vehículo (Procesos 2 y 2.1 del Taller).
    Registra kilometraje, nivel de combustible, testigos encendidos del tablero,
    daños previos de carrocería, las 4 fotos obligatorias de los 4 lados y la firma del cliente.
    """
    __tablename__ = "recepciones_vehiculo"

    id_recepcion = Column("id_recepcion", Integer, primary_key=True, index=True, autoincrement=True)
    id_vehiculo = Column("id_vehiculo", Integer, ForeignKey("vehiculos.id_vehiculo", ondelete="CASCADE"), nullable=False, index=True)
    id_encargado = Column("id_encargado", Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True, index=True)
    id_registro = Column("id_registro", Integer, ForeignKey("registros.id_registro", ondelete="SET NULL"), nullable=True, index=True)
    fecha_ingreso = Column("fecha_ingreso", DateTime, nullable=False, default=datetime.now)
    kilometraje = Column("kilometraje", Integer, nullable=False, default=0)
    nivel_combustible = Column("nivel_combustible", String(50), nullable=False, default="1/2")
    luces_tablero = Column("luces_tablero", String(500), nullable=True)
    danos_previos = Column("danos_previos", String(1000), nullable=True)
    foto_frente = Column("foto_frente", String(500), nullable=True)
    foto_posterior = Column("foto_posterior", String(500), nullable=True)
    foto_lateral_izq = Column("foto_lateral_izq", String(500), nullable=True)
    foto_lateral_der = Column("foto_lateral_der", String(500), nullable=True)
    firma_cliente = Column("firma_cliente", String(10000), nullable=True)
    observaciones = Column("observaciones", String(1000), nullable=True)

    vehiculo = relationship("Vehiculo", lazy="joined")
    encargado = relationship("Usuario", foreign_keys=[id_encargado], lazy="joined")
    registro = relationship("Registro", foreign_keys=[id_registro], lazy="joined")

    @property
    def faltantes(self) -> list[str]:
        """Calcula qué requisitos faltan para completar la recepción."""
        pendientes = []
        if self.kilometraje is None or self.kilometraje < 0:
            pendientes.append("kilometraje")
        if not self.nivel_combustible or not str(self.nivel_combustible).strip():
            pendientes.append("nivel_combustible")
        if not self.foto_frente or not str(self.foto_frente).strip():
            pendientes.append("foto_frente")
        if not self.foto_posterior or not str(self.foto_posterior).strip():
            pendientes.append("foto_posterior")
        if not self.foto_lateral_izq or not str(self.foto_lateral_izq).strip():
            pendientes.append("foto_lateral_izq")
        if not self.foto_lateral_der or not str(self.foto_lateral_der).strip():
            pendientes.append("foto_lateral_der")
        if not self.firma_cliente or not str(self.firma_cliente).strip():
            pendientes.append("firma_cliente")
        return pendientes

    @property
    def esta_completa(self) -> bool:
        """Determina si cumple estrictamente el Proceso 2.1 (4 fotos + firma + datos)."""
        return len(self.faltantes) == 0

    def to_dict(self) -> dict:
        v_dict = self.vehiculo.to_dict() if self.vehiculo else None
        return {
            "id_recepcion": self.id_recepcion,
            "id_vehiculo": self.id_vehiculo,
            "vehiculo": v_dict,
            "id_encargado": self.id_encargado,
            "nombre_encargado": self.encargado.nombre_completo if self.encargado else None,
            "id_registro": self.id_registro,
            "fecha_ingreso": self.fecha_ingreso.isoformat() if self.fecha_ingreso else datetime.now().isoformat(),
            "kilometraje": self.kilometraje,
            "nivel_combustible": self.nivel_combustible,
            "luces_tablero": self.luces_tablero,
            "danos_previos": self.danos_previos,
            "foto_frente": self.foto_frente,
            "foto_posterior": self.foto_posterior,
            "foto_lateral_izq": self.foto_lateral_izq,
            "foto_lateral_der": self.foto_lateral_der,
            "firma_cliente": self.firma_cliente,
            "observaciones": self.observaciones,
            "completa": self.esta_completa,
            "faltantes": self.faltantes,
        }


class Presupuesto(Base):
    __tablename__ = "presupuestos"

    id_presupuesto = Column("id_presupuesto", Integer, primary_key=True, index=True, autoincrement=True)
    numero_presupuesto = Column("numero_presupuesto", String(50), unique=True, index=True, nullable=False)
    id_registro = Column("id_registro", Integer, ForeignKey("registros.id_registro", ondelete="CASCADE"), nullable=False, index=True)
    id_vehiculo = Column("id_vehiculo", Integer, ForeignKey("vehiculos.id_vehiculo", ondelete="CASCADE"), nullable=False, index=True)
    id_diagnostico = Column("id_diagnostico", Integer, ForeignKey("diagnostico_vehiculo.id_diagnostico", ondelete="SET NULL"), nullable=True, index=True)
    id_usuario = Column("id_usuario", Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True, index=True)
    fecha_emision = Column("fecha_emision", DateTime, nullable=False, default=datetime.now)
    fecha_respuesta = Column("fecha_respuesta", DateTime, nullable=True)
    estado = Column("estado", String(50), nullable=False, default="BORRADOR")  # BORRADOR, ENVIADO, APROBADO_TOTAL, APROBADO_PARCIAL, RECHAZADO
    subtotal_mano_obra = Column("subtotal_mano_obra", Float, nullable=False, default=0.0)
    subtotal_repuestos = Column("subtotal_repuestos", Float, nullable=False, default=0.0)
    descuento = Column("descuento", Float, nullable=False, default=0.0)
    total_presupuestado = Column("total_presupuestado", Float, nullable=False, default=0.0)
    total_aprobado = Column("total_aprobado", Float, nullable=False, default=0.0)
    costo_diagnostico = Column("costo_diagnostico", Float, nullable=False, default=0.0)
    cobrar_solo_diagnostico = Column("cobrar_solo_diagnostico", Boolean, nullable=False, default=False)
    observaciones = Column("observaciones", String(1000), nullable=True)
    motivo_rechazo_ajuste = Column("motivo_rechazo_ajuste", String(1000), nullable=True)

    registro = relationship("Registro", lazy="joined")
    vehiculo = relationship("Vehiculo", lazy="joined")
    diagnostico = relationship("DiagnosticoVehiculo", lazy="joined")
    usuario = relationship("Usuario", foreign_keys=[id_usuario], lazy="joined")
    items = relationship("ItemPresupuesto", back_populates="presupuesto", cascade="all, delete-orphan", lazy="selectin")

    def to_dict(self) -> dict:
        return {
            "id_presupuesto": self.id_presupuesto,
            "numero_presupuesto": self.numero_presupuesto,
            "id_registro": self.id_registro,
            "id_vehiculo": self.id_vehiculo,
            "vehiculo": self.vehiculo.to_dict() if self.vehiculo else None,
            "id_diagnostico": self.id_diagnostico,
            "id_usuario": self.id_usuario,
            "nombre_asesor": self.usuario.nombre_completo if self.usuario else None,
            "fecha_emision": self.fecha_emision.isoformat() if self.fecha_emision else None,
            "fecha_respuesta": self.fecha_respuesta.isoformat() if self.fecha_respuesta else None,
            "estado": self.estado,
            "subtotal_mano_obra": round(float(self.subtotal_mano_obra or 0.0), 2),
            "subtotal_repuestos": round(float(self.subtotal_repuestos or 0.0), 2),
            "descuento": round(float(self.descuento or 0.0), 2),
            "total_presupuestado": round(float(self.total_presupuestado or 0.0), 2),
            "total_aprobado": round(float(self.total_aprobado or 0.0), 2),
            "costo_diagnostico": round(float(self.costo_diagnostico or 0.0), 2),
            "cobrar_solo_diagnostico": self.cobrar_solo_diagnostico,
            "observaciones": self.observaciones,
            "motivo_rechazo_ajuste": self.motivo_rechazo_ajuste,
            "items": [item.to_dict() for item in self.items] if self.items else [],
        }


class ItemPresupuesto(Base):
    __tablename__ = "items_presupuesto"

    id_item = Column("id_item", Integer, primary_key=True, index=True, autoincrement=True)
    id_presupuesto = Column("id_presupuesto", Integer, ForeignKey("presupuestos.id_presupuesto", ondelete="CASCADE"), nullable=False, index=True)
    tipo_item = Column("tipo_item", String(20), nullable=False, default="REPUESTO")  # REPUESTO, MANO_OBRA
    id_producto = Column("id_producto", Integer, ForeignKey("productos.id_producto", ondelete="SET NULL"), nullable=True, index=True)
    descripcion = Column("descripcion", String(255), nullable=False)
    cantidad = Column("cantidad", Float, nullable=False, default=1.0)
    precio_unitario = Column("precio_unitario", Float, nullable=False, default=0.0)
    subtotal = Column("subtotal", Float, nullable=False, default=0.0)
    estado_aprobacion = Column("estado_aprobacion", String(20), nullable=False, default="PENDIENTE")  # PENDIENTE, APROBADO, RECHAZADO, POSTERGADO
    es_adicional = Column("es_adicional", Boolean, nullable=False, default=False)

    presupuesto = relationship("Presupuesto", back_populates="items")
    producto = relationship("Producto", lazy="joined")

    def to_dict(self) -> dict:
        prod_dict = self.producto.to_dict() if self.producto else None
        return {
            "id_item": self.id_item,
            "id_presupuesto": self.id_presupuesto,
            "tipo_item": self.tipo_item,
            "id_producto": self.id_producto,
            "producto": prod_dict,
            "descripcion": self.descripcion,
            "cantidad": round(float(self.cantidad or 0.0), 2),
            "precio_unitario": round(float(self.precio_unitario or 0.0), 2),
            "subtotal": round(float(self.subtotal or 0.0), 2),
            "estado_aprobacion": self.estado_aprobacion,
            "es_adicional": self.es_adicional,
        }


class BitacoraReparacion(Base):
    """
    Registro del trabajo del mecánico: horas trabajadas, avance y fotos de la reparación (Proceso 7).
    """
    __tablename__ = "bitacoras_reparacion"

    id_bitacora = Column("id_bitacora", Integer, primary_key=True, index=True, autoincrement=True)
    id_registro = Column("id_registro", Integer, ForeignKey("registros.id_registro", ondelete="CASCADE"), nullable=False, index=True)
    id_mecanico = Column("id_mecanico", Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True, index=True)
    fecha = Column("fecha", DateTime, nullable=False, default=datetime.now)
    horas_trabajadas = Column("horas_trabajadas", Float, nullable=False, default=0.0)
    descripcion_trabajo = Column("descripcion_trabajo", String(1000), nullable=False)
    fotos_evidencia = Column("fotos_evidencia", String(3000), nullable=True)
    repuestos_instalados = Column("repuestos_instalados", String(1000), nullable=True)

    registro = relationship("Registro", lazy="joined")
    mecanico = relationship("Usuario", lazy="joined")

    def to_dict(self) -> dict:
        fotos = [f.strip() for f in (self.fotos_evidencia or "").split(",") if f.strip()]
        return {
            "id_bitacora": self.id_bitacora,
            "id_registro": self.id_registro,
            "id_mecanico": self.id_mecanico,
            "nombre_mecanico": self.mecanico.nombre_completo if self.mecanico else None,
            "fecha": self.fecha.isoformat() if self.fecha else datetime.now().isoformat(),
            "horas_trabajadas": round(float(self.horas_trabajadas or 0.0), 2),
            "descripcion_trabajo": self.descripcion_trabajo,
            "fotos_evidencia": self.fotos_evidencia,
            "lista_fotos": fotos,
            "repuestos_instalados": self.repuestos_instalados,
        }


class DanoAdicional(Base):
    """
    Nuevo daño detectado durante la reparación que requiere cotización y aprobación del cliente (Proceso 7.1).
    """
    __tablename__ = "danos_adicionales"

    id_dano = Column("id_dano", Integer, primary_key=True, index=True, autoincrement=True)
    id_registro = Column("id_registro", Integer, ForeignKey("registros.id_registro", ondelete="CASCADE"), nullable=False, index=True)
    id_mecanico = Column("id_mecanico", Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True, index=True)
    fecha_deteccion = Column("fecha_deteccion", DateTime, nullable=False, default=datetime.now)
    descripcion = Column("descripcion", String(1000), nullable=False)
    fotos_evidencia = Column("fotos_evidencia", String(3000), nullable=True)
    repuesto_sugerido = Column("repuesto_sugerido", String(255), nullable=True)
    id_producto = Column("id_producto", Integer, ForeignKey("productos.id_producto", ondelete="SET NULL"), nullable=True, index=True)
    costo_estimado = Column("costo_estimado", Float, nullable=False, default=0.0)
    estado = Column("estado", String(30), nullable=False, default="PENDIENTE")  # PENDIENTE, APROBADO, RECHAZADO
    fecha_respuesta = Column("fecha_respuesta", DateTime, nullable=True)
    observaciones_cliente = Column("observaciones_cliente", String(500), nullable=True)

    registro = relationship("Registro", lazy="joined")
    mecanico = relationship("Usuario", lazy="joined")
    producto = relationship("Producto", lazy="joined")

    def to_dict(self) -> dict:
        fotos = [f.strip() for f in (self.fotos_evidencia or "").split(",") if f.strip()]
        return {
            "id_dano": self.id_dano,
            "id_registro": self.id_registro,
            "id_mecanico": self.id_mecanico,
            "nombre_mecanico": self.mecanico.nombre_completo if self.mecanico else None,
            "fecha_deteccion": self.fecha_deteccion.isoformat() if self.fecha_deteccion else datetime.now().isoformat(),
            "descripcion": self.descripcion,
            "fotos_evidencia": self.fotos_evidencia,
            "lista_fotos": fotos,
            "repuesto_sugerido": self.repuesto_sugerido,
            "id_producto": self.id_producto,
            "producto_nombre": self.producto.nombre if self.producto else None,
            "costo_estimado": round(float(self.costo_estimado or 0.0), 2),
            "estado": self.estado,
            "fecha_respuesta": self.fecha_respuesta.isoformat() if self.fecha_respuesta else None,
            "observaciones_cliente": self.observaciones_cliente,
        }


class ControlCalidad(Base):
    """
    Inspección final de la reparación y escaneo OBD2 para verificación de entrega (Proceso 8 y 8.1).
    """
    __tablename__ = "controles_calidad"

    id_control = Column("id_control", Integer, primary_key=True, index=True, autoincrement=True)
    id_registro = Column("id_registro", Integer, ForeignKey("registros.id_registro", ondelete="CASCADE"), nullable=False, index=True)
    id_revisor = Column("id_revisor", Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True, index=True)
    fecha = Column("fecha", DateTime, nullable=False, default=datetime.now)
    paso_inspeccion = Column("paso_inspeccion", Boolean, nullable=False, default=True)
    escaner_utilizado = Column("escaner_utilizado", String(150), nullable=True)
    codigos_dtc_detectados = Column("codigos_dtc_detectados", String(1000), nullable=True, default="Sin códigos de falla")
    observaciones = Column("observaciones", String(1000), nullable=True)
    motivo_devolucion = Column("motivo_devolucion", String(1000), nullable=True)
    accion_tomada = Column("accion_tomada", String(50), nullable=False, default="APROBADO_LISTO")  # APROBADO_LISTO | DEVUELTO_A_MECANICO

    registro = relationship("Registro", lazy="joined")
    revisor = relationship("Usuario", lazy="joined")

    def to_dict(self) -> dict:
        return {
            "id_control": self.id_control,
            "id_registro": self.id_registro,
            "id_revisor": self.id_revisor,
            "nombre_revisor": self.revisor.nombre_completo if self.revisor else None,
            "fecha": self.fecha.isoformat() if self.fecha else datetime.now().isoformat(),
            "paso_inspeccion": self.paso_inspeccion,
            "escaner_utilizado": self.escaner_utilizado,
            "codigos_dtc_detectados": self.codigos_dtc_detectados,
            "observaciones": self.observaciones,
            "motivo_devolucion": self.motivo_devolucion,
            "accion_tomada": self.accion_tomada,
        }


class EntregaVehiculo(Base):
    """
    Registro formal de la entrega física del vehículo al cliente (Proceso 15).
    Verifica que la orden esté pagada y recoge firma de conformidad de salida.
    """
    __tablename__ = "entregas_vehiculo"

    id_entrega = Column("id_entrega", Integer, primary_key=True, index=True, autoincrement=True)
    id_registro = Column("id_registro", Integer, ForeignKey("registros.id_registro", ondelete="CASCADE"), nullable=False, index=True)
    id_vehiculo = Column("id_vehiculo", Integer, ForeignKey("vehiculos.id_vehiculo", ondelete="CASCADE"), nullable=False, index=True)
    id_usuario_entrega = Column("id_usuario_entrega", Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True)
    fecha_entrega = Column("fecha_entrega", DateTime, nullable=False, default=datetime.now)
    kilometraje_salida = Column("kilometraje_salida", Integer, nullable=False, default=0)
    firma_cliente_entrega = Column("firma_cliente_entrega", String(10000), nullable=True)
    persona_recibe = Column("persona_recibe", String(150), nullable=False)
    cedula_recibe = Column("cedula_recibe", String(30), nullable=True)
    observaciones = Column("observaciones", String(500), nullable=True)

    registro = relationship("Registro", lazy="joined")
    vehiculo = relationship("Vehiculo", lazy="joined")
    usuario_entrega = relationship("Usuario", lazy="joined")

    def to_dict(self) -> dict:
        return {
            "id_entrega": self.id_entrega,
            "id_registro": self.id_registro,
            "id_vehiculo": self.id_vehiculo,
            "placa": self.vehiculo.placa if self.vehiculo else None,
            "id_usuario_entrega": self.id_usuario_entrega,
            "entregado_por": self.usuario_entrega.nombre_completo if self.usuario_entrega else None,
            "fecha_entrega": self.fecha_entrega.isoformat() if self.fecha_entrega else datetime.now().isoformat(),
            "kilometraje_salida": self.kilometraje_salida,
            "firma_cliente_entrega": self.firma_cliente_entrega,
            "persona_recibe": self.persona_recibe,
            "cedula_recibe": self.cedula_recibe,
            "observaciones": self.observaciones,
        }




