@echo off
title Agent 学习 OS - 备份数据库
cd /d "%~dp0"

set BAK=backups
if not exist "%BAK%" mkdir "%BAK%"

for /f "tokens=1-6 delims=/:. " %%a in ("%date% %time%") do set TS=%%a%%b%%c_%%d%%e%%f

if not exist "backend\data\agent_study.db" (
  echo 数据库不存在（还没运行过程序？），无需备份。
  pause
  exit /b 1
)

copy /y "backend\data\agent_study.db" "%BAK%\agent_study_%TS%.db" >nul
echo 已备份到: %BAK%\agent_study_%TS%.db
echo 恢复方法：把备份文件复制回 backend\data\agent_study.db 即可。
pause
