# Generates Desktop Shortcuts for "Agent Study OS" (Start & Stop)
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$desktop = [Environment]::GetFolderPath('Desktop')
$wsh = New-Object -ComObject WScript.Shell

$pythonw = Join-Path $root '.venv\Scripts\pythonw.exe'
$launchScript = Join-Path $root 'tools\launch_hidden.py'
$stopScript = Join-Path $root 'tools\stop_service.py'
$iconPath = Join-Path $root 'assets\agentos.ico'

# 1. 启动快捷方式
$shortcutStart = $wsh.CreateShortcut((Join-Path $desktop 'Agent学习OS.lnk'))
$shortcutStart.TargetPath = $pythonw
$shortcutStart.Arguments = "`"$launchScript`""
$shortcutStart.WorkingDirectory = $root
$shortcutStart.Description = '启动 Agent 学习 OS (无窗口应用模式)'
if (Test-Path $iconPath) {
    $shortcutStart.IconLocation = "$iconPath, 0"
}
$shortcutStart.Save()

# 2. 停止快捷方式
$shortcutStop = $wsh.CreateShortcut((Join-Path $desktop '停止Agent学习OS.lnk'))
$shortcutStop.TargetPath = $pythonw
$shortcutStop.Arguments = "`"$stopScript`""
$shortcutStop.WorkingDirectory = $root
$shortcutStop.Description = '停止 Agent 学习 OS 后台服务'
$shortcutStop.Save()

Write-Output "桌面快捷方式创建完成！"
