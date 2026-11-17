"""PyInstaller runtime hook: let epson_usb find the libusb in the macOS app.

epson_usb.backends.libusb.libusb_library_path() looks in find_library() and in
the Homebrew/MacPorts directories, never inside a frozen bundle; it does honour
EPSON_USB_LIBUSB first. The spec copies libusb into the bundle
(Contents/Frameworks == sys._MEIPASS), and this hook points the variable at it
before ui.py runs, unless the user already chose a library.

Example (what the frozen app does at start-up):
    point_epson_usb_at_bundled_libusb(os.environ, sys._MEIPASS)
"""
import os
import sys
from typing import MutableMapping, Optional

#: Same pair as epson_usb's _LIBRARY_NAMES["darwin"]: PyInstaller keeps the
#: source basename, and Homebrew's libusb-1.0.dylib is a symlink to the .0.0
#: one.
BUNDLED_LIBUSB_NAMES = ("libusb-1.0.dylib", "libusb-1.0.0.dylib")
LIBUSB_ENV_VAR = "EPSON_USB_LIBUSB"


def point_epson_usb_at_bundled_libusb(
    environ: MutableMapping[str, str], bundle_dir: str
) -> Optional[str]:
    """Set EPSON_USB_LIBUSB to the bundled dylib; return it, or None.

    None means the environment was left untouched: the user already chose a
    library, or there is no libusb in bundle_dir.
    """
    if environ.get(LIBUSB_ENV_VAR):
        return None
    for name in BUNDLED_LIBUSB_NAMES:
        candidate = os.path.join(bundle_dir, name)
        if os.path.isfile(candidate):
            environ[LIBUSB_ENV_VAR] = candidate
            return candidate
    return None


if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    point_epson_usb_at_bundled_libusb(os.environ, sys._MEIPASS)
