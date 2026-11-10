from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import bcrypt
import jwt
from fastapi import HTTPException, Request, status
from app.core.config import settings


def get_signing_key() -> bytes:
    """
    Compatible con la lógica de JwtUtil.java:
    Si la clave tiene menos de 64 bytes, la rellena con ceros hasta 64 bytes
    para mantener compatibilidad exacta con tokens firmados previamente.
    """
    key_bytes = settings.JWT_SECRET.encode("utf-8")
    if len(key_bytes) < 64:
        padded = bytearray(64)
        padded[: len(key_bytes)] = key_bytes
        return bytes(padded)
    return key_bytes


def is_bcrypt_hash(value: Optional[str]) -> bool:
    if not value:
        return False
    return value.startswith("$2a$") or value.startswith("$2b$") or value.startswith("$2y$")


def hash_password(password: str) -> str:
    """Genera un hash BCrypt seguro para la contraseña."""
    if not password:
        raise ValueError("La contraseña no puede estar vacía")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: Optional[str]) -> bool:
    """
    Verifica una contraseña contra su hash BCrypt.
    También soporta el flujo de login Google determinista (`gm_google_...`).
    """
    if not plain_password:
        return False
    if plain_password.startswith("gm_google_"):
        return True
    if not hashed_password:
        return False
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return plain_password == hashed_password


def create_access_token(
    id_usuario: int, nombre_usuario: str, correo: str
) -> str:
    """Genera un token JWT HS256 compatible con JwtUtil.java."""
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=settings.JWT_EXPIRATION_MINUTES)
    payload = {
        "sub": correo or nombre_usuario,
        "id_usuario": id_usuario,
        "nombre_usuario": nombre_usuario,
        "correo": correo,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(payload, get_signing_key(), algorithm="HS256")


def generar_token(correo: str) -> str:
    return create_access_token(0, correo, correo)


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decodifica y valida el token JWT."""
    for key in (get_signing_key(), settings.JWT_SECRET.encode("utf-8")):
        try:
            decoded = jwt.decode(token, key, algorithms=["HS256"])
            if isinstance(decoded, dict):
                return decoded
        except jwt.ExpiredSignatureError:
            return None
        except Exception:
            continue
    return None


def validar_token(token: str) -> Optional[str]:
    decoded = decode_access_token(token)
    return decoded.get("sub") if decoded else None


def extraer_token_de_request(request: Request) -> Optional[str]:
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:].strip()
    query_token = request.query_params.get("token")
    if query_token:
        return query_token.strip()
    return None


def require_auth(request: Request) -> str:
    token = extraer_token_de_request(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Se requiere autenticación",
        )
    correo = validar_token(token)
    if not correo:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
        )
    return correo
