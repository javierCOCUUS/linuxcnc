Param(
    [string]$Repo = "mcp-cnc",
    [ValidateSet('push','load')][string]$Mode = 'push'
)

if (-not (docker buildx inspect multiarch-builder > $null 2>&1)) {
    Write-Output "Creating buildx builder 'multiarch-builder'..."
    docker buildx create --name multiarch-builder --use | Out-Null
}

$pushOp = if ($Mode -eq 'push') { '--push' } else { '--load' }

$services = @('mcp','dxf-engine','cam-engine','catalogue','linuxcnc-bridge')
foreach ($svc in $services) {
    Write-Output "Building $svc for linux/arm64 -> $Repo/$svc:latest"
    docker buildx build --platform linux/arm64 -t "$Repo/$svc:latest" -f "$svc/Dockerfile" $svc $pushOp
}

Write-Output "All done."
