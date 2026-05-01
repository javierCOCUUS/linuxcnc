param(
    [Parameter(Mandatory=$false)]
    [string]$NASHost = "javitnas.ddns.net",

    [Parameter(Mandatory=$false)]
    [int]$Port = 9222,

    [Parameter(Mandatory=$false)]
    [string]$User = "admin",

    [Parameter(Mandatory=$false)]
    [string[]]$Images = @("registry:2", "curlimages/curl:latest"),

    [Parameter(Mandatory=$false)]
    [string]$Destination = "/tmp",

    [Parameter(Mandatory=$false)]
    [switch]$UseSudo = $true
)

function Check-Command {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Command '$Name' is required but not found."
    }
}

Check-Command docker
Check-Command scp
Check-Command ssh

$workDir = Join-Path -Path $env:TEMP -ChildPath "nas-registry-push"
if (-not (Test-Path $workDir)) {
    New-Item -Path $workDir -ItemType Directory | Out-Null
}

function Get-ImageTarName {
    param([string]$Image)
    $safe = $Image -replace '[:/]', '_' -replace '[^A-Za-z0-9_\-\.]', '_'
    return "$safe.tar"
}

function Get-Arm64Digest {
    param([string]$Image)
    Write-Host "Inspecting manifest for $Image..."
    $json = docker manifest inspect $Image 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to inspect manifest for $Image."
    }
    $manifest = $json | ConvertFrom-Json
    if (-not $manifest.manifests) {
        throw "Manifest for $Image has no manifests list."
    }
    foreach ($entry in $manifest.manifests) {
        if ($entry.platform.os -eq 'linux' -and $entry.platform.architecture -eq 'arm64') {
            return $entry.digest
        }
    }
    throw "No linux/arm64 manifest found for $Image."
}

foreach ($image in $Images) {
    Write-Host "Processing image: $image"
    $pullImage = $image
    docker pull --platform linux/arm64 $image
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Initial pull failed for $image. Trying manifest-based ARM64 variant..."
        $digest = Get-Arm64Digest $image
        $pullImage = "$image@$digest"
        docker pull --platform linux/arm64 $pullImage
        if ($LASTEXITCODE -ne 0) {
            throw "Could not pull ARM64 variant for $image."
        }
    }

    $tarName = Get-ImageTarName $image
    $tarPath = Join-Path -Path $workDir -ChildPath $tarName
    Write-Host "Saving image $pullImage to $tarPath"
    docker save $pullImage -o $tarPath
    if ($LASTEXITCODE -ne 0) {
        Write-Host "docker save failed for $pullImage, retrying with explicit ARM64 digest..."
        $digest = Get-Arm64Digest $image
        $pullImage = "$image@$digest"
        docker pull --platform linux/arm64 $pullImage
        if ($LASTEXITCODE -ne 0) {
            throw "Could not pull ARM64 digest variant for $image."
        }
        docker save $pullImage -o $tarPath
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to save ARM64 digest image $pullImage."
        }
    }

    Write-Host "Copying $tarName to ${NASHost}:${Destination}"
    scp -P $Port $tarPath "$User@${NASHost}:${Destination}/"
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to copy $tarName to NAS."
    }

    $remoteTar = "$Destination/$tarName"
    $remoteCmd = "docker load -i '$remoteTar' && rm -f '$remoteTar'"
    if ($UseSudo) {
        $remoteCmd = "sudo -S env PATH=`$PATH:/usr/bin:/usr/local/bin:/usr/sbin:/sbin docker load -i '$remoteTar' && sudo -S env PATH=`$PATH:/usr/bin:/usr/local/bin:/usr/sbin:/sbin rm -f '$remoteTar'"
    }

    Write-Host "Loading $tarName on NAS..."
    Write-Host "If sudo prompts for a password, enter it when asked."
    ssh -t -p $Port $User@$NASHost $remoteCmd
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to load $tarName on NAS."
    }

    Write-Host "Image $image successfully pushed and loaded on NAS."
}

Write-Host "All images pushed successfully."
