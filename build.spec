# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for 다제약물 응급 QR 시스템.
빌드: pyinstaller build.spec --clean
결과: dist/EmergencyQR.exe (단일 파일)
"""
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

# EXE에 포함될 데이터 파일
datas = [
    ("static",          "static"),
    ("drug_master.db",  "."),
    (".env.example",    "."),
]

# uvicorn/fastapi는 동적 import가 많아 hidden import 필요
hiddenimports = (
    collect_submodules("uvicorn") +
    collect_submodules("fastapi") +
    collect_submodules("pydantic") +
    [
        "email_validator",
        "qrcode.image.pil",
    ]
)

a = Analysis(
    ["run_app.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "numpy",
        "pandas",
        "scipy",
    ],
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
    name="EmergencyQR",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,          # True = 콘솔 창 표시 (서버 로그 확인용)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,             # 추후 .ico 파일 추가 시 경로 지정
)
