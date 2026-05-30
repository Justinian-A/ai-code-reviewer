# scripts/version.ps1
# PowerShell version bump script for Windows

$ErrorActionPreference = "Stop"

# Read pyproject.toml
$content = Get-Content -Path "pyproject.toml" -Raw

# Extract current version
if ($content -match 'version = "(\d+\.\d+\.\d+)"') {
    $currentVersion = $matches[1]
} else {
    Write-Error "Could not find version in pyproject.toml"
    exit 1
}

# Parse version components
$parts = $currentVersion -split '\.'
$major = [int]$parts[0]
$minor = [int]$parts[1]
$patch = [int]$parts[2]

# Bump patch version
$newPatch = $patch + 1
$newVersion = "$major.$minor.$newPatch"

# Update pyproject.toml
$newContent = $content -replace "version = `"$currentVersion`"", "version = `"$newVersion`""
Set-Content -Path "pyproject.toml" -Value $newContent

Write-Host "Version bumped from $currentVersion to $newVersion"
