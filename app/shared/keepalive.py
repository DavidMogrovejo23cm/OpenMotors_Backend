import asyncio
import logging
import httpx

from app.core.config import settings

logger = logging.getLogger("gmotors.keepalive")


async def keep_alive_loop() -> None:
    """Hace ping periódico al propio servicio en Render para evitar que entre en suspensión."""
    if not settings.RENDER_EXTERNAL_URL:
        return
    target = f"{settings.RENDER_EXTERNAL_URL.rstrip('/')}/api/health"
    logger.info(f"KeepAlive activado cada 12 minutos hacia {target}")
    while True:
        await asyncio.sleep(720)
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.get(target)
        except Exception as exc:
            logger.debug(f"KeepAlive ping ignorado: {exc}")

