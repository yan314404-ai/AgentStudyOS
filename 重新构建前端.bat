@echo off
title Agent 学习 OS - 重新构建前端
cd /d "%~dp0"
cd frontend
echo 正在重新构建前端（改过前端代码后需要执行一次）...
call npm run build
if errorlevel 1 ( echo 构建失败 & pause & exit /b 1 )
echo 完成。现在可以运行 启动.bat。
pause
