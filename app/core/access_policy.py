"""Política de acciones del API. Las rutas nuevas quedan denegadas por defecto."""
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.authorization import current_user
from app.core.access_scope import scoped_query

PUBLIC = {"login", "registro_publico", "solicitar_recuperacion", "validar_token", "restablecer_contrasena", "api_health", "actuator_health", "actuator_info", "listar_roles"}
TECH_READ = {"obtener_flujo_orden",
    "listar_vehiculos", "buscar_vehiculo_por_placa", "buscar_vehiculos_por_cedula", "listar_vehiculos_por_usuario", "obtener_vehiculo",
    "listar_registros", "listar_resumen_registros", "listar_registros_por_usuario", "listar_registros_cliente", "listar_registros_encargado", "obtener_historial_cliente", "buscar_registros_por_placa", "buscar_registros_por_nombre", "obtener_registro",
    "obtener_detalles_de_factura_desde_registro", "obtener_factura", "listar_detalles_por_factura", "obtener_nota_venta_por_id", "obtener_nota_venta_por_registro",
    "listar_diagnosticos_por_registro", "listar_diagnosticos_por_vehiculo", "listar_diagnosticos_por_mecanico", "obtener_diagnostico",
    "listar_recepciones", "obtener_recepcion", "listar_recepciones_por_vehiculo", "obtener_recepcion_por_registro", "validar_recepcion_proceso_2_1",
    "listar_presupuestos", "obtener_presupuesto", "listar_presupuestos_por_registro", "listar_presupuestos_por_vehiculo",
    "listar_bitacoras_orden", "listar_danos_adicionales_orden", "listar_controles_calidad_orden", "obtener_entrega_por_registro", "listar_entregas_realizadas",
    "listar_mantenimientos_vehiculo", "obtener_estado_mantenimiento", "obtener_semaforo_desgaste_proceso_15_1_y_16", "listar_citas_preventivas", "listar_cargas", "listar_cargas_por_vehiculo",
    "listar_todas_rutas", "listar_rutas_por_usuario", "obtener_ruta", "listar_parametros", "obtener_precios_combustible", "obtener_usuario", "obtener_roles_usuario",
}
STAFF_READ = {"listar_herramientas", "obtener_herramienta","listar_usuarios", "listar_productos", "obtener_producto", "listar_categorias", "obtener_categoria", "listar_tipos", "obtener_tipo", "obtener_plantilla_8_sistemas", "detectar_placa_ocr", "buscar_dueno_por_imagen", "buscar_historial_por_ocr", "escanear_codigo_repuesto", "listar_alertas_stock_minimo"}
TECH_WRITE = {"crear_diagnostico", "registrar_avance_reparacion", "reportar_dano_adicional", "registrar_control_calidad", "actualizar_estado_registro", "actualizar_estimacion_orden", "registrar_mantenimiento", "eliminar_mantenimiento", "verificar_y_alertar", "subir_foto_evidencia_diagnostico", "subir_foto_reparacion"}
RECEPTION = {"crear_cliente", "crear_cuenta_rapida", "crear_vehiculo", "crear_recepcion", "actualizar_recepcion", "subir_foto_recepcion"}
INVENTORY_ENTRY = {"crear_producto", "actualizar_producto", "crear_categoria", "actualizar_categoria", "registrar_entrada_kardex", "subir_imagen_producto", "subir_factura_proveedor_movil", "listar_contactos_proveedores", "guardar_contacto_proveedor"}
INVENTORY_USE = {"registrar_salida_kardex", "reservar_repuesto_individual", "reservar_repuestos_de_presupuesto", "retirar_repuesto_para_instalacion", "listar_reservas_por_orden", "listar_todas_las_reservas"}
PERSONAL = {"cerrar_sesion", "subir_imagen_perfil", "usar_codigo_referido", "crear_ruta", "actualizar_ruta", "eliminar_ruta", "registrar_carga_combustible", "eliminar_carga_combustible", "agendar_cita_preventiva", "obtener_permisos_usuario", "obtener_perfil_laboral", "listar_horarios_personal", "listar_asistencia_personal"}
DECISIONS = {"responder_presupuesto_cliente", "responder_dano_adicional"}

async def authorize_request(request: Request, db: Session = Depends(get_db)):
    name = request.scope["endpoint"].__name__
    if name in PUBLIC:
        return
    actor = current_user(request, db)
    request.state.actor = actor
    if "ADMIN" in actor.roles:
        return
    if not actor.roles.intersection({"MECANICO", "CLIENTE"}):
        raise HTTPException(403, "El rol no tiene una política de acceso habilitada")
    mechanic = "MECANICO" in actor.roles
    customer = not mechanic and "CLIENTE" in actor.roles
    permission = lambda key: mechanic and key in actor.permisos
    content_type = request.headers.get("content-type", "")
    body = await request.json() if "application/json" in content_type and (await request.body()).strip() else {}
    if not isinstance(body, dict):
        body = {}
    allowed = name in TECH_READ or name in PERSONAL
    allowed |= mechanic and (name in STAFF_READ or name in TECH_WRITE)
    allowed |= permission("recepcion") and name in RECEPTION
    allowed |= permission("inventario_entradas") and name in INVENTORY_ENTRY
    allowed |= permission("inventario_consumos") and name in INVENTORY_USE
    allowed |= name == "listar_movimientos_kardex" and (permission("inventario_entradas") or permission("inventario_consumos"))
    allowed |= customer and name in DECISIONS
    allowed |= name == "listar_facturas" and customer
    allowed |= name == "subir_imagen_vehiculo" and (customer or permission("recepcion"))
    allowed |= name == "actualizar_usuario"
    allowed |= name == "actualizar_vehiculo" and (customer or permission("recepcion"))
    if name == "registrar_entrada_kardex" and body.get("id_registro", body.get("idRegistro")) is not None:
        raise HTTPException(403, "Solo el administrador puede registrar devoluciones de órdenes")
    if not allowed:
        raise HTTPException(403, "No tiene permisos para esta acción")

    from app.modules.usuarios.models import Usuario
    from app.modules.vehiculos.models import Vehiculo
    from app.modules.taller.models import Registro, DiagnosticoVehiculo, RecepcionVehiculo, Presupuesto, DanoAdicional, ItemPresupuesto
    from app.modules.facturacion.models import Factura, NotaDeVenta
    from app.modules.inventario.models import ReservaRepuesto
    from app.modules.combustible.models import CargaCombustible
    from app.modules.rutas.models import Ruta
    resources = {"id_vehiculo": (Vehiculo, "id_vehiculo"), "id_registro": (Registro, "id_registro"), "id_factura": (Factura, "id_factura"), "id_nota_venta": (NotaDeVenta, "id_nota_venta"), "id_diagnostico": (DiagnosticoVehiculo, "id_diagnostico"), "id_recepcion": (RecepcionVehiculo, "id_recepcion"), "id_presupuesto": (Presupuesto, "id_presupuesto"), "id_dano": (DanoAdicional, "id_dano"), "id_reserva": (ReservaRepuesto, "id_reserva"), "id_item_presupuesto": (ItemPresupuesto, "id_item"), "id_ruta": (Ruta, "id_ruta"), "id_carga": (CargaCombustible, "id_carga")}
    def value(key):
        camel = key.split('_')[0] + ''.join(p.title() for p in key.split('_')[1:])
        return body.get(key, body.get(camel, body.get("id_carro", body.get("idCarro")) if key == "id_vehiculo" else None))
    resolved = {}
    for key, (model, pk) in resources.items():
        identifier = request.path_params.get(key, value(key))
        if identifier is not None:
            obj = scoped_query(db, model).filter(getattr(model, pk) == identifier).first()
            if obj is None:
                raise HTTPException(404, "Registro no disponible")
            resolved[key] = obj
    if "id_registro" in resolved:
        for key in ("id_presupuesto", "id_recepcion", "id_reserva"):
            related = resolved.get(key)
            if related and related.id_registro is not None and related.id_registro != resolved["id_registro"].id_registro:
                raise HTTPException(403, "Los registros no pertenecen a la misma orden")
    if "id_item_presupuesto" in resolved and "id_presupuesto" in resolved:
        if resolved["id_item_presupuesto"].id_presupuesto != resolved["id_presupuesto"].id_presupuesto:
            raise HTTPException(403, "El ítem no corresponde al presupuesto")
    if "id_registro" in resolved and "id_vehiculo" in resolved and resolved["id_registro"].id_vehiculo != resolved["id_vehiculo"].id_vehiculo:
        raise HTTPException(403, "La orden no corresponde al vehículo")
    if mechanic and request.path_params.get("id_usuario") is not None and name in {"listar_vehiculos_por_usuario", "listar_registros_por_usuario", "listar_rutas_por_usuario"}:
        if name == "listar_rutas_por_usuario" and int(request.path_params["id_usuario"]) != actor.id_usuario:
            raise HTTPException(403, "No puede consultar las rutas de otro usuario")
    if customer:
        for key in ("id_usuario", "id_cliente", "id_encargado", "id_mecanico"):
            identifier = request.path_params.get(key)
            if identifier is not None and int(identifier) != actor.id_usuario:
                raise HTTPException(403, "No tiene permisos para este usuario")
    if name in {"obtener_usuario", "obtener_roles_usuario", "actualizar_usuario", "obtener_permisos_usuario", "usar_codigo_referido", "obtener_perfil_laboral"}:
        target = int(request.path_params["id_usuario"])
        if target != actor.id_usuario:
            if name in {"actualizar_usuario", "usar_codigo_referido", "obtener_permisos_usuario", "obtener_perfil_laboral"} and not (name == "actualizar_usuario" and permission("recepcion")):
                raise HTTPException(403, "No puede administrar esta cuenta")
            if name == "actualizar_usuario":
                from app.modules.roles.models import UsuarioRol, Rol
                if db.query(UsuarioRol).join(Rol).filter(UsuarioRol.id_usuario == target, UsuarioRol.estado == 1, Rol.nombre.in_(["ADMIN", "MECANICO"])).first():
                    raise HTTPException(403, "Recepción no puede administrar cuentas del personal")
            if scoped_query(db, Usuario).filter(Usuario.id_usuario == target).first() is None:
                raise HTTPException(404, "Usuario no disponible")
    if name == "actualizar_usuario":
        if any(k in body for k in ("puntos_bonus", "puntosBonus", "codigo_referido", "codigoReferido", "permisos", "roles")):
            raise HTTPException(403, "Los campos administrativos solo puede cambiarlos el administrador")
        target = int(request.path_params["id_usuario"])
        if target != actor.id_usuario and any(k in body for k in ("contrasena", "correo", "nombre_usuario", "nombreUsuario", "descripcion")):
            raise HTTPException(403, "No puede modificar credenciales o permisos de otra cuenta")
    if name == "crear_cuenta_rapida":
        from app.modules.roles.models import UsuarioRol, Rol
        from sqlalchemy import func
        existing = db.query(Usuario).filter(func.lower(Usuario.correo) == str(body.get("correo", "")).strip().lower()).first()
        if existing and db.query(UsuarioRol).join(Rol).filter(UsuarioRol.id_usuario == existing.id_usuario, UsuarioRol.estado == 1, Rol.nombre.in_(["ADMIN", "MECANICO"])).first():
            raise HTTPException(403, "Recepción no puede utilizar cuentas del personal")
    if name in {"crear_vehiculo", "actualizar_vehiculo", "crear_cuenta_rapida"}:
        owner = value("id_usuario")
        if owner is not None:
            from app.modules.roles.models import UsuarioRol, Rol
            staff = db.query(UsuarioRol).join(Rol).filter(UsuarioRol.id_usuario == owner, UsuarioRol.estado == 1, Rol.nombre.in_(["ADMIN", "MECANICO"])).first()
            if staff:
                raise HTTPException(403, "Recepción solo puede gestionar vehículos de clientes")
    if customer and name == "actualizar_vehiculo":
        if set(body) - {"kilometraje", "ruta_imagen_vehiculo", "rutaImagenVehiculo", "ruta_imagen_carros", "rutaImagenCarros"}:
            raise HTTPException(403, "Solo puede actualizar kilometraje y foto de su vehículo")
    if mechanic and name == "actualizar_estado_registro":
        state = body.get("estado", request.query_params.get("estado"))
        if str(state) == "3":
            raise HTTPException(403, "Solo el administrador puede registrar la entrega")
    if mechanic and name in TECH_WRITE:
        for key in ("id_mecanico", "id_revisor"):
            claimed = value(key)
            if claimed is not None and int(claimed) != actor.id_usuario:
                raise HTTPException(403, "No puede registrar trabajo a nombre de otro empleado")
    if mechanic and name in {"crear_diagnostico", "registrar_mantenimiento", "eliminar_mantenimiento", "verificar_y_alertar"} and "id_vehiculo" in resolved:
        vehicle_id = resolved["id_vehiculo"].id_vehiculo
        if scoped_query(db, Registro).filter(Registro.id_vehiculo == vehicle_id).first() is None:
            raise HTTPException(403, "El vehículo no tiene una orden asignada al mecánico")
    if mechanic and name in {"registrar_salida_kardex", "crear_recepcion"} and "id_registro" not in resolved:
        raise HTTPException(403, "Debe vincular una orden asignada")
    if mechanic and name in {"crear_recepcion", "actualizar_recepcion"}:
        claimed = value("id_encargado")
        if claimed is not None and int(claimed) != actor.id_usuario:
            raise HTTPException(403, "No puede reasignar el personal de recepción")
    if name == "responder_presupuesto_cliente":
        if resolved["id_presupuesto"].estado != "ENVIADO":
            raise HTTPException(403, "El presupuesto no está disponible para responder")
    if name in {"crear_ruta", "actualizar_ruta", "agendar_cita_preventiva"}:
        owner = value("id_usuario")
        if name != "agendar_cita_preventiva" and owner is not None and int(owner) != actor.id_usuario:
            raise HTTPException(403, "No puede registrar datos para otro usuario")
        if name == "agendar_cita_preventiva" and owner is not None:
            vehicle = resolved.get("id_vehiculo")
            if not vehicle or int(owner) != vehicle.id_usuario:
                raise HTTPException(403, "La cita no corresponde al propietario del vehículo")
