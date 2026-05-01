Param(
    [string]$Image = "registry:2",
    [string]$Dest = "admin@javitnas.ddns.net",
    [string]$DestPath = "/mnt/md0/public/MCP-CNC",
    [string]$Tmp = $env:TEMP
)

Write-Output "Image: $Image"
Write-Output "Destination: ${Dest}:${DestPath}"

$tar = Join-Path $Tmp "registry_arm64.tar"

Write-Output "Pulling $Image for linux/arm64..."
docker pull --platform linux/arm64 $Image

Write-Output "Saving image to $tar ..."
docker save $Image -o $tar

Write-Output "Copying $tar to ${Dest}:${DestPath} ..."
scp $tar "${Dest}:${DestPath}/"

Write-Output "Done. On NAS: cd $DestPath; sudo docker load -i registry_arm64.tar; sudo docker rm -f registry || true; sudo docker run -d --name registry --restart=unless-stopped -p 127.0.0.1:5000:5000 -v \"/mnt/md0/public/MCP-CNC/deploy/registry-caddy/data:/var/lib/registry\" registry:2"
