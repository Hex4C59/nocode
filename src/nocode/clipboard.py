"""Read bitmap image bytes from the system clipboard across supported platforms."""

from __future__ import annotations

import io
import shutil
import subprocess
import sys
from typing import Any, cast

from nocode.messages import sniff_media_type


def _from_pil_grabclipboard() -> tuple[bytes, str] | None:
    try:
        from PIL import Image, ImageGrab
    except ImportError:
        return None
    image = ImageGrab.grabclipboard()
    if image is None or not isinstance(image, Image.Image):
        return None
    buffer = io.BytesIO()
    image_format: str = image.format or "PNG"
    if image_format.upper() not in {"PNG", "JPEG", "GIF", "WEBP"}:
        image_format = "PNG"
    image.save(buffer, format=image_format)
    raw = buffer.getvalue()
    return raw, sniff_media_type(raw)


def _from_darwin_pyobjc() -> tuple[bytes, str] | None:
    if sys.platform != "darwin":
        return None
    try:
        from AppKit import NSPasteboard  # type: ignore[import-untyped]
    except ImportError:
        return None
    pasteboard = cast(Any, NSPasteboard).generalPasteboard()
    for uti in ("public.png", "public.jpeg", "public.tiff"):
        data = pasteboard.dataForType_(uti)
        if data:
            raw = bytes(data)
            return raw, sniff_media_type(raw)
    return None


def _from_linux_wlpaste() -> tuple[bytes, str] | None:
    if sys.platform != "linux":
        return None
    executable = shutil.which("wl-paste")
    if executable is None:
        return None
    for mime in ("image/png", "image/jpeg", "image/webp"):
        result = subprocess.run(
            [executable, "-t", mime, "--no-newline"],
            capture_output=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout:
            return result.stdout, mime
    return None


def get_clipboard_image() -> tuple[bytes, str] | None:
    """Return raw bytes plus MIME type, or `None` when no bitmap is available."""
    result = _from_pil_grabclipboard()
    if result is not None:
        return result
    result = _from_darwin_pyobjc()
    if result is not None:
        return result
    result = _from_linux_wlpaste()
    if result is not None:
        return result
    return None
