@echo off
chcp 65001 >nul
title Creator Agent - Public Link
cd /d "%~dp0"

REM 비밀번호 미설정 시 공개 중단 (config.json의 "password" 값 확인)
findstr /C:"\"password\": \"\"" config.json >nul 2>nul
if not errorlevel 1 (
  echo.
  echo  [!] config.json 의 "password" 가 비어 있습니다.
  echo      공개 링크는 누구나 접속할 수 있으므로, 먼저 비밀번호를 설정하세요.
  echo      예:  "password": "내비밀번호123"
  echo.
  pause
  exit /b 1
)

REM 에이전트 서버 시작 (별도 창)
start "Creator Agent" cmd /c start.bat

REM cloudflared 준비 (없으면 자동 다운로드)
set CF=cloudflared.exe
where cloudflared >nul 2>nul && set CF=cloudflared
if "%CF%"=="cloudflared.exe" if not exist cloudflared.exe (
  echo cloudflared 다운로드 중... (최초 1회)
  curl -L -o cloudflared.exe https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe
  if errorlevel 1 (
    echo [!] 다운로드 실패. 인터넷 연결을 확인하세요.
    pause
    exit /b 1
  )
)

echo.
echo  ============================================================
echo   아래에 나오는  https://xxxx.trycloudflare.com  주소가
echo   공개 링크입니다. 폰/외부에서 그 주소로 접속하세요.
echo   (이 창을 닫으면 공개 링크가 꺼집니다)
echo  ============================================================
echo.
%CF% tunnel --url http://localhost:8800
pause
