# Generates Desktop Shortcut for "Agent Study OS"
#
# 只创建一个启动快捷方式。关闭服务不再用桌面图标：网页「设置 → 关闭服务」里点一下即可
# （后端 POST /api/shutdown）。这样桌面只留一个图标，不会出现两个长得一样的入口。
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$desktop = [Environment]::GetFolderPath('Desktop')
$wsh = New-Object -ComObject WScript.Shell

$pythonw = Join-Path $root '.venv\Scripts\pythonw.exe'
$launchScript = Join-Path $root 'tools\launch_hidden.py'
$iconPath = Join-Path $root 'assets\agentos.ico'

# 启动快捷方式
$shortcutStart = $wsh.CreateShortcut((Join-Path $desktop 'Agent学习OS.lnk'))
$shortcutStart.TargetPath = $pythonw
$shortcutStart.Arguments = "`"$launchScript`""
$shortcutStart.WorkingDirectory = $root
$shortcutStart.Description = '启动 Agent 学习 OS (无窗口应用模式)'
if (Test-Path $iconPath) {
    $shortcutStart.IconLocation = "$iconPath, 0"
}
$shortcutStart.Save()

# 清掉旧版遗留的「停止」快捷方式（关闭服务已移到网页设置页）
$oldStop = Join-Path $desktop '停止Agent学习OS.lnk'
if (Test-Path $oldStop) {
    Remove-Item $oldStop -Force
    Write-Output "已移除旧版「停止Agent学习OS」快捷方式"
}

Write-Output "桌面快捷方式创建完成！关闭服务请在网页「设置 → 关闭服务」里操作。"
