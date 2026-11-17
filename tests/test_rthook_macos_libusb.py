"""Tests for the PyInstaller runtime hook that exposes the bundled libusb.

The hook runs inside the frozen macOS app; here it is loaded by path, where
sys.frozen is unset, so importing it has no side effect.
"""
import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Dict

HOOK_PATH = (
    Path(__file__).resolve().parent.parent
    / "pyinstaller_hooks"
    / "rthook_macos_libusb.py"
)


def load_hook() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "rthook_macos_libusb", HOOK_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_sets_variable_when_bundled_dylib_exists(tmp_path: Path) -> None:
    hook = load_hook()
    dylib = tmp_path / "libusb-1.0.dylib"
    dylib.write_bytes(b"")
    environ: Dict[str, str] = {}

    chosen = hook.point_epson_usb_at_bundled_libusb(environ, str(tmp_path))

    assert chosen == str(dylib)
    assert environ["EPSON_USB_LIBUSB"] == str(dylib)


def test_accepts_versioned_dylib_name(tmp_path: Path) -> None:
    # realpath() of Homebrew's libusb-1.0.dylib is libusb-1.0.0.dylib, and
    # PyInstaller keeps the source basename inside Contents/Frameworks.
    hook = load_hook()
    dylib = tmp_path / "libusb-1.0.0.dylib"
    dylib.write_bytes(b"")
    environ: Dict[str, str] = {}

    chosen = hook.point_epson_usb_at_bundled_libusb(environ, str(tmp_path))

    assert chosen == str(dylib)


def test_keeps_value_chosen_by_user(tmp_path: Path) -> None:
    hook = load_hook()
    (tmp_path / "libusb-1.0.dylib").write_bytes(b"")
    environ = {"EPSON_USB_LIBUSB": "/custom/libusb.dylib"}

    chosen = hook.point_epson_usb_at_bundled_libusb(environ, str(tmp_path))

    assert chosen is None
    assert environ["EPSON_USB_LIBUSB"] == "/custom/libusb.dylib"


def test_leaves_environment_alone_without_bundled_dylib(
    tmp_path: Path,
) -> None:
    hook = load_hook()
    environ: Dict[str, str] = {}

    chosen = hook.point_epson_usb_at_bundled_libusb(environ, str(tmp_path))

    assert chosen is None
    assert "EPSON_USB_LIBUSB" not in environ
