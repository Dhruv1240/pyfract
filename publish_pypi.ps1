param(
    [ValidateSet("testpypi", "pypi")]
    [string]$Repository = "testpypi",
    [switch]$SkipBuild,
    [switch]$SkipDeps,
    [switch]$UseTrustedPublishing
)

$ErrorActionPreference = "Stop"

function Write-Step($Message) {
    Write-Host "==> $Message" -ForegroundColor Cyan
}

Set-Location $PSScriptRoot

if (-not $SkipDeps) {
    Write-Step "Installing/upgrading build dependencies"
    python -m pip install --upgrade pip build twine
}

if (-not $SkipBuild) {
    Write-Step "Cleaning previous dist artifacts"
    if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
    if (Test-Path "build") { Remove-Item -Recurse -Force "build" }

    Write-Step "Building source and wheel distributions"
    python -m build
}

if ($UseTrustedPublishing) {
    Write-Step "Uploading to $Repository (Trusted Publishing / ambient credentials)"
    python -m twine upload --repository $Repository dist/*
}
else {
    if ($Repository -eq "pypi") {
        if (-not $env:TWINE_PASSWORD -and -not $env:PYPI_TOKEN) {
            throw "Missing credentials. Set TWINE_USERNAME='__token__' and TWINE_PASSWORD='<pypi-token>' (or set PYPI_TOKEN)."
        }
        if (-not $env:TWINE_USERNAME) { $env:TWINE_USERNAME = "__token__" }
        if (-not $env:TWINE_PASSWORD -and $env:PYPI_TOKEN) { $env:TWINE_PASSWORD = $env:PYPI_TOKEN }
    }
    else {
        if (-not $env:TWINE_PASSWORD -and -not $env:TEST_PYPI_TOKEN) {
            throw "Missing credentials. Set TWINE_USERNAME='__token__' and TWINE_PASSWORD='<test-pypi-token>' (or set TEST_PYPI_TOKEN)."
        }
        if (-not $env:TWINE_USERNAME) { $env:TWINE_USERNAME = "__token__" }
        if (-not $env:TWINE_PASSWORD -and $env:TEST_PYPI_TOKEN) { $env:TWINE_PASSWORD = $env:TEST_PYPI_TOKEN }
    }

    Write-Step "Uploading to $Repository"
    python -m twine upload --repository $Repository dist/*
}

Write-Host "Done." -ForegroundColor Green
