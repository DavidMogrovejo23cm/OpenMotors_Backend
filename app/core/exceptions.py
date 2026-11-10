from typing import Any
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class BusinessValidationError(ValueError):
    """Error de validación de reglas de negocio (HTTP 400)."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class EntityNotFoundError(LookupError):
    """Entidad no encontrada en la base de datos (HTTP 404)."""

    def __init__(self, entity: str, entity_id: Any = None):
        msg = f"{entity} con ID {entity_id} no encontrado" if entity_id is not None else f"{entity} no encontrado"
        super().__init__(msg)
        self.message = msg


class ConflictError(RuntimeError):
    """Conflicto de estado o duplicidad de registro (HTTP 409)."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class PermissionDeniedError(PermissionError):
    """Falta de permisos para ejecutar una operación (HTTP 403)."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(BusinessValidationError)
    async def business_validation_handler(request: Request, exc: BusinessValidationError):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "error": str(exc), "mensaje": str(exc)},
        )

    @app.exception_handler(EntityNotFoundError)
    async def not_found_handler(request: Request, exc: EntityNotFoundError):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "error": str(exc), "mensaje": str(exc)},
        )

    @app.exception_handler(ConflictError)
    async def conflict_handler(request: Request, exc: ConflictError):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"success": False, "error": str(exc), "mensaje": str(exc)},
        )

    @app.exception_handler(PermissionDeniedError)
    async def permission_denied_handler(request: Request, exc: PermissionDeniedError):
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"success": False, "error": str(exc), "mensaje": str(exc)},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        errors = exc.errors()
        first_msg = errors[0].get("msg", "Datos de entrada inválidos") if errors else "Datos inválidos"
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "error": f"Error de validación: {first_msg}",
                "mensaje": f"Error de validación: {first_msg}",
                "detalles": errors,
            },
        )
