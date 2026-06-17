@echo off
chcp 65001 > nul
REM ============================================================
REM  월간 배포: 보험코드 갱신 -> PWA 빌드(docs/) -> GitHub Pages 푸시
REM
REM  [사전 1회 설정 필요]
REM    git init
REM    git remote add origin https://github.com/<사용자>/<저장소>.git
REM    git add . && git commit -m "init" && git push -u origin main
REM    GitHub > Settings > Pages > Deploy from branch: main, 폴더 /docs
REM
REM  이후엔 새 "약제급여목록*.xlsx"를 폴더에 두고 이 파일을 더블클릭.
REM ============================================================
set PYTHONUTF8=1
set PY=C:\ProgramData\anaconda3\python.exe
if not exist "%PY%" set PY=python

echo [1/3] 보험코드 매핑 갱신 (약제급여목록*.xlsx)...
"%PY%" -m app.services.external.hira_benefit_loader
if errorlevel 1 goto err

echo.
echo [2/3] PWA 빌드 (docs/ 조립: 생성기 + 리더 + 서비스워커)...
"%PY%" build_pwa.py
if errorlevel 1 goto err

echo.
echo [3/3] GitHub Pages 배포 (git push)...
git add docs
git commit -m "update: 약물/보험코드 데이터 갱신 %date%"
git push
if errorlevel 1 goto err

echo.
echo ============================================================
echo   [완료] 배포 완료. 약국은 다음 접속 때 자동으로 최신본 사용.
echo ============================================================
pause
exit /b 0

:err
echo.
echo ============================================================
echo   [에러] 실패. 위 메시지를 확인하세요.
echo   - "약제급여목록*.xlsx" 가 폴더에 있는지
echo   - git 원격(origin)과 GitHub 로그인이 설정됐는지
echo ============================================================
pause
exit /b 1
