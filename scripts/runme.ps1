param(
    [ValidateSet("native","docker")] [string]$Mode = "docker",
    [int]$Port = 8080,
    [switch]$Build,
    [switch]$Start,
    [switch]$Stop,
    [switch]$EnableMaintenance,
    [switch]$DisableMaintenance
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Write-Info($msg) { Write-Host $msg -ForegroundColor Cyan }
function Write-Warn($msg) { Write-Host $msg -ForegroundColor Yellow }
function Write-Err($msg)  { Write-Host $msg -ForegroundColor Red }

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Repo = Split-Path -Parent $Root
$JavaDemo = Join-Path $Repo 'java-tomcat-demo'
$WarPath = Join-Path $JavaDemo 'target\maintenance-demo.war'
$ContainerName = 'tomcat-maintenance-demo'
$ImageTag = 'maintenance-demo:tomcat10'

function Test-Exe($name) {
    return [bool](Get-Command $name -ErrorAction SilentlyContinue)
}

function Build-War() {
    if (Test-Exe 'mvn') {
        Write-Info 'Building WAR with local Maven...'
        Push-Location $JavaDemo; mvn -q clean package; Pop-Location
    } elseif (Test-Exe 'docker') {
        Write-Info 'Building WAR using dockerized Maven...'
        $mnt = ($JavaDemo -replace '\\','/')
        docker run --rm -v "$mnt:/app" -w /app maven:3-eclipse-temurin-17 mvn -q clean package
    } else {
        Write-Err 'Maven not found and Docker not available. Install one to build the WAR.'
        exit 1
    }
    if (-not (Test-Path $WarPath)) { Write-Err "WAR not found at $WarPath"; exit 1 }
}

function Deploy-Native() {
    if (-not $env:TOMCAT_HOME) { Write-Err 'Set TOMCAT_HOME to your Tomcat 10+ install path.'; exit 1 }
    $dest = Join-Path $env:TOMCAT_HOME 'webapps\ROOT.war'
    Write-Info "Copying WAR to $dest"
    Copy-Item $WarPath $dest -Force
    if ($Start) {
        Write-Info 'Starting Tomcat...'
        & (Join-Path $env:TOMCAT_HOME 'bin\startup.bat') | Out-Null
        Write-Info "Tomcat listening on http://localhost:$Port"
    }
    if ($Stop) {
        Write-Info 'Stopping Tomcat...'
        & (Join-Path $env:TOMCAT_HOME 'bin\shutdown.bat') | Out-Null
    }
}

function Deploy-Docker() {
    if ($Stop) {
        Write-Info 'Stopping and removing existing container (if any)...'
        docker rm -f $ContainerName 2>$null | Out-Null
    }
    if ($Build -or $Start -or -not (docker image inspect $ImageTag 2>$null)) {
        Write-Info 'Building Docker image...'
        Push-Location $JavaDemo; docker build -t $ImageTag .; Pop-Location
    }
    if ($Start) {
        Write-Info 'Starting container...'
        docker run -d --name $ContainerName -p "$Port:8080" $ImageTag | Out-Null
        Write-Info "App available at http://localhost:$Port"
    }
}

function Toggle-Maintenance($enable) {
    if ($Mode -eq 'docker') {
        $cmd = if ($enable) { 'touch /tmp/maint.on' } else { 'rm -f /tmp/maint.on' }
        docker exec $ContainerName sh -c "$cmd"
        Write-Info ("Maintenance " + ($enable ? 'ENABLED' : 'DISABLED') + ' in container')
    } else {
        $flagDir = 'C:\tmp'
        $flag = Join-Path $flagDir 'maint.on'
        if ($enable) {
            if (-not (Test-Path $flagDir)) { New-Item -ItemType Directory -Path $flagDir | Out-Null }
            New-Item -ItemType File -Path $flag -Force | Out-Null
        } else {
            Remove-Item -Force $flag -ErrorAction SilentlyContinue
        }
        Write-Info ("Maintenance " + ($enable ? 'ENABLED' : 'DISABLED') + ' on host (C:\\tmp\\maint.on)')
    }
}

function Test-Endpoints() {
    Write-Info 'Testing endpoints...'
    try {
        $u1 = "http://localhost:$Port/api/status"
        $u2 = "http://localhost:$Port/admin/status"
        (Invoke-WebRequest -UseBasicParsing $u1).StatusCode | Out-Null
        (Invoke-WebRequest -UseBasicParsing $u2).StatusCode | Out-Null
        Write-Host "- $u1" -ForegroundColor Green
        Write-Host "- $u2" -ForegroundColor Green
    } catch {
        Write-Warn "Request failed: $_"
    }
}

# Default behavior: build and start if no explicit actions were passed
$noAction = -not ($Build -or $Start -or $Stop -or $EnableMaintenance -or $DisableMaintenance)
if ($noAction) { $Build = $true; $Start = $true }

if ($Build) { Build-War }

switch ($Mode) {
    'native' { Deploy-Native }
    'docker' { Deploy-Docker }
}

if ($EnableMaintenance) { Toggle-Maintenance $true; Test-Endpoints }
if ($DisableMaintenance) { Toggle-Maintenance $false; Test-Endpoints }

if ($Start -and -not ($EnableMaintenance -or $DisableMaintenance)) { Test-Endpoints }

Write-Info 'Done.'