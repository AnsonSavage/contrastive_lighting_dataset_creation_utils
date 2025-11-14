import os
import tempfile
from contextlib import contextmanager
from typing import Generator


@contextmanager
def temporary_payload_file(payload: bytes, suffix: str = ".bin") -> Generator[str, None, None]:
    """Write payload bytes to a temp file accessible by Blender and clean it up."""
    fd, path = tempfile.mkstemp(prefix="render_payload_", suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as tmp:
            tmp.write(payload)
        yield path
    finally:
        try:
            os.remove(path)
        except FileNotFoundError:
            print(f"Warning: Temporary payload file {path} was already removed.", flush=True)