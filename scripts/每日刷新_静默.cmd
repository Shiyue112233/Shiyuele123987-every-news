@echo off
rem 供 Windows 计划任务调用的静默刷新脚本：不弹窗、不暂停，只写日志。
cd /d "%~dp0.."

set "LOG=%~dp0..\data\refresh.log"

set "PY="
for %%p in (python.exe) do if not defined PY if exist "%%~$PATH:p" set "PY=%%~$PATH:p"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
if not defined PY for /d %%d in ("%LOCALAPPDATA%\Programs\Python\Python*") do if not defined PY if exist "%%~fd\python.exe" set "PY=%%~fd\python.exe"
if not defined PY (
  echo [%date% %time%] 找不到 python.exe，跳过刷新。>>"%LOG%"
  exit /b 1
)

echo [%date% %time%] 开始刷新>>"%LOG%"
"%PY%" scripts\fetch_news.py --quiet >>"%LOG%" 2>&1
if errorlevel 1 (
  echo [%date% %time%] 刷新失败。>>"%LOG%"
  exit /b 1
)
echo [%date% %time%] 刷新完成>>"%LOG%"
exit /b 0
