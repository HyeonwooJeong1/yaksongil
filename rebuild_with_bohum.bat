@echo off
chcp 65001 > nul
REM ============================================================
REM  약제급여목록(xlsx) -> 보험코드 매핑 -> qr_generator.html 재빌드
REM  사용법: 최신 "약제급여목록*.xlsx"를 이 폴더에 두고 더블클릭.
REM  (xlsx 파싱에 openpyxl 필요 -> conda python 사용)
REM ============================================================
set PYTHONUTF8=1
set PY=C:\ProgramData\anaconda3\python.exe
if not exist "%PY%" set PY=python

echo ============================================================
echo   보험코드 매핑 갱신 + qr_generator.html 재빌드
echo ============================================================
echo.

echo [1/2] 약제급여목록 -^> 보험코드 매핑 생성...
"%PY%" -m app.services.external.hira_benefit_loader
if errorlevel 1 goto err
echo.

echo [2/2] qr_generator.html 재빌드...
"%PY%" build_static.py
if errorlevel 1 goto err
echo.

echo ============================================================
echo   [완료] dist\qr_generator.html 갱신 완료
echo   이 파일을 약국에 재배포하세요.
echo ============================================================
pause
exit /b 0

:err
echo.
echo ============================================================
echo   [에러] 실패. 위 메시지를 확인하세요.
echo   - "약제급여목록*.xlsx" 파일이 이 폴더에 있는지 확인
echo   - conda python 경로(%PY%)가 맞는지 확인
echo ============================================================
pause
exit /b 1
