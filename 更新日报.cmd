@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

where python >nul 2>&1
if errorlevel 1 (
  echo [错误] 未找到 python，请先安装 Python 并勾选 Add to PATH。
  echo.
  pause
  exit /b 1
)

python scripts\fetch_news.py %*
if errorlevel 1 (
  echo.
  echo [警告] 未抓到任何新闻，请检查网络后重试。
  echo.
  pause
  exit /b 1
)

echo.
echo 完成。正在打开 index.html ...
start "" "%~dp0index.html"
echo.
pause
