from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, UploadFile, File, Query, Body, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import EntityNotFoundError
from app.modules.taller.schemas import (
    TipoCreate,
    RegistroCreate,
    DiagnosticoCreate,
    RecepcionCreate,
    RecepcionUpdate,
    PresupuestoCreate,
    PresupuestoDecisionRequest,
    BitacoraReparacionCreate,
    DanoAdicionalCreate,
    DanoAdicionalDecisionRequest,
    ControlCalidadCreate,
    EntregaVehiculoCreate,
)
from app.modules.taller.service import (
    TipoService,
    RegistroService,
    DiagnosticoService,
    RecepcionService,
    PresupuestoService,
    ReparacionService,
    EntregaService,
)
from app.modules.facturacion.service import DetalleFacturaService
from app.shared.ocr_service import ocr_service
from app.shared.storage_service import storage_service

tipos_router = APIRouter(prefix="/api/tipos", tags=["Tipos de Servicio"])
registros_router = APIRouter(prefix="/api/registros", tags=["Registros de Taller"])
diagnosticos_router = APIRouter(prefix="/api/diagnosticos", tags=["Diagnósticos Mecánicos"])
recepciones_router = APIRouter(prefix="/api/recepciones", tags=["Hojas de Recepción"])
presupuestos_router = APIRouter(prefix="/api/presupuestos", tags=["Presupuestos de Taller"])
reparaciones_router = APIRouter(prefix="/api/reparaciones", tags=["Fase C: Reparación y Control de Calidad"])
entregas_router = APIRouter(prefix="/api/entregas", tags=["Fase E: Entrega de Vehículo - Proceso 15"])


# ==========================================
# TIPOS DE SERVICIO (/api/tipos)
# ==========================================

@tipos_router.post("", status_code=status.HTTP_201_CREATED)
@tipos_router.post("/", status_code=status.HTTP_201_CREATED, include_in_schema=False)
def crear_tipo(payload: TipoCreate, db: Session = Depends(get_db)):
    t = TipoService.crear(db, payload)
    return t.to_dict()


@tipos_router.get("")
@tipos_router.get("/", include_in_schema=False)
def listar_tipos(db: Session = Depends(get_db)):
    tipos = TipoService.listar_todos(db)
    return [t.to_dict() for t in tipos]


@tipos_router.get("/{id_tipo}")
def obtener_tipo(id_tipo: int, db: Session = Depends(get_db)):
    try:
        t = TipoService.obtener_por_id(db, id_tipo)
        return t.to_dict()
    except EntityNotFoundError:
        return Response(status_code=status.HTTP_404_NOT_FOUND)


@tipos_router.put("/{id_tipo}")
def actualizar_tipo(id_tipo: int, payload: TipoCreate, db: Session = Depends(get_db)):
    t = TipoService.actualizar(db, id_tipo, payload)
    return t.to_dict()


@tipos_router.delete("/{id_tipo}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_tipo(id_tipo: int, db: Session = Depends(get_db)):
    TipoService.eliminar(db, id_tipo)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ==========================================
# REGISTROS DE TALLER (/api/registros)
# ==========================================

@registros_router.post("", status_code=status.HTTP_201_CREATED)
@registros_router.post("/", status_code=status.HTTP_201_CREATED, include_in_schema=False)
def crear_registro(payload: RegistroCreate, db: Session = Depends(get_db)):
    return RegistroService.crear(db, payload)


@registros_router.post("/test")
def test_registro():
    return "POST OK"


@registros_router.put("/{id_registro}/factura")
def asociar_factura_a_registro(
    id_registro: int,
    payload: Optional[Dict[str, Any]] = Body(default=None),
    idFactura: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
):
    id_fac = idFactura
    if id_fac is None and payload:
        id_fac = payload.get("idFactura") or payload.get("id_factura")
    if id_fac is None:
        return JSONResponse(status_code=400, content={"error": "Debe indicar idFactura"})
    return RegistroService.asociar_factura(db, id_registro, int(id_fac))


@registros_router.patch("/{id_registro}/estado")
def actualizar_estado_registro(
    id_registro: int,
    estado: Optional[int] = Query(default=None),
    payload: Optional[Dict[str, Any]] = Body(default=None),
    db: Session = Depends(get_db),
):
    nuevo_estado = estado
    if nuevo_estado is None and payload:
        nuevo_estado = payload.get("estado")
    if nuevo_estado is None:
        return JSONResponse(status_code=400, content={"error": "El parámetro 'estado' es obligatorio"})
    return RegistroService.cambiar_estado(db, id_registro, int(nuevo_estado))


@registros_router.get("/usuario/{id_usuario}")
def listar_registros_por_usuario(id_usuario: int, db: Session = Depends(get_db)):
    return RegistroService.listar_por_cliente(db, id_usuario)


@registros_router.delete("/{id_registro}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_registro(id_registro: int, db: Session = Depends(get_db)):
    RegistroService.eliminar(db, id_registro)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@registros_router.get("")
@registros_router.get("/", include_in_schema=False)
def listar_registros(db: Session = Depends(get_db)):
    return RegistroService.listar_todos_dto(db)


@registros_router.get("/resumen")
def listar_resumen_registros(db: Session = Depends(get_db)):
    return RegistroService.listar_todos_dto(db)


@registros_router.get("/cliente/{id_cliente}")
def listar_registros_cliente(id_cliente: int, db: Session = Depends(get_db)):
    return RegistroService.listar_por_cliente(db, id_cliente)


@registros_router.get("/encargado/{id_encargado}")
def listar_registros_encargado(id_encargado: int, db: Session = Depends(get_db)):
    return RegistroService.listar_por_encargado(db, id_encargado)


@registros_router.get("/historial/{id_cliente}")
def obtener_historial_cliente(id_cliente: int, db: Session = Depends(get_db)):
    return RegistroService.listar_por_cliente(db, id_cliente)


@registros_router.get("/buscar/placa")
def buscar_registros_por_placa(placa: str = Query(""), db: Session = Depends(get_db)):
    return RegistroService.buscar_por_placa(db, placa)


@registros_router.get("/buscar/nombre")
def buscar_registros_por_nombre(nombre: str = Query(""), db: Session = Depends(get_db)):
    return RegistroService.buscar_por_nombre_cliente(db, nombre)


@registros_router.get("/{id_factura}/detalles-factura")
def obtener_detalles_de_factura_desde_registro(id_factura: int, db: Session = Depends(get_db)):
    dets = DetalleFacturaService.listar_por_factura(db, id_factura)
    return [d.to_dict() for d in dets]


@registros_router.post("/ocr/historial")
async def buscar_historial_por_ocr(
    archivo: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if not archivo:
        return JSONResponse(status_code=400, content={"error": "El archivo está vacío"})
    content = await archivo.read()
    ocr_result = ocr_service.reconocer_placa(content, archivo.filename or "placa.jpg")
    if not ocr_result.get("success") or not ocr_result.get("placa"):
        return JSONResponse(
            status_code=400,
            content={"error": "No se pudo detectar la placa en la imagen", "detalleOcr": ocr_result},
        )
    placa_detectada = ocr_result["placa"].strip().upper()
    historial = RegistroService.buscar_por_placa(db, placa_detectada)
    if not historial:
        return JSONResponse(
            status_code=404,
            content={
                "mensaje": "No se encontraron registros para la placa detectada",
                "placaDetectada": placa_detectada,
                "historial": [],
            },
        )
    return {
        "mensaje": "Historial encontrado exitosamente",
        "placaDetectada": placa_detectada,
        "totalRegistros": len(historial),
        "historial": historial,
    }


@registros_router.get("/{id_registro}")
def obtener_registro(id_registro: int, db: Session = Depends(get_db)):
    try:
        return RegistroService.obtener_por_id_dto(db, id_registro)
    except EntityNotFoundError:
        return Response(status_code=status.HTTP_404_NOT_FOUND)


# ==========================================
# DIAGNÓSTICOS (/api/diagnosticos)
# ==========================================

@diagnosticos_router.get("/plantilla-8-sistemas")
def obtener_plantilla_8_sistemas():
    """Retorna los 8 sistemas del auto con sus puntos de inspección sugeridos (Proceso 3)."""
    return DiagnosticoService.plantilla_8_sistemas()


@diagnosticos_router.post("", status_code=status.HTTP_201_CREATED)
@diagnosticos_router.post("/", status_code=status.HTTP_201_CREATED, include_in_schema=False)
def crear_diagnostico(payload: DiagnosticoCreate, db: Session = Depends(get_db)):
    """Registra la revisión de los 8 sistemas, códigos DTC del escáner y problemas encontrados."""
    diag = DiagnosticoService.crear(db, payload)
    return diag.to_dict()


@diagnosticos_router.get("/registro/{id_registro}")
def listar_diagnosticos_por_registro(id_registro: int, db: Session = Depends(get_db)):
    diags = DiagnosticoService.listar_por_registro(db, id_registro)
    return [d.to_dict() for d in diags]


@diagnosticos_router.get("/vehiculo/{id_vehiculo}")
def listar_diagnosticos_por_vehiculo(id_vehiculo: int, db: Session = Depends(get_db)):
    diags = DiagnosticoService.listar_por_vehiculo(db, id_vehiculo)
    return [d.to_dict() for d in diags]


@diagnosticos_router.get("/mecanico/{id_mecanico}")
def listar_diagnosticos_por_mecanico(id_mecanico: int, db: Session = Depends(get_db)):
    diags = DiagnosticoService.listar_por_mecanico(db, id_mecanico)
    return [d.to_dict() for d in diags]


@diagnosticos_router.get("/{id_diagnostico}")
def obtener_diagnostico(id_diagnostico: int, db: Session = Depends(get_db)):
    try:
        diag = DiagnosticoService.obtener_por_id(db, id_diagnostico)
        return diag.to_dict()
    except EntityNotFoundError:
        return Response(status_code=status.HTTP_404_NOT_FOUND)


@diagnosticos_router.post("/fotos-evidencia")
def subir_foto_evidencia_diagnostico(
    archivo: UploadFile = File(...),
    sistema: Optional[str] = Query(default="GENERAL"),
):
    """Sube foto de evidencia de una pieza dañada o problema encontrado durante la inspección."""
    if not archivo or not archivo.filename:
        return JSONResponse(status_code=400, content={"error": "Archivo no proporcionado"})
    prefix = f"diag_{sistema.lower()}" if sistema else "diag"
    url = storage_service.upload_file(archivo, "diagnosticos", prefix)
    return {"url": url, "sistema": sistema}


# ==========================================
# HOJAS DE RECEPCIÓN (/api/recepciones)
# ==========================================

@recepciones_router.post("", status_code=status.HTTP_201_CREATED)
@recepciones_router.post("/", status_code=status.HTTP_201_CREATED, include_in_schema=False)
def crear_recepcion(payload: RecepcionCreate, db: Session = Depends(get_db)):
    """Registra la hoja de recepción del auto (Proceso 2: km, combustible, testigos, fotos y firma)."""
    return RecepcionService.crear(db, payload)


@recepciones_router.get("")
@recepciones_router.get("/", include_in_schema=False)
def listar_recepciones(db: Session = Depends(get_db)):
    return RecepcionService.listar_todas(db)


@recepciones_router.get("/{id_recepcion}")
def obtener_recepcion(id_recepcion: int, db: Session = Depends(get_db)):
    try:
        return RecepcionService.obtener_por_id(db, id_recepcion)
    except EntityNotFoundError:
        return Response(status_code=status.HTTP_404_NOT_FOUND)


@recepciones_router.put("/{id_recepcion}")
def actualizar_recepcion(
    id_recepcion: int, payload: RecepcionUpdate, db: Session = Depends(get_db)
):
    """Actualiza datos, fotos o firma de una recepción existente."""
    try:
        return RecepcionService.actualizar(db, id_recepcion, payload)
    except EntityNotFoundError:
        return Response(status_code=status.HTTP_404_NOT_FOUND)


@recepciones_router.get("/vehiculo/{id_vehiculo}")
def listar_recepciones_por_vehiculo(id_vehiculo: int, db: Session = Depends(get_db)):
    return RecepcionService.listar_por_vehiculo(db, id_vehiculo)


@recepciones_router.get("/registro/{id_registro}")
def obtener_recepcion_por_registro(id_registro: int, db: Session = Depends(get_db)):
    res = RecepcionService.obtener_por_registro(db, id_registro)
    if not res:
        return Response(status_code=status.HTTP_404_NOT_FOUND)
    return res


@recepciones_router.get("/{id_recepcion}/validar")
def validar_recepcion_proceso_2_1(id_recepcion: int, db: Session = Depends(get_db)):
    """Verifica si la recepción cumple con el Proceso 2.1 (4 fotos, combustible, km y firma)."""
    try:
        return RecepcionService.validar_completitud(db, id_recepcion)
    except EntityNotFoundError:
        return Response(status_code=status.HTTP_404_NOT_FOUND)


@recepciones_router.post("/fotos")
def subir_foto_recepcion(
    archivo: UploadFile = File(...),
    tipo: str = Query(..., description="frente | posterior | lateral_izq | lateral_der | firma | tablero"),
):
    """Sube una foto de la recepción o firma del cliente y retorna su URL pública."""
    if not archivo or not archivo.filename:
        return JSONResponse(status_code=400, content={"error": "Archivo no proporcionado"})
    prefix = f"rec_{tipo}"
    url = storage_service.upload_file(archivo, "recepciones", prefix)
    return {"url": url, "tipo": tipo}


# ==========================================
# PRESUPUESTOS Y COTIZACIONES (/api/presupuestos) - PROCESO 5
# ==========================================

@presupuestos_router.post("", status_code=status.HTTP_201_CREATED)
@presupuestos_router.post("/", status_code=status.HTTP_201_CREATED, include_in_schema=False)
def crear_presupuesto(payload: PresupuestoCreate, db: Session = Depends(get_db)):
    """Crea un presupuesto con desglose de repuestos y mano de obra (Proceso 5)."""
    return PresupuestoService.crear(db, payload)


@presupuestos_router.get("")
@presupuestos_router.get("/", include_in_schema=False)
def listar_presupuestos(db: Session = Depends(get_db)):
    return PresupuestoService.listar_todos(db)


@presupuestos_router.get("/{id_presupuesto}")
def obtener_presupuesto(id_presupuesto: int, db: Session = Depends(get_db)):
    try:
        return PresupuestoService.obtener_por_id(db, id_presupuesto)
    except EntityNotFoundError:
        return Response(status_code=status.HTTP_404_NOT_FOUND)


@presupuestos_router.get("/registro/{id_registro}")
def listar_presupuestos_por_registro(id_registro: int, db: Session = Depends(get_db)):
    return PresupuestoService.listar_por_registro(db, id_registro)


@presupuestos_router.get("/vehiculo/{id_vehiculo}")
def listar_presupuestos_por_vehiculo(id_vehiculo: int, db: Session = Depends(get_db)):
    return PresupuestoService.listar_por_vehiculo(db, id_vehiculo)


@presupuestos_router.post("/{id_presupuesto}/enviar")
def enviar_presupuesto_al_cliente(id_presupuesto: int, db: Session = Depends(get_db)):
    """Cambia el estado del presupuesto a ENVIADO para revisión del cliente."""
    try:
        return PresupuestoService.enviar_al_cliente(db, id_presupuesto)
    except EntityNotFoundError:
        return Response(status_code=status.HTTP_404_NOT_FOUND)


@presupuestos_router.post("/{id_presupuesto}/decision")
def responder_presupuesto_cliente(
    id_presupuesto: int, payload: PresupuestoDecisionRequest, db: Session = Depends(get_db)
):
    """
    Registra la decisión del cliente sobre el presupuesto:
    - APROBADO_TOTAL: Aprobación total de mano de obra y repuestos -> Avanza a Proceso 6.
    - APROBADO_PARCIAL (Proceso 5.1): Ajuste de presupuesto, se aprueba solo parte de los ítems.
    - RECHAZADO (Proceso 5.2): Se rechaza el trabajo. Si aplica, se cobra costo de diagnóstico.
    """
    try:
        return PresupuestoService.registrar_decision_cliente(db, id_presupuesto, payload)
    except EntityNotFoundError:
        return Response(status_code=status.HTTP_404_NOT_FOUND)


# ==========================================
# FASE C: REPARACIÓN, DAÑOS ADICIONALES Y CONTROL DE CALIDAD (/api/reparaciones)
# ==========================================

@reparaciones_router.post("/bitacora", status_code=status.HTTP_201_CREATED)
def registrar_avance_reparacion(payload: BitacoraReparacionCreate, db: Session = Depends(get_db)):
    """Registra horas trabajadas, avance técnico y fotos de la reparación (Proceso 7)."""
    return ReparacionService.registrar_bitacora(db, payload)


@reparaciones_router.get("/bitacora/{id_registro}")
def listar_bitacoras_orden(id_registro: int, db: Session = Depends(get_db)):
    """Consulta la bitácora técnica de una orden de taller."""
    return ReparacionService.listar_bitacoras_por_registro(db, id_registro)


@reparaciones_router.post("/danos-adicionales", status_code=status.HTTP_201_CREATED)
def reportar_dano_adicional(payload: DanoAdicionalCreate, db: Session = Depends(get_db)):
    """
    Reporta un nuevo daño encontrado durante la intervención mecánica (Proceso 7.1).
    Queda pendiente de autorización del cliente antes de continuar o cobrar.
    """
    return ReparacionService.reportar_dano_adicional(db, payload)


@reparaciones_router.post("/danos-adicionales/{id_dano}/decision")
def responder_dano_adicional(
    id_dano: int, payload: DanoAdicionalDecisionRequest, db: Session = Depends(get_db)
):
    """Registra la respuesta del cliente (APROBADO / RECHAZADO) para el trabajo adicional."""
    return ReparacionService.responder_dano_adicional(db, id_dano, payload)


@reparaciones_router.get("/danos-adicionales/{id_registro}")
def listar_danos_adicionales_orden(id_registro: int, db: Session = Depends(get_db)):
    """Lista todos los daños adicionales detectados en una orden."""
    return ReparacionService.listar_danos_por_registro(db, id_registro)


@reparaciones_router.post("/control-calidad", status_code=status.HTTP_201_CREATED)
def registrar_control_calidad(payload: ControlCalidadCreate, db: Session = Depends(get_db)):
    """
    Inspección final de calidad y escaneo OBD2 post-reparación:
    - Si pasa (Proceso 9): Marca vehículo como LISTO PARA ENTREGA (estado 3).
    - Si no pasa (Proceso 8.1): Devuelve al mecánico para corregir sin costo extra.
    """
    return ReparacionService.registrar_control_calidad(db, payload)


@reparaciones_router.get("/control-calidad/{id_registro}")
def listar_controles_calidad_orden(id_registro: int, db: Session = Depends(get_db)):
    """Obtiene el historial de revisiones de calidad y escaneo final de la orden."""
    return ReparacionService.listar_controles_por_registro(db, id_registro)


@reparaciones_router.post("/fotos")
def subir_foto_reparacion(
    archivo: UploadFile = File(...),
    tipo: str = Query(..., description="proceso_reparacion | dano_adicional | escaneo_final"),
):
    """Sube fotos tomadas durante la reparación o evidencia de daños ocultos."""
    if not archivo or not archivo.filename:
        return JSONResponse(status_code=400, content={"error": "Archivo no proporcionado"})
    url = storage_service.upload_file(archivo, "reparaciones", f"rep_{tipo}")
    return {"url": url, "tipo": tipo}


# ==========================================
# FASE E: ENTREGA DEL VEHÍCULO (/api/entregas) - PROCESO 15
# ==========================================

@entregas_router.post("", status_code=status.HTTP_201_CREATED)
@entregas_router.post("/", status_code=status.HTTP_201_CREATED, include_in_schema=False)
def registrar_entrega_vehiculo(payload: EntregaVehiculoCreate, db: Session = Depends(get_db)):
    """
    Proceso 15: Entrega física del vehículo al cliente.
    Verifica que la orden esté pagada, registra firma de salida y reinicia ciclos de desgaste.
    """
    return EntregaService.entregar_vehiculo(db, payload)


@entregas_router.get("/registro/{id_registro}")
def obtener_entrega_por_registro(id_registro: int, db: Session = Depends(get_db)):
    res = EntregaService.obtener_entrega_por_registro(db, id_registro)
    if not res:
        return Response(status_code=status.HTTP_404_NOT_FOUND)
    return res


@entregas_router.get("")
@entregas_router.get("/", include_in_schema=False)
def listar_entregas_realizadas(db: Session = Depends(get_db)):
    return EntregaService.listar_entregas(db)




