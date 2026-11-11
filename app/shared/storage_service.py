import logging
import os
import re
import uuid
from pathlib import Path
from typing import Tuple
import requests
from fastapi import UploadFile
from app.core.config import settings

logger = logging.getLogger("openauto.storage")

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
LOCAL_UPLOAD_ROOT = Path("static/uploads")


class StorageService:
    """
    Servicio de almacenamiento de imágenes para Usuarios, Vehiculos y Productos.
    - Si SUPABASE_URL y las llaves están configuradas, sube a Supabase Storage
      (asegurando de forma idempotente que el bucket exista y sea público).
    - Si no hay configuración de Supabase (desarrollo local), almacena el archivo
      en `static/uploads/<carpeta>` y devuelve la URL pública servida por FastAPI.
    """

    def _base_url(self) -> str:
        url = (settings.SUPABASE_URL or "").strip()
        return url[:-1] if url.endswith("/") else url

    def _auth_key(self) -> str:
        srk = (settings.SUPABASE_SERVICE_ROLE_KEY or "").strip()
        return srk if srk else (settings.SUPABASE_ANON_KEY or "").strip()

    def _supabase_configured(self) -> bool:
        return bool(self._base_url() and self._auth_key())

    def validar_imagen(self, file: UploadFile, content: bytes) -> Tuple[bool, str]:
        if not content:
            return False, "El archivo está vacío"
        filename = file.filename or ""
        ext = os.path.splitext(filename.lower())[1]
        if ext not in ALLOWED_EXTENSIONS:
            return False, "El archivo debe ser una imagen (jpg, png, gif, webp)"
        if len(content) > MAX_FILE_SIZE:
            return False, "El archivo no puede ser mayor a 5MB"
        return True, "OK"

    def _ensure_bucket(self) -> None:
        if not self._supabase_configured():
            return
        bucket = settings.SUPABASE_BUCKET
        auth_key = self._auth_key()
        headers = {
            "Authorization": f"Bearer {auth_key}",
            "apikey": auth_key,
            "Content-Type": "application/json",
        }
        try:
            r = requests.get(
                f"{self._base_url()}/storage/v1/bucket/{bucket}",
                headers=headers,
                timeout=10,
            )
            if r.ok:
                requests.put(
                    f"{self._base_url()}/storage/v1/bucket/{bucket}",
                    headers=headers,
                    json={"public": True, "file_size_limit": 10485760},
                    timeout=10,
                )
                return
            requests.post(
                f"{self._base_url()}/storage/v1/bucket",
                headers=headers,
                json={
                    "id": bucket,
                    "name": bucket,
                    "public": True,
                    "file_size_limit": 10485760,
                },
                timeout=10,
            )
        except Exception as exc:
            logger.warning("[SUPABASE] ensure_bucket warning: %s", exc)

    def subir_archivo(self, file: UploadFile, content: bytes, carpeta: str) -> str:
        original_name = file.filename or "imagen.jpg"
        sanitized = re.sub(r"[^a-zA-Z0-9.-]", "_", original_name)
        nombre_archivo = f"{uuid.uuid4()}_{sanitized}"
        ruta = f"{carpeta}{nombre_archivo}"

        if self._supabase_configured():
            self._ensure_bucket()
            bucket = settings.SUPABASE_BUCKET
            auth_key = self._auth_key()
            upload_url = f"{self._base_url()}/storage/v1/object/{bucket}/{ruta}"
            content_type = file.content_type or "application/octet-stream"
            resp = requests.post(
                upload_url,
                data=content,
                headers={
                    "Authorization": f"Bearer {auth_key}",
                    "apikey": auth_key,
                    "Content-Type": content_type,
                    "x-upsert": "true",
                },
                timeout=30,
            )
            if not resp.ok:
                raise RuntimeError(f"Error de Supabase {resp.status_code}: {resp.text}")
            return f"{self._base_url()}/storage/v1/object/public/{bucket}/{ruta}"

        # Fallback local en static/uploads/
        dest_dir = LOCAL_UPLOAD_ROOT / carpeta.strip("/")
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / nombre_archivo
        dest_path.write_bytes(content)
        return f"/images/uploads/{ruta}"

    def subir_imagen_usuario(self, file: UploadFile, content: bytes) -> str:
        return self.subir_archivo(file, content, "usuarios/perfil/")

    def subir_imagen_vehiculo(self, file: UploadFile, content: bytes) -> str:
        return self.subir_archivo(file, content, "vehiculos/perfil/")

    def subir_imagen_producto(self, file: UploadFile, content: bytes) -> str:
        return self.subir_archivo(file, content, "productos/imagen/")

    def ensure_bucket(self) -> None:
        self._ensure_bucket()

    def upload_file(self, file: UploadFile, carpeta: str, prefix: str = "") -> str:
        content = file.file.read()
        folder = carpeta.strip("/") + "/"
        return self.subir_archivo(file, content, folder)

    def delete_file(self, url_imagen: str) -> None:
        self.eliminar_imagen(url_imagen)

    def eliminar_imagen(self, url_imagen: str) -> None:
        if not url_imagen or not url_imagen.strip():
            return
        if not self._supabase_configured() or not url_imagen.startswith("http"):
            return
        try:
            bucket = settings.SUPABASE_BUCKET
            token = f"/object/public/{bucket}/"
            idx = url_imagen.find(token)
            ruta = url_imagen[idx + len(token) :] if idx != -1 else url_imagen
            delete_url = f"{self._base_url()}/storage/v1/object/{bucket}/{ruta}"
            auth_key = self._auth_key()
            requests.delete(
                delete_url,
                headers={
                    "Authorization": f"Bearer {auth_key}",
                    "apikey": auth_key,
                },
                timeout=10,
            )
        except Exception as exc:
            logger.warning("[SUPABASE] No se pudo eliminar imagen anterior: %s", exc)


storage_service = StorageService()
