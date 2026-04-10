# 从系统剪贴板读取位图字节；按平台分支，无 UI。支持矩阵见模块末尾说明。
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
    im = ImageGrab.grabclipboard()
    if im is None or not isinstance(im, Image.Image):
        return None
    buf = io.BytesIO()
    fmt: str = im.format or "PNG"
    if fmt.upper() not in ("PNG", "JPEG", "GIF", "WEBP"):
        fmt = "PNG"
    im.save(buf, format=fmt)
    raw = buf.getvalue()
    mt = sniff_media_type(raw)
    return (raw, mt)


def _from_darwin_pyobjc() -> tuple[bytes, str] | None:
    if sys.platform != "darwin":
        return None
    try:
        from AppKit import NSPasteboard  # type: ignore[import-untyped]
    except ImportError:
        return None
    pb = cast(Any, NSPasteboard).generalPasteboard()
    for uti in ("public.png", "public.jpeg", "public.tiff"):
        data = pb.dataForType_(uti)
        if data:
            raw = bytes(data)
            return (raw, sniff_media_type(raw))
    return None


def _from_linux_wlpaste() -> tuple[bytes, str] | None:
    if sys.platform != "linux":
        return None
    exe = shutil.which("wl-paste")
    if exe is None:
        return None
    for mime in ("image/png", "image/jpeg", "image/webp"):
        r = subprocess.run(
            [exe, "-t", mime, "--no-newline"],
            capture_output=True,
            check=False,
        )
        if r.returncode == 0 and r.stdout:
            raw = r.stdout
            return (raw, mime)
    return None


def get_clipboard_image() -> tuple[bytes, str] | None:
    """
    返回 (原始字节, media_type)，剪贴板无图或当前环境不支持时返回 None。

    支持矩阵（尽力而为）：
    - Windows / macOS / Linux：优先 Pillow ImageGrab（X11 下常可用）。
    - macOS：Pillow 失败时再试 PyObjC NSPasteboard（需安装 pyobjc-framework-Cocoa）。
    - Linux Wayland：若安装 wl-paste，在 Pillow 失败时再试。
    """
    got = _from_pil_grabclipboard()
    if got is not None:
        return got
    got = _from_darwin_pyobjc()
    if got is not None:
        return got
    got = _from_linux_wlpaste()
    if got is not None:
        return got
    return None
