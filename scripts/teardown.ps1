#!/usr/bin/env pwsh
# Complete Teardown Script for Kubernetes Maintenance Mode Demo
# Safely cleans up all resources in proper order

param(
    [Parameter()]
    [switch]$KeepMinikube,
    
    [Parameter()]
    [switch]$Force,
    
    [Parameter()]
    [switch]$DeepClean
)

$ErrorActionPreference = 'Stop'

function Write-Header {
    param([string]$Text)
    Write-Host "`n=== $Text ===" -ForegroundColor Cyan
}

function Write-Step {
    param([string]$Text)
    Write-Host "`n$Text" -ForegroundColor Yellow
}

function Test-MinikubeRunning {
    try {
        $status = minikube status --format='{{.Host}}' 2>$null
        return $status -eq 'Running'
    } catch {
        return $false
    }
}

function Test-NamespaceExists {
    try {
        kubectl get namespace sample-app 2>$null | Out-Null
        return $true
    } catch {
        return $false
    }
}

Write-Header "Kubernetes Maintenance Mode Demo - Teardown"

# Safety check
if (-not $Force) {
    Write-Host "`nThis will remove:" -ForegroundColor Yellow
    Write-Host "  - sample-app namespace (all pods, services, deployments)" -ForegroundColor White
    Write-Host "  - Port-forward processes" -ForegroundColor White
    if (-not $KeepMinikube) {
        Write-Host "  - Minikube cluster (complete shutdown)" -ForegroundColor White
    }
    if ($DeepClean) {
        Write-Host "  - Minikube cluster data (complete deletion)" -ForegroundColor Red
        Write-Host "  - Docker images" -ForegroundColor Red
    }
    
    Write-Host "`nAre you sure you want to continue? (yes/no): " -NoNewline -ForegroundColor Yellow
    $confirmation = Read-Host
    if ($confirmation -ne "yes") {
        Write-Host "`n[CANCELLED] Teardown cancelled by user" -ForegroundColor Gray
        exit 0
    }
}

# Step 1: Stop port-forward processes
Write-Step "Step 1: Stopping port-forward processes..."
try {
    $portForwards = Get-Process -Name kubectl -ErrorAction SilentlyContinue | Where-Object {
        $_.CommandLine -like "*port-forward*"
    }
    
    if ($portForwards) {
        $portForwards | Stop-Process -Force
        Write-Host "[OK] Stopped $($portForwards.Count) port-forward process(es)" -ForegroundColor Green
    } else {
        Write-Host "[OK] No port-forward processes found" -ForegroundColor Green
    }
} catch {
    Write-Host "[WARNING] Could not stop port-forward processes: $_" -ForegroundColor Yellow
}

# Step 2: Delete Kubernetes namespace
if (Test-MinikubeRunning) {
    Write-Step "Step 2: Deleting Kubernetes namespace..."
    
    if (Test-NamespaceExists) {
        try {
            Write-Host "  Deleting sample-app namespace..." -ForegroundColor Gray
            kubectl delete namespace sample-app --timeout=90s --wait=true 2>&1 | Out-Null
            
            # Verify deletion
            $maxWait = 30
            $waited = 0
            while ((Test-NamespaceExists) -and ($waited -lt $maxWait)) {
                Write-Host "  Waiting for namespace deletion... ($waited/$maxWait seconds)" -ForegroundColor Gray
                Start-Sleep -Seconds 2
                $waited += 2
            }
            
            if (-not (Test-NamespaceExists)) {
                Write-Host "[OK] Namespace deleted successfully" -ForegroundColor Green
            } else {
                Write-Host "[WARNING] Namespace still exists after timeout" -ForegroundColor Yellow
            }
        } catch {
            Write-Host "[WARNING] Error deleting namespace: $_" -ForegroundColor Yellow
        }
    } else {
        Write-Host "[OK] Namespace already deleted" -ForegroundColor Green
    }
} else {
    Write-Host "[SKIP] Minikube not running, skipping namespace deletion" -ForegroundColor Gray
}

# Step 3: Handle Minikube
if (-not $KeepMinikube) {
    if (Test-MinikubeRunning) {
        Write-Step "Step 3: Stopping Minikube cluster..."
        try {
            minikube stop 2>&1 | Out-Null
            Write-Host "[OK] Minikube stopped successfully" -ForegroundColor Green
        } catch {
            Write-Host "[WARNING] Error stopping Minikube: $_" -ForegroundColor Yellow
        }
    } else {
        Write-Host "[OK] Minikube already stopped" -ForegroundColor Green
    }
    
    # Deep clean option
    if ($DeepClean) {
        Write-Step "Step 4: Deep cleaning Minikube (deleting cluster data)..."
        Write-Host "[WARNING] This will delete all Minikube data!" -ForegroundColor Red
        Start-Sleep -Seconds 2
        
        try {
            minikube delete 2>&1 | Out-Null
            Write-Host "[OK] Minikube cluster deleted" -ForegroundColor Green
        } catch {
            Write-Host "[WARNING] Error deleting Minikube: $_" -ForegroundColor Yellow
        }
        
        # Clean Docker images
        Write-Step "Step 5: Cleaning Docker images..."
        try {
            docker images --filter=reference='sample-app:*' --format '{{.ID}}' | ForEach-Object {
                docker rmi $_ --force 2>&1 | Out-Null
            }
            Write-Host "[OK] Sample app Docker images removed" -ForegroundColor Green
        } catch {
            Write-Host "[WARNING] Error removing Docker images: $_" -ForegroundColor Yellow
        }
    }
} else {
    Write-Host "[SKIP] Keeping Minikube running (--KeepMinikube flag set)" -ForegroundColor Gray
}

# Summary
Write-Header "Teardown Summary"
Write-Host "Completed actions:" -ForegroundColor Green
Write-Host "  [OK] Port-forward processes stopped" -ForegroundColor White
Write-Host "  [OK] Kubernetes namespace cleaned" -ForegroundColor White

if (-not $KeepMinikube) {
    Write-Host "  [OK] Minikube stopped" -ForegroundColor White
    if ($DeepClean) {
        Write-Host "  [OK] Minikube cluster data deleted" -ForegroundColor White
        Write-Host "  [OK] Docker images cleaned" -ForegroundColor White
    }
} else {
    Write-Host "  [KEPT] Minikube cluster still running" -ForegroundColor Cyan
}

Write-Host "`nTo restart the demo:" -ForegroundColor Yellow
if ($DeepClean) {
    Write-Host "  .\scripts\runme.ps1 setup" -ForegroundColor White
} elseif (-not $KeepMinikube) {
    Write-Host "  minikube start" -ForegroundColor White
    Write-Host "  .\scripts\runme.ps1 setup" -ForegroundColor White
} else {
    Write-Host "  .\scripts\runme.ps1 setup" -ForegroundColor White
}

Write-Host "`n[OK] Teardown complete!`n" -ForegroundColor Green
