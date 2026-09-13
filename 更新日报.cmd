@echo off
setlocal
cd /d "%~dp0"

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

echo 正在抓取最新新闻...
"%PY%" scripts\fetch_news.py %*
if errorlevel 1 (
  echo.
  echo [警告] 没抓到新闻，请检查网络后重试。
  echo.
  pause
  exit /b 1
)

echo.
echo 完成。正在打开 index.html ...
start "" "%~dp0index.html"
pause
