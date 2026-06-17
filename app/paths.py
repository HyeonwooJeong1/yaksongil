"""
실행 환경(개발/PyInstaller 빌드)에 따라 경로를 다르게 반환.

PyInstaller --onefile 모드:
  - sys._MEIPASS: 임시 압축 해제 폴더 (읽기 전용)
  - sys.executable: 실제 EXE 파일 경로
  - DB는 EXE 옆 또는 %APPDATA%/EmergencyQR/ 에 저장 (쓰기 가능)
"""
import os
import sys
from pathlib import Path

IS_FROZEN = getattr(sys, "frozen", False)


def resource_dir() -> Path:
    """static 등 읽기 전용 리소스의 위치."""
    if IS_FROZEN:
        return Path(sys._MEIPASS)
    return Path(__file__).parent.parent


def user_data_dir() -> Path:
    """DB, .env 등 쓰기 가능한 사용자 데이터 위치."""
    if IS_FROZEN:
        base = Path(os.environ.get("APPDATA", Path.home())) / "EmergencyQR"
        base.mkdir(parents=True, exist_ok=True)
        return base
    return Path(__file__).parent.parent


def static_dir() -> Path:
    return resource_dir() / "static"


def db_path() -> Path:
    return user_data_dir() / "drug_master.db"


def output_dir() -> Path:
    """생성된 QR 이미지 저장 위치 (사용자 데이터)."""
    out = user_data_dir() / "output"
    out.mkdir(exist_ok=True)
    return out


def env_path() -> Path:
    """.env 파일 위치 (사용자가 직접 편집 가능한 곳)."""
    return user_data_dir() / ".env"
