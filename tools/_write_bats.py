# -*- coding: utf-8 -*-
"""把启动脚本按 GBK 编码写盘 —— 中文 Windows 的 cmd 原生按 GBK 解析 bat，
比 UTF-8+chcp 65001 可靠。运行一次后此脚本可删。
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

BAT_MAIN = """@echo off
setlocal enabledelayedexpansion
title Agent 学习 OS - 一键启动
cd /d "%~dp0"

set ROOT=%CD%
set VENV=%ROOT%\\.venv
set BACKEND=%ROOT%\\backend
set FRONTEND=%ROOT%\\frontend

echo ==============================================
echo   [Agent 学习 OS] 一键启动
echo   首次运行会自动安装依赖，请耐心等待
echo ==============================================

rem ---------- 1. 检查 Python ----------
where python >nul 2>nul
if errorlevel 1 (
  echo [错误] 没有找到 Python。
  echo   请先安装 Python 3.10+，安装时勾选 "Add Python to PATH"。
  echo   下载地址: https://www.python.org/downloads/
  pause
  exit /b 1
)

rem ---------- 2. 创建虚拟环境 ----------
if not exist "%VENV%\\Scripts\\python.exe" (
  echo [1/5] 创建 Python 虚拟环境...
  python -m venv "%VENV%"
  if errorlevel 1 ( echo [错误] 创建虚拟环境失败 & pause & exit /b 1 )
) else (
  echo [1/5] 虚拟环境已存在，跳过
)

rem ---------- 3. 安装后端依赖 ----------
if not exist "%VENV%\\Lib\\site-packages\\fastapi" (
  echo [2/5] 安装后端依赖 fastapi / uvicorn ...
  "%VENV%\\Scripts\\python.exe" -m pip install --disable-pip-version-check -r "%BACKEND%\\requirements.txt"
  if errorlevel 1 ( echo [错误] 后端依赖安装失败，请检查网络后重试 & pause & exit /b 1 )
) else (
  echo [2/5] 后端依赖已就绪
)

rem ---------- 4. 检查 Node / npm ----------
where node >nul 2>nul
if errorlevel 1 (
  echo [错误] 没有找到 Node.js。
  echo   请安装 Node 18+（推荐 LTS）：https://nodejs.org/
  pause
  exit /b 1
)
where npm >nul 2>nul
if errorlevel 1 ( echo [错误] 没有找到 npm & pause & exit /b 1 )

rem ---------- 5. 安装前端依赖 ----------
if not exist "%FRONTEND%\\node_modules" (
  echo [3/5] 安装前端依赖（npm install）...
  pushd "%FRONTEND%"
  call npm install --no-audit --no-fund
  if errorlevel 1 ( echo [错误] npm install 失败，请检查网络后重试 & popd & pause & exit /b 1 )
  popd
) else (
  echo [3/5] 前端依赖已就绪
)

rem ---------- 6. 构建前端 ----------
if not exist "%FRONTEND%\\dist" (
  echo [4/5] 构建前端...
  pushd "%FRONTEND%"
  call npm run build
  if errorlevel 1 ( echo [错误] 前端构建失败 & popd & pause & exit /b 1 )
  popd
) else (
  echo [4/5] 前端已构建（需重新构建请删除 frontend\\dist 或运行 重新构建前端.bat）
)

rem ---------- 7. 启动服务并打开浏览器 ----------
echo [5/5] 启动服务，请稍候...
echo   地址: http://127.0.0.1:8000

rem 后端单独开一个窗口跑，主脚本负责等它起来后开浏览器
start "AgentOS-后端服务" cmd /k ""%VENV%\\Scripts\\python.exe" -m uvicorn main:app --app-dir "%BACKEND%" --host 127.0.0.1 --port 8000"

set TRY=0
:waitloop
set /a TRY+=1
curl -s -o nul http://127.0.0.1:8000/api/health >nul 2>nul
if not errorlevel 1 goto open_browser
if %TRY% geq 60 (
  echo 服务启动超时，请手动打开浏览器访问 http://127.0.0.1:8000
  goto done
)
ping -n 2 127.0.0.1 >nul
goto waitloop

:open_browser
start "" http://127.0.0.1:8000

:done
echo.
echo 服务已启动。关闭窗口「AgentOS-后端服务」即可停止程序。
pause
"""

BAT_DEV = """@echo off
title Agent 学习 OS - 开发模式
cd /d "%~dp0"
set ROOT=%CD%
set VENV=%ROOT%\\.venv
set BACKEND=%ROOT%\\backend
set FRONTEND=%ROOT%\\frontend

echo 开发模式：前端热更新 + 后端自动重载。
echo 首次运行请先执行 启动.bat 完成依赖安装。

if not exist "%VENV%\\Scripts\\python.exe" ( echo 请先运行一次 启动.bat & pause & exit /b 1 )
if not exist "%FRONTEND%\\node_modules" ( echo 请先运行一次 启动.bat & pause & exit /b 1 )

echo [1/2] 启动后端（热重载）
start "AgentOS-后端" cmd /k ""%VENV%\\Scripts\\python.exe" -m uvicorn main:app --app-dir "%BACKEND%" --host 127.0.0.1 --port 8000 --reload"
ping -n 3 127.0.0.1 >nul

echo [2/2] 启动前端（Vite Dev Server）
start "AgentOS-前端" cmd /k "cd /d "%FRONTEND%" && npm run dev"

echo.
echo 前端: http://127.0.0.1:5173   （改动自动刷新）
echo 后端: http://127.0.0.1:8000
echo 关闭两个新窗口即可退出。此窗口可以关闭。
pause
"""

BAT_BACKUP = """@echo off
title Agent 学习 OS - 备份数据库
cd /d "%~dp0"

set BAK=backups
if not exist "%BAK%" mkdir "%BAK%"

for /f "tokens=1-6 delims=/:. " %%a in ("%date% %time%") do set TS=%%a%%b%%c_%%d%%e%%f

if not exist "backend\\data\\agent_study.db" (
  echo 数据库不存在（还没运行过程序？），无需备份。
  pause
  exit /b 1
)

copy /y "backend\\data\\agent_study.db" "%BAK%\\agent_study_%TS%.db" >nul
echo 已备份到: %BAK%\\agent_study_%TS%.db
echo 恢复方法：把备份文件复制回 backend\\data\\agent_study.db 即可。
pause
"""

BAT_REBUILD = """@echo off
title Agent 学习 OS - 重新构建前端
cd /d "%~dp0"
cd frontend
echo 正在重新构建前端（改过前端代码后需要执行一次）...
call npm run build
if errorlevel 1 ( echo 构建失败 & pause & exit /b 1 )
echo 完成。现在可以运行 启动.bat。
pause
"""

FILES = {
    "启动.bat": BAT_MAIN,
    "启动-开发模式.bat": BAT_DEV,
    "备份数据库.bat": BAT_BACKUP,
    "重新构建前端.bat": BAT_REBUILD,
}

for name, content in FILES.items():
    (ROOT / name).write_text(content, encoding="gbk")
    print(f"wrote {name} ({len(content)} chars, GBK)")

print("done")
