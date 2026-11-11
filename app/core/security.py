from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import bcrypt
import jwt
from fastapi import HTTPException, Request, status
from app.core.config import settings


def get_signing_key() -> bytes:
    """Devuelve la clave de firma configurada exclusivamente por el entorno."""
    return settings.JWT_SECRET.encode("utf-8")


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
    """Verifica una contraseña exclusivamente contra su hash BCrypt."""
    if not plain_password:
        return False
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
    try:
        decoded = jwt.decode(token, get_signing_key(), algorithms=["HS256"])
        return decoded if isinstance(decoded, dict) else None
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
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
