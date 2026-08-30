# Generates the Agent Study OS desktop icon (v2 - "learning" theme):
# an open white book with a gold check mark, on an emerald-green rounded square.
# The check mark echoes the app's daily check-in ("每日打卡") feature.
# Outputs:
#   assets/agentos.ico  (multi-size PNG-compressed ICO, for the shortcut)
#   assets/agentos.png  (256px preview, so you can eyeball it)
# ASCII-only on purpose so PowerShell 5.1 parses it under any codepage.
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing

$root   = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$assets = Join-Path $root 'assets'
if (-not (Test-Path $assets)) { New-Item -ItemType Directory -Path $assets | Out-Null }

$EMERALD_TOP = [System.Drawing.Color]::FromArgb(255, 52, 211, 153)   # #34d399
$EMERALD_BOT = [System.Drawing.Color]::FromArgb(255, 6, 122, 88)     # #067a58
$WHITE       = [System.Drawing.Color]::FromArgb(255, 255, 255, 255)
$PAGE_EDGE   = [System.Drawing.Color]::FromArgb(255, 224, 246, 235)  # faint mint page edge
$GOLD        = [System.Drawing.Color]::FromArgb(255, 251, 191, 36)   # #fbbf24
$DARK_GOLD   = [System.Drawing.Color]::FromArgb(255, 217, 119, 6)    # #d97706

function New-CapBitmap([int]$size) {
    $bmp = New-Object System.Drawing.Bitmap($size, $size)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $g.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
    $s = $size / 256.0
    function P([double]$v) { [int][Math]::Round($v * $s) }

    # rounded-rect background + emerald vertical gradient
    $radius = P 52
    $d = $radius * 2
    $bgPath = New-Object System.Drawing.Drawing2D.GraphicsPath
    $bgPath.AddArc(0, 0, $d, $d, 180, 90)
    $bgPath.AddArc($size - $d, 0, $d, $d, 270, 90)
    $bgPath.AddArc($size - $d, $size - $d, $d, $d, 0, 90)
    $bgPath.AddArc(0, $size - $d, $d, $d, 90, 90)
    $bgPath.CloseFigure()
    $bgRect = New-Object System.Drawing.Rectangle(0, 0, $size, $size)
    $bgBrush = New-Object System.Drawing.Drawing2D.LinearGradientBrush($bgRect, $EMERALD_TOP, $EMERALD_BOT, 90)
    $g.FillPath($bgBrush, $bgPath)

    $whiteBrush = New-Object System.Drawing.SolidBrush($WHITE)
    $goldBrush  = New-Object System.Drawing.SolidBrush($GOLD)
    $darkGoldPen = New-Object System.Drawing.Pen -ArgumentList $DARK_GOLD, ([single]([Math]::Max(1.0, (P 2))))
    $edgePen    = New-Object System.Drawing.Pen -ArgumentList $PAGE_EDGE, ([single]([Math]::Max(1.0, (P 2))))

    # ---- OPEN BOOK (V-shaped, two pages) ----
    $leftPage = New-Object 'System.Drawing.Point[]' 4
    $leftPage[0] = New-Object System.Drawing.Point -ArgumentList (P 48),(P 134)   # top-left
    $leftPage[1] = New-Object System.Drawing.Point -ArgumentList (P 128),(P 146)  # top-right (spine, slightly lower)
    $leftPage[2] = New-Object System.Drawing.Point -ArgumentList (P 128),(P 208)  # bottom-right (spine)
    $leftPage[3] = New-Object System.Drawing.Point -ArgumentList (P 48),(P 196)   # bottom-left (outer, lower = open)
    $g.FillPolygon($whiteBrush, $leftPage)
    $g.DrawPolygon($edgePen, $leftPage)

    $rightPage = New-Object 'System.Drawing.Point[]' 4
    $rightPage[0] = New-Object System.Drawing.Point -ArgumentList (P 208),(P 134) # top-right
    $rightPage[1] = New-Object System.Drawing.Point -ArgumentList (P 128),(P 146) # top-left (spine)
    $rightPage[2] = New-Object System.Drawing.Point -ArgumentList (P 128),(P 208) # bottom-left (spine)
    $rightPage[3] = New-Object System.Drawing.Point -ArgumentList (P 208),(P 196) # bottom-right (outer)
    $g.FillPolygon($whiteBrush, $rightPage)
    $g.DrawPolygon($edgePen, $rightPage)

    # book stack line under the pages (slight 3D hint)
    $stackPen = New-Object System.Drawing.Pen -ArgumentList $WHITE, ([single]([Math]::Max(2.0, (P 6))))
    $stackPen.StartCap = [System.Drawing.Drawing2D.LineCap]::Round
    $stackPen.EndCap   = [System.Drawing.Drawing2D.LineCap]::Round
    $g.DrawLine($stackPen, (P 56), (P 214), (P 200), (P 214))

    # ---- GOLD CHECK MARK rising above the book ----
    $checkPen = New-Object System.Drawing.Pen -ArgumentList $GOLD, ([single]([Math]::Max(4.0, (P 24))))
    $checkPen.StartCap = [System.Drawing.Drawing2D.LineCap]::Round
    $checkPen.EndCap   = [System.Drawing.Drawing2D.LineCap]::Round
    $checkPen.LineJoin = [System.Drawing.Drawing2D.LineJoin]::Round
    $checkPath = New-Object System.Drawing.Drawing2D.GraphicsPath
    $checkPath.AddLine((P 60),(P 96), (P 102),(P 138))
    $checkPath.AddLine((P 102),(P 138), (P 200),(P 62))
    $g.DrawPath($checkPen, $checkPath)

    # tiny highlight on the check mark
    $hlPen = New-Object System.Drawing.Pen -ArgumentList $DARK_GOLD, ([single]([Math]::Max(1.5, (P 5))))
    $hlPen.StartCap = [System.Drawing.Drawing2D.LineCap]::Round
    $hlPen.EndCap   = [System.Drawing.Drawing2D.LineCap]::Round
    $g.DrawLine($hlPen, (P 98),(P 140), (P 106),(P 148))

    $g.Dispose()
    return $bmp
}

# render each size to a PNG-compressed image record
$sizes = @(256, 64, 48, 32, 16)
$imgs = @()
foreach ($sz in $sizes) {
    $bmp = New-CapBitmap $sz
    $ms = New-Object System.IO.MemoryStream
    $bmp.Save($ms, [System.Drawing.Imaging.ImageFormat]::Png)
    $bytes = $ms.ToArray()
    if ($sz -eq 256) {
        [System.IO.File]::WriteAllBytes((Join-Path $assets 'agentos.png'), $bytes)
    }
    $imgs += [PSCustomObject]@{ w = $sz; h = $sz; data = $bytes }
    $ms.Dispose()
    $bmp.Dispose()
}

# assemble ICO (PNG-compressed entries, supported since Windows Vista/7)
$out = New-Object System.IO.MemoryStream
$bw = New-Object System.IO.BinaryWriter($out)
$bw.Write([UInt16]0)                        # reserved
$bw.Write([UInt16]1)                        # type: icon
$bw.Write([UInt16]$imgs.Count)
$offset = 6 + 16 * $imgs.Count
foreach ($im in $imgs) {
    $w = if ($im.w -eq 256) { 0 } else { $im.w }   # 0 in header means 256
    $h = if ($im.h -eq 256) { 0 } else { $im.h }
    $bw.Write([Byte]$w)
    $bw.Write([Byte]$h)
    $bw.Write([Byte]0)                       # color count
    $bw.Write([Byte]0)                       # reserved
    $bw.Write([UInt16]1)                     # planes
    $bw.Write([UInt16]32)                    # bit depth
    $bw.Write([UInt32]$im.data.Length)       # bytes in image
    $bw.Write([UInt32]$offset)               # offset to image data
    $offset += $im.data.Length
}
foreach ($im in $imgs) { $bw.Write($im.data) }
$bw.Flush()
[System.IO.File]::WriteAllBytes((Join-Path $assets 'agentos.ico'), $out.ToArray())
$bw.Dispose(); $out.Dispose()

Write-Output ("ICO written: " + (Join-Path $assets 'agentos.ico'))
Write-Output ("PNG written: " + (Join-Path $assets 'agentos.png'))

# ---- honest self-check: sample pixels from the 256px preview ----
$png = New-Object System.Drawing.Bitmap((Join-Path $assets 'agentos.png'))
function Show([string]$name, [System.Drawing.Color]$c) {
    "{0} => R{1} G{2} B{3} A{4}" -f $name, $c.R, $c.G, $c.B, $c.A
}
Show 'corner(bg)      ' ($png.GetPixel(40, 40))
Show 'left-page(white)' ($png.GetPixel(80, 175))
Show 'right-page(white)' ($png.GetPixel(176, 175))
Show 'check(gold)     ' ($png.GetPixel(150, 100))
Show 'book-stack(white)' ($png.GetPixel(128, 214))
Show 'outside(trans)  ' ($png.GetPixel(4, 4))
$png.Dispose()
