# -*- mode: python ; coding: utf-8 -*-

import argparse
import os
import os.path
import pkgutil
import subprocess
import sys
from PIL import Image, ImageDraw, ImageFont
from PyInstaller.utils.hooks import collect_submodules, collect_data_files


def create_image(png_file, text):
    x_size = 800
    y_size = 150
    font_size = 30
    img = Image.new('RGB', (x_size, y_size), color='black')
    fnt = ImageFont.truetype('arialbd.ttf', font_size)
    d = ImageDraw.Draw(img)
    shadow_offset = 2
    bbox = d.textbbox((0, 0), text, font=fnt)
    x, y = (x_size-bbox[2])/2, (y_size-bbox[3])/2
    d.text((x+shadow_offset, y+shadow_offset), text, font=fnt, fill='gray')
    d.text((x, y), text, font=fnt, fill='#baf8f8')
    img.save(png_file, 'PNG')


# PyInstaller has no splash screen on macOS, and a macOS .app must be a onedir
# build wrapped in BUNDLE() (onefile + BUNDLE is deprecated): see the
# "if not IS_MACOS" branches below. Windows and Linux builds are unchanged.
IS_MACOS = sys.platform == "darwin"
BUNDLE_ID = "io.github.ircama.epson_print_conf"


def find_homebrew_libusb():
    """Return the Homebrew libusb dylib to copy into the macOS app.

    epson_usb needs libusb on macOS; bundling it makes USB work without
    "brew install libusb" on the user's Mac. The symlink is resolved, so the
    copy is named libusb-1.0.0.dylib (pyinstaller_hooks/rthook_macos_libusb.py
    accepts both names).
    """
    prefix = subprocess.run(
        ["brew", "--prefix", "libusb"], capture_output=True, text=True
    ).stdout.strip()
    path = os.path.join(prefix, "lib", "libusb-1.0.dylib")
    if not prefix or not os.path.isfile(path):
        raise SystemExit(
            "libusb-1.0.dylib not found (tried %r); install it with: "
            "brew install libusb" % path
        )
    return os.path.realpath(path)


parser = argparse.ArgumentParser()
parser.add_argument("--default", action="store_true")
parser.add_argument("--version", action="store", default=None)
options = parser.parse_args()

PROGRAM = [ 'gui.py' ]
BASENAME = 'epson_print_conf'

# Module search path: include the current directory so that the local
# modules can be found.
PATHEX = ['.']

DATAS = [(BASENAME + '.pickle', '.')]
SPLASH_IMAGE = BASENAME + '.png'

version = (
    "ui.VERSION = '" + options.version.replace('v', '') + "'"
) if options.version else ""

if not IS_MACOS:
    create_image(
        SPLASH_IMAGE, 'Epson Printer Configuration tool loading...'
    )

SPLASH_IMPORT = "" if IS_MACOS else "import pyi_splash\n"
SPLASH_CLOSE = "" if IS_MACOS else "pyi_splash.close()\n"

if not options.default and not os.path.isfile(DATAS[0][0]):
    print("\nMissing file", DATAS[0][0], "without using the default option.")
    quit()

gui_wrapper = SPLASH_IMPORT + """import pickle
import ui
from os import path

""" + version + """
path_to_pickle = path.abspath(
    path.join(path.dirname(__file__), '""" + DATAS[0][0] + """')
)
with open(path_to_pickle, 'rb') as fp:
    conf_dict = pickle.load(fp)
app = ui.EpsonPrinterUI(conf_dict=conf_dict, replace_conf=False)
""" + SPLASH_CLOSE + """app.mainloop()
"""

if options.default:
    DATAS = []
    gui_wrapper = SPLASH_IMPORT + """import pickle
import ui
from os import path

""" + version + """
app = ui.main()
""" + SPLASH_CLOSE + """app.mainloop()
"""

with open(PROGRAM[0], 'w') as file:
    file.write(gui_wrapper)

# black submodules: https://github.com/pyinstaller/pyinstaller/issues/8270
black_submodules = collect_submodules('black')
blib2to3_submodules = collect_submodules('blib2to3')

# "black" data files: https://github.com/pyinstaller/pyinstaller/issues/8270
blib2to3_data = collect_data_files('blib2to3')

# mypyc-compiled wheels (tomli, black) import a top-level helper module named
# "<hash>__mypyc" that PyInstaller does not detect, and the hash changes with
# every release: the fixed names below go stale. Without it the frozen app
# dies at start-up with "No module named 'c787785866c7b801238d__mypyc'"
# (tomli 2.5.0). Collect whatever helpers are installed at build time.
mypyc_helpers = sorted(
    module.name for module in pkgutil.iter_modules()
    if module.name.endswith('__mypyc')
)

epson_usb_submodules = [
    name for name in collect_submodules('epson_usb')
    if not name.startswith('epson_usb.tests')
] + [
    # Our own bridge to that library: the USB-capable EpsonPrinter subclass.
    'epson_usb_bridge',
]

a = Analysis(
    PROGRAM,
    pathex=PATHEX,
    binaries=[(find_homebrew_libusb(), '.')] if IS_MACOS else [],
    datas=DATAS + blib2to3_data,  # the latter required by black
    hiddenimports=[
        'tk_date_entry',  # DateEntry widget used by the GUI (PyPI: tk-date-entry)
        'babel.numbers',
        # The following modules are needed by "black": https://github.com/pyinstaller/pyinstaller/issues/8270
        '30fcd23745efe32ce681__mypyc',
        '3c22db458360489351e4__mypyc',
        '6b397dd64e00b5aff23d__mypyc', 'click', 'json', 'platform',
        'mypy_extensions', 'pathspec', '_black_version', 'platformdirs'
    ] + mypyc_helpers + epson_usb_submodules
      + black_submodules + blib2to3_submodules,  # the last two required by black
    hookspath=[],
    hooksconfig={},
    runtime_hooks=(
        ['pyinstaller_hooks/rthook_macos_libusb.py'] if IS_MACOS else []
    ),
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)
if not IS_MACOS:
    splash = Splash(
        SPLASH_IMAGE,
        binaries=a.binaries,
        datas=a.datas,
        text_pos=None,
        text_size=12,
        minify_script=True,
        always_on_top=True,
    )

    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        splash,
        splash.binaries,
        [],
        name=BASENAME,
        debug=False,  # Setting to True gives you progress messages from the executable (for console=False there will be annoying MessageBoxes on Windows).
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=options.default,  # On Windows or Mac OS governs whether to use the console executable or the windowed executable. Always True on Linux/Unix (always console executable - it does not matter there).
        disable_windowed_traceback=False,  # Disable traceback dump of unhandled exception in windowed (noconsole) mode (Windows and macOS only)
        hide_console='hide-early', # Windows only. In console-enabled executable, hide or minimize the console window ('hide-early', 'minimize-early', 'hide-late', 'minimize-late')
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name=BASENAME,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,  # UPX breaks code signatures on macOS
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )
    coll = COLLECT(
        exe, a.binaries, a.datas, strip=False, upx=False, name=BASENAME
    )
    app = BUNDLE(
        coll,
        name=BASENAME + '.app',
        icon=None,
        bundle_identifier=BUNDLE_ID,
        version=options.version.replace('v', '') if options.version else None,
        info_plist={'NSHighResolutionCapable': True},
    )

if not IS_MACOS:
    os.remove(SPLASH_IMAGE)
os.remove(PROGRAM[0])
