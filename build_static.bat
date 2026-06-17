@echo off
chcp 65001 > nul
echo ============================================================
echo   단일 HTML 파일 빌드 (백엔드 없음)
echo ============================================================
echo.

echo [1/2] 데이터 적재 (이미 적재됐으면 빠르게 패스)...
python -m app.seed
if errorlevel 1 goto error
python -m app.services.external.hira_dur_loader
if errorlevel 1 goto error
python -m app.services.external.hira_drug_price_loader
if errorlevel 1 goto error
echo.

echo [2/2] HTML 빌드 중...
python build_static.py
if errorlevel 1 goto error
echo.

echo ============================================================
echo   [완료] dist\qr_generator.html
echo   탐색기로 dist 폴더 열기:
start "" "%CD%\dist"
echo ============================================================
pause
exit /b 0

:error
echo.
echo ============================================================
echo   [에러] 빌드 실패. 위 에러 메시지 확인.
echo ============================================================
pause
exit /b 1
