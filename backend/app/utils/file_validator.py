"""Upload validation: extension, size, safe filenames, path-traversal protection."""
import re
from pathlib import Path
from app.config import settings


class FileValidationError(ValueError):
    pass


def safe_filename(name: str) -> str:
    """Strip directories and unsafe characters from a user-supplied filename."""
    name = Path(name.replace("\\", "/")).name
    name = re.sub(r"[^A-Za-z0-9._ -]", "_", name).strip(" .")
    if not name:
        raise FileValidationError("Invalid file name.")
    return name[:150]


def validate_upload(filename: str, size_bytes: int) -> str:
    """Returns the cleaned filename or raises FileValidationError."""
    clean = safe_filename(filename or "")
    ext = Path(clean).suffix.lower()
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise FileValidationError(f"Unsupported file type '{ext}'. Allowed: PDF, DOCX, TXT.")
    if size_bytes == 0:
        raise FileValidationError("The file is empty.")
    if size_bytes > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
        raise FileValidationError(f"File exceeds the {settings.MAX_FILE_SIZE_MB} MB limit.")
    return clean


def resolve_inside(base: Path, *parts: str) -> Path:
    """Join paths and guarantee the result stays inside `base` (blocks ../ traversal)."""
    target = base.joinpath(*parts).resolve()
    if base.resolve() not in target.parents and target != base.resolve():
        raise FileValidationError("Illegal path.")
    return target
