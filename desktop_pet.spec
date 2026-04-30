# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import sys

block_cipher = None

PYTHON_ROOT = Path(sys.base_prefix)
TCL_ROOT = PYTHON_ROOT / 'tcl'
DLL_ROOT = PYTHON_ROOT / 'DLLs'

datas = []
binaries = []

if (TCL_ROOT / 'tcl8.6').is_dir():
    datas.append((str(TCL_ROOT / 'tcl8.6'), '_tcl_data'))
if (TCL_ROOT / 'tk8.6').is_dir():
    datas.append((str(TCL_ROOT / 'tk8.6'), '_tk_data'))
if (TCL_ROOT / 'tcl8').is_dir():
    datas.append((str(TCL_ROOT / 'tcl8'), 'tcl8'))

if (DLL_ROOT / 'tcl86t.dll').is_file():
    binaries.append((str(DLL_ROOT / 'tcl86t.dll'), '.'))
if (DLL_ROOT / 'tk86t.dll').is_file():
    binaries.append((str(DLL_ROOT / 'tk86t.dll'), '.'))

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        'win32gui', 'win32con',
        'psutil',
        'tkinter', '_tkinter', 'tkinter.messagebox', 'tkinter.filedialog', 'tkinter.ttk',
        'PIL', 'PIL.Image',
        'requests', 'requests.adapters', 'requests.auth',
        'backend_client',
    ],
    hookspath=['hooks'],
    hooksconfig={},
    runtime_hooks=['rthooks/pyi_rth_tk_fix.py'],
    excludes=['edge_tts', 'pygame'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='desktop_pet',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/pixel_cat_icon.ico',
)
