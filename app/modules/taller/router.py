from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, UploadFile, File, Query, Body, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import EntityNotFoundError
from app.modules.taller.schemas import TipoCreate, RegistroCreate, DiagnosticoCreate
from app.modules.taller.service import TipoService, RegistroService, DiagnosticoService
from app.modules.facturacion.service import DetalleFacturaService
from app.shared.ocr_service import ocr_service

tipos_router = APIRouter(prefix="/api/tipos", tags=["Tipos de Servicio"])
registros_router = APIRouter(prefix="/api/registros", tags=["Registros de Taller"])
diagnosticos_router = APIRouter(prefix="/api/diagnosticos", tags=["Diagnósticos Mecánicos"])


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

@diagnosticos_router.post("", status_code=status.HTTP_201_CREATED)
@diagnosticos_router.post("/", status_code=status.HTTP_201_CREATED, include_in_schema=False)
def crear_diagnostico(payload: DiagnosticoCreate, db: Session = Depends(get_db)):
    diag = DiagnosticoService.crear(db, payload)
    return diag.to_dict()


@diagnosticos_router.get("/moto/{id_moto}")
def listar_diagnosticos_por_moto(id_moto: int, db: Session = Depends(get_db)):
    diags = DiagnosticoService.listar_por_moto(db, id_moto)
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

