"""Private file storage abstraction (D-015). Keys are server-generated; paths never come from clients."""
import re
from pathlib import Path

from django.conf import settings

KEY_RE = re.compile(r"^(evidence|generated|approved)/[0-9a-f]{32}\.(pdf|jpg|png)$")


def read_path(key) -> Path:
    if not KEY_RE.match(key or ""):
        raise ValueError("invalid storage key")
    return Path(settings.PRIVATE_STORAGE_ROOT) / key


def write_bytes(key, data):
    path = read_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".part")
    tmp.write_bytes(data)
    tmp.replace(path)
    return path


def write_upload(key, uploaded):
    path = read_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".part")
    with tmp.open("wb") as fh:
        for chunk in uploaded.chunks():
            fh.write(chunk)
    tmp.replace(path)
    return path
