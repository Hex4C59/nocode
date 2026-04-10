"""Tests for clipboard backend selection and fallback behavior."""

from __future__ import annotations

from nocode import clipboard as clipboard_module


def test_get_clipboard_image_returns_none_when_no_backend_succeeds(monkeypatch) -> None:
    monkeypatch.setattr(clipboard_module, "_from_pil_grabclipboard", lambda: None)
    monkeypatch.setattr(clipboard_module, "_from_darwin_pyobjc", lambda: None)
    monkeypatch.setattr(clipboard_module, "_from_linux_wlpaste", lambda: None)

    assert clipboard_module.get_clipboard_image() is None


def test_get_clipboard_image_uses_first_non_empty_backend(monkeypatch) -> None:
    monkeypatch.setattr(clipboard_module, "_from_pil_grabclipboard", lambda: None)
    monkeypatch.setattr(
        clipboard_module,
        "_from_darwin_pyobjc",
        lambda: (b"image-bytes", "image/png"),
    )

    def fail_if_called() -> tuple[bytes, str]:
        raise AssertionError("linux fallback should not be called")

    monkeypatch.setattr(clipboard_module, "_from_linux_wlpaste", fail_if_called)

    assert clipboard_module.get_clipboard_image() == (b"image-bytes", "image/png")
