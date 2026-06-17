@echo off
chcp 65001 > nul
echo ============================================================
echo   다제약물 응급 QR 시스템 - EXE 빌드 스크립트
echo ============================================================
echo.

REM 1) PyInstaller 설치
echo [1/4] PyInstaller 설치 확인...
pip show pyinstaller > nul 2>&1
if errorlevel 1 (
    pip install pyinstaller
) else (
    echo       이미 설치됨.
)
echo.

REM 2) DB 적재
echo [2/4] 약물 마스터 DB 적재 (Mock + DUR + 약가마스터)...
python -m app.seed
if errorlevel 1 goto error
python -m app.services.external.hira_dur_loader
if errorlevel 1 goto error
python -m app.services.external.hira_drug_price_loader
if errorlevel 1 goto error
echo.

REM 3) 빌드 캐시 정리
echo [3/4] 이전 빌드 정리...
if exist build rmdir /s /q build
if exist dist  rmdir /s /q dist
echo.

REM 4) EXE 빌드
echo [4/4] PyInstaller 빌드 시작...
pyinstaller build.spec --clean
if errorlevel 1 goto error
echo.

echo ============================================================
echo   [완료] dist\EmergencyQR.exe 생성됨
echo   배포: 이 파일 하나만 약국에 전달하면 됩니다.
echo ============================================================
pause
exit /b 0

:error
echo.
echo ============================================================
echo   [에러] 빌드 실패. 위 에러 메시지를 확인하세요.
echo ============================================================
pause
exit /b 1
