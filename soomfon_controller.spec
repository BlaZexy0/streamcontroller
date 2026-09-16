# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


project_root = Path(SPECPATH)
hiddenimports = collect_submodules("streamdeck_app.profiles")
datas = [
    (str(project_root / "config.json"), "."),
    (str(project_root / "assets" / "screensaver"), "assets/screensaver"),
]
datas += [
    (str(source), "streamdeck_app/profiles")
    for source in (project_root / "streamdeck_app" / "profiles").glob("*.py")
]

a = Analysis(
    [str(project_root / "controller.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "numpy", "matplotlib", "pytest"],
    module_collection_mode={"streamdeck_app.profiles": "pyz+py"},
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SoomfonController",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="SoomfonController",
)
