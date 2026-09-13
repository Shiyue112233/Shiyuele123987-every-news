@echo off
rem 供 Windows 计划任务调用的静默刷新脚本：不弹窗、不暂停，只写日志。
chcp 65001 >nul
cd /d "%~dp0.."

set "LOG=%~dp0..\data\refresh.log"

where python >nul 2>&1
if errorlevel 1 (
  echo [%date% %time%] 未找到 python，跳过刷新。>>"%LOG%"
  exit /b 1
)

echo [%date% %time%] 开始刷新>>"%LOG%"
python scripts\fetch_news.py --quiet >>"%LOG%" 2>&1
if errorlevel 1 (
  echo [%date% %time%] 刷新失败（退出码 %errorlevel%）>>"%LOG%"
  exit /b 1
)
echo [%date% %time%] 刷新完成>>"%LOG%"
exit /b 0
