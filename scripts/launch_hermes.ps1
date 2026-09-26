# JARVIS AI OS — Hermes Terminal Launcher
# Loads JARVIS .env environment variables and API keys into Hermes session

$ErrorActionPreference = "Stop"
$rootDir = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $rootDir ".env"

Write-Host "=================================================" -ForegroundColor Cyan
Write-Host "  JARVIS AI OS — Hermes Terminal Environment" -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Cyan

if (Test-Path $envFile) {
    Write-Host "[+] Loading environment & API keys from: $envFile" -ForegroundColor Green
    Get-Content $envFile | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#") -and ($line -match "^\s*([A-Za-z0-9_]+)\s*=\s*(.*)$")) {
            $key = $matches[1]
            $val = $matches[2].Trim("`"'")
            [System.Environment]::SetEnvironmentVariable($key, $val, "Process")
            if ($key -eq "GEMINI_API_KEY") {
                [System.Environment]::SetEnvironmentVariable("GOOGLE_API_KEY", $val, "Process")
            }
        }
    }
    Write-Host "[+] All API keys injected into current session." -ForegroundColor Green
} else {
    Write-Host "[!] Warning: .env file not found at $envFile" -ForegroundColor Yellow
}

# Sync to Hermes local secrets
$hermesEnv = "$env:LOCALAPPDATA\hermes\.env"
if (Test-Path $envFile) {
    Copy-Item -Path $envFile -Destination $hermesEnv -Force
}

Write-Host "`nLaunching Hermes..." -ForegroundColor Cyan
if ($args.Count -gt 0) {
    & hermes @args
} else {
    & hermes
}
