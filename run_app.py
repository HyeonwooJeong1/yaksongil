"""
PyInstaller 빌드용 진입점.

실행 흐름:
1. 사용자 데이터 폴더 초기화 (.env, drug_master.db 복사)
2. uvicorn 백그라운드 실행
3. 브라우저 자동 오픈
4. Ctrl+C 또는 콘솔 창 닫을 때까지 대기
"""
import shutil
import sys
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn

from app.paths import IS_FROZEN, db_path, env_path, resource_dir, user_data_dir

HOST = "127.0.0.1"
PORT = 8000


def setup_user_data():
    """
    PyInstaller 모드: 임베드된 초기 DB와 .env.example을 사용자 폴더로 복사.
    이미 있으면 덮어쓰지 않음 (사용자 추가 데이터 보존).
    """
    if not IS_FROZEN:
        return

    base = user_data_dir()
    print(f"[INFO] 사용자 데이터 폴더: {base}")

    # 초기 DB 복사 (한 번만)
    target_db = db_path()
    if not target_db.exists():
        source_db = resource_dir() / "drug_master.db"
        if source_db.exists():
            shutil.copy2(source_db, target_db)
            print(f"[INFO] 초기 DB 복사 완료: {target_db}")

    # .env 템플릿 복사 (한 번만)
    target_env = env_path()
    if not target_env.exists():
        source_env = resource_dir() / ".env.example"
        if source_env.exists():
            shutil.copy2(source_env, target_env)
            print(f"[INFO] .env 템플릿 생성: {target_env}")
            print("       e약은요 API 키를 사용하려면 위 파일을 편집하세요.")


def open_browser_delayed():
    """서버 부팅 후 브라우저 오픈 (1.5초 대기)."""
    time.sleep(1.5)
    url = f"http://{HOST}:{PORT}"
    print(f"[INFO] 브라우저 오픈: {url}")
    webbrowser.open(url)


def main():
    print("=" * 60)
    print("  다제약물 응급 QR 시스템")
    print(f"  http://{HOST}:{PORT}")
    print("=" * 60)
    print()

    setup_user_data()

    # 백그라운드에서 브라우저 오픈
    threading.Thread(target=open_browser_delayed, daemon=True).start()

    print("[INFO] 서버 시작 중... (이 창을 닫으면 서버가 종료됩니다)")
    print()

    try:
        uvicorn.run(
            "app.main:app",
            host=HOST,
            port=PORT,
            reload=False,    # 빌드 환경에서는 reload 비활성
            log_level="info",
        )
    except KeyboardInterrupt:
        print("\n[INFO] 사용자 종료 요청")
        sys.exit(0)


if __name__ == "__main__":
    main()
