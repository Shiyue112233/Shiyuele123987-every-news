@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

rem -c safe.directory=* ：绕开「目录属于沙箱账号」导致的 dubious ownership 报错
set "GITC=git -c safe.directory=*"

echo ============================================================
echo   把「每日简报」发布到 GitHub Pages（手机可看）
echo ============================================================
echo.

where git >nul 2>&1
if errorlevel 1 (
  echo [错误] 没找到 git。请先安装 Git for Windows：https://git-scm.com/download/win
  echo.
  pause
  exit /b 1
)

if not exist ".github\workflows\daily.yml" (
  echo [警告] 没找到 .github\workflows\daily.yml
  echo         没有它就不会每天自动更新，请确认文件夹完整（含隐藏的 .github）。
  echo.
)

echo [1/6] 抓取最新内容（约 5 秒）...
where python >nul 2>&1
if not errorlevel 1 (
  python scripts\fetch_news.py --quiet
  if errorlevel 1 echo       [提示] 本次抓取未成功，会用现有内容发布。
) else (
  echo       [提示] 未找到 python，跳过抓取，直接发布现有内容。
)

echo [2/6] 处理 Git 目录所有权...
git config --global --add safe.directory "%CD%" >nul 2>&1
%GITC% config core.autocrlf false >nul 2>&1

echo [3/6] 准备仓库...
if exist ".git" (
  echo       已有仓库，跳过初始化。
) else (
  %GITC% init -b main >nul
  echo       已初始化。
)
%GITC% config user.name "daily-brief" >nul 2>&1
%GITC% config user.email "daily-brief@users.noreply.github.com" >nul 2>&1

echo [4/6] 提交内容...
%GITC% add -A
%GITC% diff --cached --quiet
if errorlevel 1 (
  %GITC% commit -q -m "更新简报 %date%"
  echo       已提交。
) else (
  echo       没有新变化。
)

echo.
echo [5/6] 远程仓库地址
set "CUR="
for /f "delims=" %%i in ('%GITC% remote get-url origin 2^>nul') do set "CUR=%%i"
if defined CUR echo       当前：!CUR!
echo       例：https://github.com/yourname/daily-brief.git
set "REPO_URL="
set /p "REPO_URL=请粘贴 GitHub 仓库地址后回车（直接回车=用当前地址）："
if "!REPO_URL!"=="" (
  if defined CUR (
    set "REPO_URL=!CUR!"
  ) else (
    echo [错误] 没有地址，无法推送。请先到 GitHub 新建一个空仓库再把地址粘进来。
    echo.
    pause
    exit /b 1
  )
)

%GITC% remote get-url origin >nul 2>&1
if errorlevel 1 (
  %GITC% remote add origin "!REPO_URL!"
) else (
  %GITC% remote set-url origin "!REPO_URL!"
)

echo.
echo [6/6] 推送到 GitHub（首次会弹浏览器让你登录，登录一次即可）
echo.
%GITC% push -u origin main
if errorlevel 1 (
  echo.
  echo [失败] 常见原因：
  echo    1^) 仓库地址粘贴错了；
  echo    2^) 没登录 GitHub —— 重跑本脚本，按弹出的窗口完成授权；
  echo    3^) 仓库不是空的 —— 新建仓库时不要勾 README / .gitignore / license。
  echo.
  pause
  exit /b 1
)

echo.
echo ============================================================
echo   推送完成！
echo ============================================================
echo.
echo   还差最后一步（只需做一次）：
echo     1. 打开你的仓库页面 -^> Settings -^> 左侧 Pages
echo     2. Source 选 "GitHub Actions"，保存
echo     3. 顶部 Actions -^> 选「每日更新简报」-^> Run workflow 手动跑一次
echo     4. 等 1 分钟，网址就固定为：
echo        https://你的用户名.github.io/仓库名/
echo.
echo   之后每天北京时间 06:30 云端自动抓取 + 自动发布，手机上收藏那个网址即可。
echo.
start "" "https://github.com"
pause
