<#
.SYNOPSIS
  Starts the SSB Suraksha screening service.

.DESCRIPTION
  Loads Phase_1 (orientation, U-Net detection, perspective correction, PP-OCRv5,
  MRZ/QR), backend/validation (deterministic rule sets) and the faceverify
  pipeline (SCRFD + ArcFace R50) into one process, and serves POST /screen.

  Two environment details are handled here rather than left to the operator:

    * TLS. Antivirus HTTPS scanning (Avast here) presents a certificate signed
      by a private CA. PaddleX downloads its language models over HTTPS and
      fails with CERTIFICATE_VERIFY_FAILED unless Python is told to trust that
      CA. Node already knows about it via NODE_EXTRA_CA_CERTS; Python has no
      equivalent, so a bundle is built from certifi's roots plus that CA.
    * The model-source probe. PaddleX pings several model hosts at startup and
      aborts if none answer, which turns a slow network into a failed launch.
      The probe is skipped; a model that is genuinely missing still fails loudly
      when it is needed.

.PARAMETER Port
  Defaults to 8000.

.PARAMETER BindHost
  Defaults to 0.0.0.0 so a phone on the same network can reach it. Binding to
  localhost would make the service invisible to the device it exists to serve.
#>
[CmdletBinding()]
param(
    [int]$Port = 8000,
    [string]$BindHost = '0.0.0.0'
)

$ErrorActionPreference = 'Stop'
$ServiceRoot = $PSScriptRoot

function New-PythonCaBundle {
    <#
      Returns a CA bundle that trusts both the public roots and any locally
      installed interception CA, or $null when nothing is intercepting.
      NODE_EXTRA_CA_CERTS is the signal: whatever installed the proxy set it so
      Node would keep working, and that CA is what Python is missing.
    #>
    $ca = $env:NODE_EXTRA_CA_CERTS
    if (-not $ca -or -not (Test-Path $ca)) { return $null }

    $bundle = "$env:LOCALAPPDATA\ssb-suraksha\python-ca-bundle.pem"
    $certifi = & python -c "import certifi;print(certifi.where())"
    if ($LASTEXITCODE -ne 0) { return $null }

    if (Test-Path $bundle) {
        $built = (Get-Item $bundle).LastWriteTime
        if ($built -gt (Get-Item $ca).LastWriteTime -and $built -gt (Get-Item $certifi).LastWriteTime) {
            return $bundle
        }
    }

    New-Item -ItemType Directory -Force -Path (Split-Path $bundle) | Out-Null
    Get-Content $certifi -Raw | Set-Content $bundle -Encoding ascii
    Add-Content $bundle "`n"
    Get-Content $ca -Raw | Add-Content $bundle -Encoding ascii
    Write-Host "TLS      trusting $ca"
    return $bundle
}

$bundle = New-PythonCaBundle
if ($bundle) {
    $env:REQUESTS_CA_BUNDLE = $bundle
    $env:SSL_CERT_FILE = $bundle
    $env:CURL_CA_BUNDLE = $bundle
}
$env:PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK = 'True'
$env:PYTHONPATH = $ServiceRoot

$addresses = Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' } |
    Select-Object -ExpandProperty IPAddress

Write-Host ""
Write-Host "Screening service starting on port $Port"
Write-Host "Point the app's screening service address at one of:"
foreach ($ip in $addresses) { Write-Host "    http://${ip}:$Port" }
Write-Host ""
Write-Host "Models load on first start and can take a minute."
Write-Host ""

Push-Location $ServiceRoot
try {
    & python -m uvicorn ssb_screening_api.main:app --host $BindHost --port $Port
} finally { Pop-Location }
