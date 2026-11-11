from fastapi import APIRouter, Depends, UploadFile, File, Form, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import EntityNotFoundError
from app.modules.vehiculos.schemas import VehiculoCreate, VehiculoUpdate
from app.modules.vehiculos.service import VehiculoService
from app.shared.storage_service import storage_service
from app.shared.ocr_service import ocr_service

vehiculos_router = APIRouter(prefix="/api/vehiculos", tags=["Vehiculos"])


@vehiculos_router.post("", status_code=status.HTTP_201_CREATED)
@vehiculos_router.post("/", status_code=status.HTTP_201_CREATED, include_in_schema=False)
def crear_vehiculo(payload: VehiculoCreate, db: Session = Depends(get_db)):
    nueva = VehiculoService.crear(db, payload)
    return nueva.to_dict()


@vehiculos_router.get("")
@vehiculos_router.get("/", include_in_schema=False)
def listar_vehiculos(db: Session = Depends(get_db)):
    vehiculos = VehiculoService.listar_todas(db)
    return [m.to_dict() for m in vehiculos]


@vehiculos_router.get("/placa/{placa}")
@vehiculos_router.get("/buscar/placa/{placa}", include_in_schema=False)
def buscar_vehiculo_por_placa(placa: str, db: Session = Depends(get_db)):
    vehiculo = VehiculoService.obtener_por_placa(db, placa)
    if not vehiculo:
        return Response(status_code=status.HTTP_404_NOT_FOUND)
    return vehiculo.to_dict()


@vehiculos_router.get("/cedula/{cedula}")
@vehiculos_router.get("/buscar/cedula/{cedula}", include_in_schema=False)
def buscar_vehiculos_por_cedula(cedula: str, db: Session = Depends(get_db)):
    """Proceso 1: Buscar vehículos por la cédula del cliente."""
    vehiculos = VehiculoService.listar_por_cedula(db, cedula)
    return [v.to_dict() for v in vehiculos]


@vehiculos_router.get("/usuario/{id_usuario}")
def listar_vehiculos_por_usuario(id_usuario: int, db: Session = Depends(get_db)):
    vehiculos = VehiculoService.listar_por_usuario(db, id_usuario)
    return [m.to_dict() for m in vehiculos]


@vehiculos_router.get("/{id_vehiculo}")
def obtener_vehiculo(id_vehiculo: int, db: Session = Depends(get_db)):
    try:
        vehiculo = VehiculoService.obtener_por_id(db, id_vehiculo)
        return vehiculo.to_dict()
    except EntityNotFoundError:
        return Response(status_code=status.HTTP_404_NOT_FOUND)


@vehiculos_router.put("/{id_vehiculo}")
def actualizar_vehiculo(id_vehiculo: int, payload: VehiculoUpdate, db: Session = Depends(get_db)):
    vehiculo = VehiculoService.actualizar(db, id_vehiculo, payload)
    return vehiculo.to_dict()


@vehiculos_router.delete("/{id_vehiculo}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_vehiculo(id_vehiculo: int, db: Session = Depends(get_db)):
    VehiculoService.eliminar(db, id_vehiculo)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@vehiculos_router.post("/upload")
def subir_imagen_vehiculo(
    archivo: UploadFile = File(...),
    placa: str = Form("vehiculo"),
):
    if not archivo or not archivo.filename:
        return JSONResponse(status_code=400, content={"error": "El archivo está vacío"})
    url = storage_service.upload_file(archivo, "vehiculos", f"vehiculo_{placa}")
    return {"url": url}


@vehiculos_router.post("/ocr/placa")
async def detectar_placa_ocr(archivo: UploadFile = File(...)):
    if not archivo:
        return JSONResponse(status_code=400, content={"error": "No se proporcionó ninguna imagen"})
    content = await archivo.read()
    if not content:
        return JSONResponse(status_code=400, content={"error": "El archivo está vacío"})
    res = ocr_service.reconocer_placa(content, archivo.filename or "placa.jpg")
    if res.get("success"):
        return res
    return JSONResponse(status_code=400, content=res)


@vehiculos_router.post("/ocr/buscar-dueno")
async def buscar_dueno_por_imagen(archivo: UploadFile = File(...), db: Session = Depends(get_db)):
    if not archivo:
        return JSONResponse(status_code=400, content={"error": "El archivo está vacío"})
    content = await archivo.read()
    ocr_result = ocr_service.reconocer_placa(content, archivo.filename or "placa.jpg")
    if not ocr_result.get("success") or not ocr_result.get("placa"):
        return JSONResponse(
            status_code=400,
            content={"error": "No se pudo detectar la placa", "detalleOcr": ocr_result},
        )
    placa_detectada = ocr_result["placa"].strip().upper()
    vehiculo = VehiculoService.obtener_por_placa(db, placa_detectada)
    if not vehiculo:
        return JSONResponse(
            status_code=404,
            content={
                "mensaje": "No se encontró ningún vehículo registrado con esa placa",
                "placaDetectada": placa_detectada,
            },
        )
    return {
        "mensaje": "Vehículo encontrado exitosamente",
        "placaDetectada": placa_detectada,
        "vehiculo": vehiculo.to_dict(),
        "dueno": vehiculo.to_dict().get("usuario"),
    }


@vehiculos_router.post("/{id_vehiculo}/ocr-placa")
async def actualizar_placa_por_ocr(
    id_vehiculo: int,
    archivo: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    vehiculo = VehiculoService.obtener_por_id(db, id_vehiculo)
    content = await archivo.read()
    ocr_result = ocr_service.reconocer_placa(content, archivo.filename or "placa.jpg")
    if not ocr_result.get("success") or not ocr_result.get("placa"):
        return JSONResponse(
            status_code=400,
            content={"error": "No se pudo detectar una placa válida", "detalle": ocr_result},
        )
    nueva_placa = ocr_result["placa"].strip().upper()
    actualizada = VehiculoService.actualizar(db, vehiculo.id_vehiculo, VehiculoUpdate(placa=nueva_placa))
    return {
        "mensaje": "Placa reconocida y actualizada con éxito",
        "placaDetectada": nueva_placa,
        "confianza": ocr_result.get("confianza"),
        "vehiculo": actualizada.to_dict(),
    }

