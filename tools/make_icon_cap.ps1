# Generates the Agent Study OS desktop icon:
# a white graduation cap with a gold tassel on an emerald-green rounded square.
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
$EDGE_WHITE  = [System.Drawing.Color]::FromArgb(255, 196, 232, 212)  # light mint outline
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

    # head band (rounded white bar under the board)
    $bandX = P 60; $bandY = P 182; $bandW = P 136; $bandH = P 30
    $bandR = P 15
    $bd = $bandR * 2
    $bandPath = New-Object System.Drawing.Drawing2D.GraphicsPath
    $bandPath.AddArc($bandX, $bandY, $bd, $bd, 180, 90)
    $bandPath.AddArc($bandX + $bandW - $bd, $bandY, $bd, $bd, 270, 90)
    $bandPath.AddArc($bandX + $bandW - $bd, $bandY + $bandH - $bd, $bd, $bd, 0, 90)
    $bandPath.AddArc($bandX, $bandY + $bandH - $bd, $bd, $bd, 90, 90)
    $bandPath.CloseFigure()
    $g.FillPath($whiteBrush, $bandPath)

    # board: white diamond
    $board = New-Object 'System.Drawing.Point[]' 4
    $board[0] = New-Object System.Drawing.Point -ArgumentList (P 128),(P 70)
    $board[1] = New-Object System.Drawing.Point -ArgumentList (P 206),(P 128)
    $board[2] = New-Object System.Drawing.Point -ArgumentList (P 128),(P 186)
    $board[3] = New-Object System.Drawing.Point -ArgumentList (P 50),(P 128)
    $g.FillPolygon($whiteBrush, $board)
    $edgePen = New-Object System.Drawing.Pen -ArgumentList $EDGE_WHITE, ([single]([Math]::Max(1.0, (P 2))))
    $g.DrawPolygon($edgePen, $board)

    # center button (gold)
    $g.FillEllipse($goldBrush, (P 118), (P 118), (P 20), (P 20))

    # tassel: bezier hanging from the right vertex, gold
    $tasselPen = New-Object System.Drawing.Pen -ArgumentList $GOLD, ([single]([Math]::Max(1.5, (P 6))))
    $tasselPen.StartCap = [System.Drawing.Drawing2D.LineCap]::Round
    $tasselPen.EndCap   = [System.Drawing.Drawing2D.LineCap]::Round
    $tasselPath = New-Object System.Drawing.Drawing2D.GraphicsPath
    $tasselPath.AddBezier((P 206),(P 128),(P 214),(P 152),(P 222),(P 178),(P 228),(P 196))
    $g.DrawPath($tasselPen, $tasselPath)
    # tassel end ball
    $g.FillEllipse($goldBrush, (P 219), (P 187), (P 18), (P 18))
    # knot just below the vertex
    $knotPen = New-Object System.Drawing.Pen -ArgumentList $DARK_GOLD, ([single]([Math]::Max(1.5, (P 5))))
    $knotPen.StartCap = [System.Drawing.Drawing2D.LineCap]::Round
    $knotPen.EndCap   = [System.Drawing.Drawing2D.LineCap]::Round
    $g.DrawLine($knotPen, (P 206), (P 128), (P 206), (P 140))

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
Show 'corner(bg)   ' ($png.GetPixel(40, 40))
Show 'board(white) ' ($png.GetPixel(128, 95))
Show 'button(gold) ' ($png.GetPixel(128, 128))
Show 'outside(trans)' ($png.GetPixel(4, 4))
$png.Dispose()
