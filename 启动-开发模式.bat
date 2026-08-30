@echo off
title Agent 学习 OS - 开发模式
cd /d "%~dp0"
set ROOT=%CD%
set VENV=%ROOT%\.venv
set BACKEND=%ROOT%\backend
set FRONTEND=%ROOT%\frontend

echo 开发模式：前端热更新 + 后端自动重载。
echo 首次运行请先执行 启动.bat 完成依赖安装。

if not exist "%VENV%\Scripts\python.exe" ( echo 请先运行一次 启动.bat & pause & exit /b 1 )
if not exist "%FRONTEND%\node_modules" ( echo 请先运行一次 启动.bat & pause & exit /b 1 )

echo [1/2] 启动后端（热重载）
start "AgentOS-后端" cmd /k ""%VENV%\Scripts\python.exe" -m uvicorn main:app --app-dir "%BACKEND%" --host 127.0.0.1 --port 8000 --reload"
ping -n 3 127.0.0.1 >nul

echo [2/2] 启动前端（Vite Dev Server）
start "AgentOS-前端" cmd /k "cd /d "%FRONTEND%" && npm run dev"

echo.
echo 前端: http://127.0.0.1:5173   （改动自动刷新）
echo 后端: http://127.0.0.1:8000
echo 关闭两个新窗口即可退出。此窗口可以关闭。
pause
