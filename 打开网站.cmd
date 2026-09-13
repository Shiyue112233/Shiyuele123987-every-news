@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================
echo   每日简报 · 本地网站（手机同 WiFi 可看）
echo ============================================
echo.

set "PY="
for %%p in (python.exe) do if not defined PY if exist "%%~$PATH:p" set "PY=%%~$PATH:p"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
if not defined PY for /d %%d in ("%LOCALAPPDATA%\Programs\Python\Python*") do if not defined PY if exist "%%~fd\python.exe" set "PY=%%~fd\python.exe"
if not defined PY (
  echo [错误] 找不到 python.exe，请先安装 Python 并勾选 Add to PATH。
  echo.
  pause
  exit /b 1
)

echo [1/3] 抓取最新新闻（约 5 秒，失败则用上次内容）...
"%PY%" scripts\fetch_news.py --quiet
if errorlevel 1 echo       本次抓取未成功，将显示上一次生成的内容。

echo [2/3] 取本机局域网地址...
set "TMPF=%TEMP%\codex-news-lanip.txt"
del "%TMPF%" >nul 2>&1
"%PY%" scripts\lan_ip.py >"%TMPF%" 2>nul
set "LANIP="
if exist "%TMPF%" for /f "usebackq delims=" %%i in ("%TMPF%") do set "LANIP=%%i"

echo [3/3] 启动网站服务...
echo.
echo    电脑上打开：  http://localhost:8080
if defined LANIP echo    手机上打开：  http://!LANIP!:8080   （手机要和电脑在同一个 WiFi）
echo.
echo    这个窗口不要关，关掉网站就停了。按 Ctrl+C 可以停止。
echo ============================================
echo.

start "" "http://localhost:8080/"
"%PY%" -m http.server 8080 --bind 0.0.0.0 --directory site

echo.
echo 网站已停止。
pause
