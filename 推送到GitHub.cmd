@echo off
setlocal enabledelayedexpansion
title 发布每日简报到 GitHub Pages
cd /d "%~dp0"

echo ============================================================
echo   把「每日简报」发布到 GitHub Pages（手机可看）
echo ============================================================
echo.

rem ---------- 找 git.exe：PATH 里没有就用常见安装位置，再不行用 Codex 内置运行时 ----------
set "GITEXE="
for %%g in (git.exe) do if not defined GITEXE if exist "%%~$PATH:g" set "GITEXE=%%~$PATH:g"
if not defined GITEXE if exist "%ProgramFiles%\Git\cmd\git.exe" set "GITEXE=%ProgramFiles%\Git\cmd\git.exe"
if not defined GITEXE if exist "%ProgramFiles(x86)%\Git\cmd\git.exe" set "GITEXE=%ProgramFiles(x86)%\Git\cmd\git.exe"
if not defined GITEXE if exist "%LOCALAPPDATA%\Programs\Git\cmd\git.exe" set "GITEXE=%LOCALAPPDATA%\Programs\Git\cmd\git.exe"
if not defined GITEXE for /d %%d in ("%USERPROFILE%\.cache\codex-runtimes\*") do if not defined GITEXE if exist "%%~fd\dependencies\native\git\cmd\git.exe" set "GITEXE=%%~fd\dependencies\native\git\cmd\git.exe"
if not defined GITEXE (
  echo [错误] 找不到 git.exe。
  echo        请先安装 Git for Windows: https://git-scm.com/download/win
  echo.
  pause
  exit /b 1
)
echo 使用 git: %GITEXE%
echo.

rem ---------- 找 python.exe（找不到就跳过抓取，用现有内容发布）----------
set "PY="
for %%p in (python.exe) do if not defined PY if exist "%%~$PATH:p" set "PY=%%~$PATH:p"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
if not defined PY for /d %%d in ("%LOCALAPPDATA%\Programs\Python\Python*") do if not defined PY if exist "%%~fd\python.exe" set "PY=%%~fd\python.exe"

echo [1/6] 抓取最新新闻...
if defined PY (
  "%PY%" scripts\fetch_news.py --quiet
  if errorlevel 1 echo       本次抓取未成功，改用现有内容发布。
) else (
  echo       未找到 python，跳过抓取，直接发布现有内容。
)

echo [2/6] 处理目录所有权...
"%GITEXE%" config --global --add safe.directory "%CD%" >nul 2>&1
"%GITEXE%" -c safe.directory=* config core.autocrlf false >nul 2>&1

echo [3/6] 准备仓库...
if exist ".git" (
  echo       已有仓库，跳过初始化。
) else (
  "%GITEXE%" -c safe.directory=* init -b main >nul
  echo       已初始化。
)
"%GITEXE%" -c safe.directory=* config user.name "daily-brief" >nul 2>&1
"%GITEXE%" -c safe.directory=* config user.email "daily-brief@users.noreply.github.com" >nul 2>&1

echo [4/6] 提交内容...
"%GITEXE%" -c safe.directory=* add -A
"%GITEXE%" -c safe.directory=* diff --cached --quiet
if errorlevel 1 (
  "%GITEXE%" -c safe.directory=* commit -q -m "更新简报 %date%"
  echo       已提交。
) else (
  echo       没有新变化。
)

echo.
echo [5/6] 远程仓库地址
set "TMPF=%TEMP%\codex-news-remote.txt"
del "%TMPF%" >nul 2>&1
"%GITEXE%" -c safe.directory=* remote get-url origin >"%TMPF%" 2>nul
set "CUR="
if exist "%TMPF%" for /f "usebackq delims=" %%i in ("%TMPF%") do set "CUR=%%i"
if defined CUR echo       当前：!CUR!
set "REPO_URL="
set /p "REPO_URL= 直接回车用当前地址，或粘贴新地址后回车："
if not defined REPO_URL set "REPO_URL=!CUR!"
if not defined REPO_URL (
  echo [错误] 没有仓库地址。请先到 GitHub 新建一个空仓库，再把地址粘进来。
  echo.
  pause
  exit /b 1
)

"%GITEXE%" -c safe.directory=* remote get-url origin >nul 2>&1
if errorlevel 1 (
  "%GITEXE%" -c safe.directory=* remote add origin "!REPO_URL!"
) else (
  "%GITEXE%" -c safe.directory=* remote set-url origin "!REPO_URL!"
)

echo.
echo [6/7] 同步远端（云端每天也会自己提交，先并入再推）
"%GITEXE%" -c safe.directory=* fetch origin main >nul 2>&1
if errorlevel 1 (
  echo       取不到远端（网络问题），跳过同步。
) else (
  "%GITEXE%" -c safe.directory=* rev-parse --verify origin/main >nul 2>&1
  if not errorlevel 1 (
    "%GITEXE%" -c safe.directory=* merge -X ours origin/main --no-edit >nul 2>&1
    if errorlevel 1 (
      echo       自动合并没成功，已放弃合并（保持本地内容），稍后按提示重跑。
      "%GITEXE%" -c safe.directory=* merge --abort >nul 2>&1
    ) else (
      echo       已与远端同步（保留本地最新内容）。
    )
  )
)

echo.
echo [7/7] 开始推送（首次会弹出浏览器让你登录 GitHub，点同意即可）
echo.
"%GITEXE%" -c safe.directory=* push -u origin main
if errorlevel 1 (
  echo.
  echo [失败] 常见原因：
  echo    1^) 仓库地址粘贴错了
  echo    2^) 浏览器授权没完成 —— 重跑本脚本，按弹窗点同意
  echo    3^) 仓库不是空的 —— 新建仓库时不要勾 README / .gitignore / license
  echo.
  pause
  exit /b 1
)

echo.
echo ============================================================
echo   推送完成！
echo ============================================================
echo.
echo   最后两步（只需做一次）：
echo     1. 打开仓库页面 -^> Settings -^> 左侧 Pages
echo        Build and deployment -^> Source 选 "GitHub Actions"
echo     2. 打开仓库 Actions 页 -^> 每日更新简报 -^> Run workflow
echo.
echo   之后每天北京时间 06:30 云端自动更新。
echo.
pause
