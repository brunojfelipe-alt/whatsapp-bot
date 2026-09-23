#!/usr/bin/env bash
set -euo pipefail

PORT="${1:-8000}"

if ! command -v cloudflared >/dev/null 2>&1; then
    echo "cloudflared não encontrado. Instale com: winget install Cloudflare.cloudflared"
    exit 1
fi

echo "Subindo tunel HTTPS para http://localhost:${PORT} ..."
cloudflared tunnel --url "http://localhost:${PORT}"
