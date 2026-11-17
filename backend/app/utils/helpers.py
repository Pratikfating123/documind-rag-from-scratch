import hashlib
import uuid
from datetime import datetime, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def new_id() -> str:
    return uuid.uuid4().hex


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
