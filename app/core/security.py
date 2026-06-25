import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

_MAC_STRIP = re.compile(r"[^0-9a-fA-F]")
_MAC_VALID = re.compile(r"^[0-9a-f]{12}$")


# ---- Passwords ------------------------------------------------------------

def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ---- JWT ------------------------------------------------------------------

def create_access_token(subject: str, scopes: list[str] | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {"sub": subject, "scopes": scopes or [], "exp": expire, "type": "access"}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def create_refresh_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.refresh_token_expire_days
    )
    payload = {"sub": subject, "exp": expire, "type": "refresh"}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError as exc:  # pragma: no cover - thin wrapper
        raise ValueError("invalid token") from exc


# ---- API keys -------------------------------------------------------------

def generate_api_key() -> tuple[str, str, str]:
    """Returns (full_key, prefix, sha256_hash). Only the hash is stored."""
    raw = secrets.token_urlsafe(32)
    prefix = raw[:8]
    full = f"pk_{prefix}_{raw}"
    digest = hashlib.sha256(full.encode()).hexdigest()
    return full, prefix, digest


def hash_api_key(full_key: str) -> str:
    return hashlib.sha256(full_key.encode()).hexdigest()


# ---- MAC normalization ----------------------------------------------------

def normalize_mac(value: str) -> str:
    """Strip separators, lowercase, validate as 12 hex chars."""
    cleaned = _MAC_STRIP.sub("", value).lower()
    if not _MAC_VALID.match(cleaned):
        raise ValueError(f"invalid MAC address: {value!r}")
    return cleaned


def format_mac(mac: str, sep: str = ":") -> str:
    """Render normalized MAC with a separator for display / model-specific files."""
    return sep.join(mac[i : i + 2] for i in range(0, 12, 2))
