import logging
import re
from typing import Optional
import requests
from app.core.config import settings

logger = logging.getLogger("openauto.ocr")

# Patrones típicos de placas ecuatorianas de autos (ej. ABC-1234, ABC1234, AB-1234)
PLATE_PATTERNS = [
    re.compile(r"\b([A-Z]{3}[-]?\d{3,4})\b"),           # Autos Ecuador formato estándar: ABC-1234 o ABC1234
    re.compile(r"\b([A-Z]{2,3}[-]?\d{3,4}[A-Z]?)\b"),   # General vehículo / auto
]


def _extraer_candidato_placa(texto: str) -> Optional[str]:
    if not texto:
        return None
    limpio = re.sub(r"[^A-Z0-9-]", " ", texto.upper())
    for pattern in PLATE_PATTERNS:
        match = pattern.search(limpio)
        if match:
            return match.group(1).replace("-", "")
    compacto = re.sub(r"[^A-Z0-9]", "", texto.upper())
    for pattern in PLATE_PATTERNS:
        match = pattern.search(compacto)
        if match:
            return match.group(1)
    if 5 <= len(compacto) <= 8 and any(c.isalpha() for c in compacto) and any(c.isdigit() for c in compacto):
        return compacto
    return None


class OcrService:
    """
    Servicio híbrido de reconocimiento óptico de placas (OCR) en Python:
    1) Intenta reconocimiento local directo con `ddddocr` o `pytesseract` (si están instalados).
    2) Si hay un microservicio Flask OCR externo activo en `FLASK_OCR_URL`, también lo consulta como respaldo.
    """

    def detectar_placa(self, content: bytes, filename: str = "placa.jpg") -> Optional[str]:
        if not content:
            return None

        # 1. Intentar OCR nativo con ddddocr (rápido y sin binarios externos)
        try:
            import ddddocr  # type: ignore

            ocr = ddddocr.DdddOcr(show_ad=False)
            raw_text = ocr.classification(content)
            placa = _extraer_candidato_placa(raw_text)
            if placa:
                logger.info("[OCR-PYTHON] Placa detectada con ddddocr: %s", placa)
                return placa
        except Exception as exc:
            logger.debug("[OCR-PYTHON] ddddocr no disponible o sin resultado: %s", exc)

        # 2. Intentar OCR nativo con pytesseract + PIL
        try:
            import io
            from PIL import Image  # type: ignore
            import pytesseract  # type: ignore

            img = Image.open(io.BytesIO(content))
            raw_text = pytesseract.image_to_string(img, config="--psm 7")
            placa = _extraer_candidato_placa(raw_text)
            if placa:
                logger.info("[OCR-PYTHON] Placa detectada con pytesseract: %s", placa)
                return placa
        except Exception as exc:
            logger.debug("[OCR-PYTHON] pytesseract no disponible o sin resultado: %s", exc)

        # 3. Respaldo al servidor Flask OCR externo (compatibilidad total con FlaskOcrClient.java)
        try:
            resp = requests.post(
                settings.FLASK_OCR_URL,
                files={"image": (filename or "placa.jpg", content, "image/jpeg")},
                timeout=8,
            )
            if resp.ok and isinstance(resp.json(), dict):
                placa = resp.json().get("placa")
                if placa:
                    return str(placa).strip().upper()
        except Exception as exc:
            logger.warning("[OCR-FLASK] Servidor Flask OCR no disponible: %s", exc)
            raise RuntimeError("Servidor OCR no disponible. Contacte con un administrador.") from exc

        return None

    def reconocer_placa(self, content: bytes, filename: str = "placa.jpg") -> dict:
        try:
            placa = self.detectar_placa(content, filename)
            if placa:
                return {"success": True, "placa": placa, "confianza": 0.95}
            return {"success": False, "placa": None, "error": "No se detectó ninguna placa válida"}
        except Exception as exc:
            return {"success": False, "placa": None, "error": str(exc)}


ocr_service = OcrService()
