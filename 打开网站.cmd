@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================
echo   每日简报 · 本地网站
echo ============================================
echo.

where python >nul 2>&1
if errorlevel 1 (
  echo [错误] 未找到 python，请先安装 Python 并勾选 Add to PATH。
  echo.
  pause
  exit /b 1
)

echo [1/3] 正在抓取最新内容（约 5 秒，失败则直接用上次内容）...
python scripts\fetch_news.py --quiet
if errorlevel 1 echo       [提示] 本次抓取未成功，将显示上一次生成的内容。

echo [2/3] 取本机局域网地址...
for /f "delims=" %%i in ('python scripts\lan_ip.py 2^>nul') do set "LANIP=%%i"

echo [3/3] 启动网站服务...
echo.
echo    电脑上打开：  http://localhost:8080
if defined LANIP echo    手机上打开：  http://!LANIP!:8080  （需同一 WiFi）
echo.
echo    这个窗口不要关，关掉网站就停了。按 Ctrl+C 可停止。
echo ============================================
echo.

start "" "http://localhost:8080/"
python -m http.server 8080 --bind 0.0.0.0 --directory site

echo.
echo 网站已停止。
pause
