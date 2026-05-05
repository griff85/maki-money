# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

playwright_datas, playwright_binaries, playwright_hiddenimports = collect_all('playwright')

a = Analysis(
    ['maki_main.py'],
    pathex=[],
    binaries=playwright_binaries,
    datas=playwright_datas + [
        ('small_maki_money.png', '.'),
        ('maki_money_logo.png', '.'),
    ],
    hiddenimports=playwright_hiddenimports + ['greenlet'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MakiBot',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='maki_money_logo.png',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MakiBot',
)
