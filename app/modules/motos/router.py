from fastapi import APIRouter, Depends, UploadFile, File, Form, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import EntityNotFoundError
from app.modules.motos.schemas import MotoCreate, MotoUpdate
from app.modules.motos.service import MotoService
from app.shared.storage_service import storage_service
from app.shared.ocr_service import ocr_service

motos_router = APIRouter(prefix="/api/motos", tags=["Motos"])


@motos_router.post("", status_code=status.HTTP_201_CREATED)
@motos_router.post("/", status_code=status.HTTP_201_CREATED, include_in_schema=False)
def crear_moto(payload: MotoCreate, db: Session = Depends(get_db)):
    nueva = MotoService.crear(db, payload)
    return nueva.to_dict()


@motos_router.get("")
@motos_router.get("/", include_in_schema=False)
def listar_motos(db: Session = Depends(get_db)):
    motos = MotoService.listar_todas(db)
    return [m.to_dict() for m in motos]


@motos_router.get("/placa/{placa}")
def buscar_moto_por_placa(placa: str, db: Session = Depends(get_db)):
    moto = MotoService.obtener_por_placa(db, placa)
    if not moto:
        return Response(status_code=status.HTTP_404_NOT_FOUND)
    return moto.to_dict()


@motos_router.get("/usuario/{id_usuario}")
def listar_motos_por_usuario(id_usuario: int, db: Session = Depends(get_db)):
    motos = MotoService.listar_por_usuario(db, id_usuario)
    return [m.to_dict() for m in motos]


@motos_router.get("/{id_moto}")
def obtener_moto(id_moto: int, db: Session = Depends(get_db)):
    try:
        moto = MotoService.obtener_por_id(db, id_moto)
        return moto.to_dict()
    except EntityNotFoundError:
        return Response(status_code=status.HTTP_404_NOT_FOUND)


@motos_router.put("/{id_moto}")
def actualizar_moto(id_moto: int, payload: MotoUpdate, db: Session = Depends(get_db)):
    moto = MotoService.actualizar(db, id_moto, payload)
    return moto.to_dict()


@motos_router.delete("/{id_moto}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_moto(id_moto: int, db: Session = Depends(get_db)):
    MotoService.eliminar(db, id_moto)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@motos_router.post("/upload")
def subir_imagen_moto(
    archivo: UploadFile = File(...),
    placa: str = Form("moto"),
):
    if not archivo or not archivo.filename:
        return JSONResponse(status_code=400, content={"error": "El archivo está vacío"})
    url = storage_service.upload_file(archivo, "motos", f"moto_{placa}")
    return {"url": url}


@motos_router.post("/ocr/placa")
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


@motos_router.post("/ocr/buscar-dueno")
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
    moto = MotoService.obtener_por_placa(db, placa_detectada)
    if not moto:
        return JSONResponse(
            status_code=404,
            content={
                "mensaje": "No se encontró ninguna moto registrada con esa placa",
                "placaDetectada": placa_detectada,
            },
        )
    return {
        "mensaje": "Moto encontrada exitosamente",
        "placaDetectada": placa_detectada,
        "moto": moto.to_dict(),
        "dueno": moto.to_dict().get("usuario"),
    }


@motos_router.post("/{id_moto}/ocr-placa")
async def actualizar_placa_por_ocr(
    id_moto: int,
    archivo: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    moto = MotoService.obtener_por_id(db, id_moto)
    content = await archivo.read()
    ocr_result = ocr_service.reconocer_placa(content, archivo.filename or "placa.jpg")
    if not ocr_result.get("success") or not ocr_result.get("placa"):
        return JSONResponse(
            status_code=400,
            content={"error": "No se pudo detectar una placa válida", "detalle": ocr_result},
        )
    nueva_placa = ocr_result["placa"].strip().upper()
    actualizada = MotoService.actualizar(db, moto.id_moto, MotoUpdate(placa=nueva_placa))
    return {
        "mensaje": "Placa reconocida y actualizada con éxito",
        "placaDetectada": nueva_placa,
        "confianza": ocr_result.get("confianza"),
        "moto": actualizada.to_dict(),
    }

