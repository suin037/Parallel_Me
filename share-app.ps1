$ErrorActionPreference = "Stop"

$cloudflared = "C:\Program Files (x86)\cloudflared\cloudflared.exe"
if (-not (Test-Path -LiteralPath $cloudflared)) {
    throw "cloudflared를 찾지 못했습니다: $cloudflared"
}

$frontend = Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue
$backend = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue

if (-not $backend) {
    Write-Host "[오류] 백엔드 8000번 서버가 실행 중이지 않습니다." -ForegroundColor Red
    Write-Host "먼저 별도 PowerShell에서 백엔드를 실행하세요."
    exit 1
}
if (-not $frontend) {
    Write-Host "[오류] 프론트엔드 5173번 서버가 실행 중이지 않습니다." -ForegroundColor Red
    Write-Host "먼저 별도 PowerShell에서 npm run dev를 실행하세요."
    exit 1
}

Write-Host "프론트·백엔드 확인 완료. 공유 주소를 만드는 중입니다..." -ForegroundColor Cyan
Write-Host "아래에 표시되는 https://...trycloudflare.com 주소를 공유하세요." -ForegroundColor Yellow
Write-Host "이 창을 닫으면 공유가 종료됩니다.`n"

& $cloudflared tunnel --no-autoupdate --protocol http2 --url http://127.0.0.1:5173
