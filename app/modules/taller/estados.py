"""Contrato único de estados de trabajo y pago de las órdenes."""
from enum import IntEnum, StrEnum
from app.core.exceptions import BusinessValidationError

class EstadoOrden(IntEnum):
    PENDIENTE = 0
    EN_PROCESO = 1
    FINALIZADA = 2
    ENTREGADA = 3

class EstadoPago(StrEnum):
    PENDIENTE = "PENDIENTE"
    PARCIAL = "PARCIAL"
    PAGADO = "PAGADO"

TRANSICIONES = {0: {1}, 1: {2}, 2: {1, 3}, 3: set()}

def validar_transicion(actual: int, nuevo: int) -> None:
    if nuevo not in TRANSICIONES:
        raise BusinessValidationError("Estado inválido: use pendiente, en proceso, finalizada o entregada")
    if actual != nuevo and nuevo not in TRANSICIONES.get(actual, set()):
        raise BusinessValidationError("Transición de trabajo no permitida")

def aplicar_estado(registro, nuevo: int) -> None:
    from datetime import datetime
    validar_transicion(registro.estado, nuevo)
    if registro.estado == nuevo:
        return
    if nuevo == EstadoOrden.ENTREGADA and registro.costo_total > 0 and registro.estado_pago != EstadoPago.PAGADO:
        raise BusinessValidationError("No se puede entregar una orden con saldo pendiente")
    registro.estado = nuevo
    if nuevo == EstadoOrden.FINALIZADA:
        registro.fecha_completado = datetime.now()
    elif nuevo == EstadoOrden.EN_PROCESO:
        registro.fecha_completado = None
    elif nuevo == EstadoOrden.ENTREGADA:
        registro.fecha_entregado = datetime.now()
