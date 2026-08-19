Add-Type -AssemblyName System.Drawing

$characters = @(
    @{ Id = 'firewall'; Color = '#4B0A0A' },
    @{ Id = 'switch'; Color = '#34120D' },
    @{ Id = 'access-point'; Color = '#34120D' },
    @{ Id = 'router'; Color = '#34120D' },
    @{ Id = 'hacker'; Color = '#34120D' },
    @{ Id = 'sysadmin'; Color = '#34120D' },
    @{ Id = 'user'; Color = '#34120D' },
    @{ Id = 'lan-cable'; Color = '#34120D' },
    @{ Id = 'server'; Color = '#34120D' },
    @{ Id = 'cloud'; Color = '#34120D' }
)

$states = @(
    @{ Name = 'mouth_closed.png'; Width = 150; Height = 20; Open = 7 },
    @{ Name = 'mouth_small.png'; Width = 150; Height = 55; Open = 36 },
    @{ Name = 'mouth_wide.png'; Width = 150; Height = 95; Open = 75 }
)

foreach ($character in $characters) {
    $directory = Join-Path $PSScriptRoot "..\characters\$($character.Id)"

    foreach ($state in $states) {
        $bitmap = New-Object System.Drawing.Bitmap($state.Width, $state.Height)
        $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
        $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
        $graphics.Clear([System.Drawing.Color]::Transparent)

        $fill = New-Object System.Drawing.SolidBrush([System.Drawing.ColorTranslator]::FromHtml($character.Color))
        $outline = New-Object System.Drawing.Pen([System.Drawing.Color]::Black, 5)
        $top = [Math]::Max(0, [int](($state.Height - $state.Open) / 2))
        $rect = [System.Drawing.Rectangle]::new(
            3,
            $top,
            ([int]$state.Width - 6),
            [int]$state.Open
        )

        $graphics.FillEllipse($fill, $rect)
        $graphics.DrawEllipse($outline, $rect)
        $outline.Dispose()
        $fill.Dispose()
        $graphics.Dispose()

        $bitmap.Save((Join-Path $directory $state.Name), [System.Drawing.Imaging.ImageFormat]::Png)
        $bitmap.Dispose()
    }
}
