param(
    [int]$Port = 8000
)

$cloudflared = Get-Command cloudflared -ErrorAction SilentlyContinue
if (-not $cloudflared) {
    Write-Host "cloudflared não encontrado. Instale com: winget install Cloudflare.cloudflared"
    exit 1
}

Write-Host "Subindo tunel HTTPS para http://localhost:$Port ..."
& cloudflared tunnel --url "http://localhost:$Port"
