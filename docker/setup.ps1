$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot/..
if (!(Test-Path -LiteralPath '.env')) {
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $entries = @()
    foreach ($name in @('UNIFIED_CTI_API_KEY', 'PKCERT_DB_PASSWORD', 'MYSQL_ROOT_PASSWORD')) {
        $buffer = New-Object byte[] 32
        $rng.GetBytes($buffer)
        $value = [BitConverter]::ToString($buffer).Replace('-', '').ToLowerInvariant()
        $entries += "$name=$value"
    }
    $rng.Dispose()
    $entries += 'ENABLE_LIVE_COLLECTION=false'
    Set-Content -LiteralPath '.env' -Value $entries -Encoding ascii
    Write-Host 'Created local .env credentials.'
}
docker buildx inspect hexsentry-builder *> $null
if ($LASTEXITCODE -eq 0) {
    docker compose build --builder hexsentry-builder
    if ($LASTEXITCODE -ne 0) { throw "Container build failed." }
    docker compose up -d --no-build
} else {
    docker compose up -d --build
}
if ($LASTEXITCODE -ne 0) { throw 'Docker startup failed. Check Docker Desktop and the output above.' }
docker compose ps
Write-Host 'Dashboard: http://localhost:3000'

