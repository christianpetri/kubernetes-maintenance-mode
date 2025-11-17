#!/usr/bin/env pwsh
# Kubernetes Maintenance Mode Demo - Quick Start Script

param(
    [Parameter()]
    [ValidateSet('setup', 'enable', 'disable', 'status', 'clean')]
    [string]$Action = 'status',
    
    [Parameter()]
    [switch]$Force
)

$ErrorActionPreference = 'Stop'

function Write-Header {
    param([string]$Text)
    Write-Host "`n=== $Text ===" -ForegroundColor Cyan
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

switch ($Action) {
    'setup' {
        Write-Header "Setting up Minikube cluster and deploying application"
        
        if (Test-MinikubeRunning) {
            Write-Host "[OK] Minikube is already running" -ForegroundColor Green
        } else {
            Write-Host "Starting Minikube..." -ForegroundColor Yellow
            minikube start --cpus=4 --memory=8192 --driver=docker
            if ($LASTEXITCODE -ne 0) {
                Write-Host "[ERROR] Failed to start Minikube" -ForegroundColor Red
                exit 1
            }
        }
        
        Write-Host "`nBuilding Docker image in Minikube..." -ForegroundColor Yellow
        minikube docker-env | Invoke-Expression
        docker build -t sample-app:latest .
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[ERROR] Failed to build Docker image" -ForegroundColor Red
            exit 1
        }
        
        Write-Host "`nEnabling Minikube addons..." -ForegroundColor Yellow
        Write-Host "  Enabling ingress addon..." -ForegroundColor Gray
        minikube addons enable ingress
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[WARNING] Failed to enable ingress addon, continuing..." -ForegroundColor Yellow
        }
        
        Write-Host "`nDeploying to Kubernetes..." -ForegroundColor Yellow
        kubectl apply -f kubernetes/namespace.yaml
        kubectl apply -f kubernetes/configmap.yaml
        kubectl apply -f kubernetes/redis-deployment.yaml
        kubectl apply -f kubernetes/deployment.yaml
        kubectl apply -f kubernetes/service.yaml
        kubectl apply -f kubernetes/maintenance-page-deployment.yaml
        kubectl apply -f kubernetes/ingress.yaml
        
        Write-Host "`nWaiting for pods to be ready..." -ForegroundColor Yellow
        Write-Host "  (Note: Only admin and user pods in normal mode will be ready)" -ForegroundColor Gray
        
        # Wait for admin pod first (always ready)
        kubectl wait --for=condition=ready pod -l app=sample-app,tier=admin -n sample-app --timeout=120s
        
        # Check if we're in maintenance mode
        $maintenanceMode = kubectl get configmap sample-app-config -n sample-app -o jsonpath='{.data.maintenance}'
        if ($maintenanceMode -ne "true") {
            # Only wait for user pods if not in maintenance mode
            kubectl wait --for=condition=ready pod -l app=sample-app,tier=user -n sample-app --timeout=120s
        }
        
        Write-Host ""
        Write-Host "[OK] Setup complete!" -ForegroundColor Green
        
        # Start service tunnels for direct access
        Write-Host "`nStarting service tunnels..." -ForegroundColor Yellow
        Write-Host "(Direct access to services - no Host headers needed)" -ForegroundColor Gray
        
        Start-Process pwsh -ArgumentList "-NoExit", "-Command", @"
Write-Host '=== USER Service Tunnel ===' -ForegroundColor Cyan;
Write-Host 'Keep this window open!' -ForegroundColor Yellow;
Write-Host 'Access URL will be shown below:' -ForegroundColor Green;
Write-Host '';
minikube service sample-app-user -n sample-app
"@
        
        Start-Process pwsh -ArgumentList "-NoExit", "-Command", @"
Write-Host '=== ADMIN Service Tunnel ===' -ForegroundColor Cyan;
Write-Host 'Keep this window open!' -ForegroundColor Yellow;
Write-Host 'Access URL will be shown below:' -ForegroundColor Green;
Write-Host '';
minikube service sample-app-admin -n sample-app
"@
        
        Start-Sleep -Seconds 3
        
        Write-Host "`nAccess:" -ForegroundColor Cyan
        Write-Host "  Check the tunnel windows for URLs" -ForegroundColor Yellow
        Write-Host "  Direct localhost access - no configuration needed!" -ForegroundColor Green
        Write-Host "`nDemo:" -ForegroundColor Cyan
        Write-Host "  1. Open user URL in browser" -ForegroundColor White
        Write-Host "  2. Open admin URL in browser" -ForegroundColor White
        Write-Host "  3. Click 'Enable Maintenance' in admin panel" -ForegroundColor White
        Write-Host "  4. Refresh user page -> see maintenance page" -ForegroundColor White
        Write-Host "  5. Admin page remains accessible" -ForegroundColor White
    }
    
    'enable' {
        Write-Header "Enabling Maintenance Mode"
        
        if (-not (Test-NamespaceExists)) {
            Write-Host "[ERROR] Namespace 'sample-app' not found. Run setup first." -ForegroundColor Red
            exit 1
        }
        
        kubectl patch configmap sample-app-config -n sample-app --type=json `
            -p '[{"op": "replace", "path": "/data/maintenance", "value": "true"}]'
        kubectl rollout restart deployment -n sample-app
        
        Write-Host "`nWaiting for rollout to complete..." -ForegroundColor Yellow
        kubectl rollout status deployment sample-app-admin -n sample-app --timeout=60s
        kubectl rollout status deployment sample-app-user -n sample-app --timeout=60s
        
        Write-Host ""
        Write-Host "[OK] Maintenance mode enabled!" -ForegroundColor Green
        Write-Host ""
        Write-Host "Pod status:" -ForegroundColor Cyan
        kubectl get pods -n sample-app
        
        Write-Host ""
        Write-Host "Expected behavior:" -ForegroundColor Yellow
        Write-Host "  - Admin pods (sample-app-admin-*): 1/1 Ready (ALWAYS accessible)" -ForegroundColor Green
        Write-Host "  - User pods (sample-app-user-*):  0/1 Not Ready (removed from Service)" -ForegroundColor Red
        Write-Host ""
        Write-Host "Note: Both pod types run identical code - behavior differs only via ADMIN_ACCESS env var" -ForegroundColor Cyan
    }
    
    'disable' {
        Write-Header "Disabling Maintenance Mode"
        
        if (-not (Test-NamespaceExists)) {
            Write-Host "[ERROR] Namespace 'sample-app' not found. Run setup first." -ForegroundColor Red
            exit 1
        }
        
        kubectl patch configmap sample-app-config -n sample-app --type=json `
            -p '[{"op": "replace", "path": "/data/maintenance", "value": "false"}]'
        kubectl rollout restart deployment -n sample-app
        
        Write-Host "`nWaiting for rollout to complete..." -ForegroundColor Yellow
        kubectl rollout status deployment sample-app-admin -n sample-app --timeout=60s
        kubectl rollout status deployment sample-app-user -n sample-app --timeout=60s
        
        Write-Host ""
        Write-Host "[OK] Maintenance mode disabled!" -ForegroundColor Green
        Write-Host ""
        Write-Host "Pod status:" -ForegroundColor Cyan
        kubectl get pods -n sample-app
        
        Write-Host ""
        Write-Host "All pods should be 1/1 Ready" -ForegroundColor Green
    }
    
    'status' {
        Write-Header "Current Status"
        
        if (-not (Test-NamespaceExists)) {
            Write-Host "[ERROR] Namespace 'sample-app' not found. Run setup first." -ForegroundColor Red
            exit 1
        }
        
        $configMap = kubectl get configmap sample-app-config -n sample-app -o jsonpath='{.data.maintenance}' 2>$null
        
        Write-Host "`nMaintenance Mode: " -NoNewline -ForegroundColor Cyan
        if ($configMap -eq "true") {
            Write-Host "ENABLED" -ForegroundColor Red
        } else {
            Write-Host "DISABLED" -ForegroundColor Green
        }
        
        Write-Host "`nPod Status:" -ForegroundColor Cyan
        kubectl get pods -n sample-app
        
        Write-Host "`nService Status:" -ForegroundColor Cyan
        Write-Host "  Admin Service (always accessible):" -ForegroundColor Yellow
        $adminEndpoints = kubectl get endpointslices -n sample-app -l kubernetes.io/service-name=sample-app-admin -o jsonpath='{.items[0].endpoints[*].addresses[0]}' 2>$null
        if ($adminEndpoints) {
                Write-Host "    [OK] Endpoints: $adminEndpoints" -ForegroundColor Green
            } else {
                Write-Host "    [WARNING] No endpoints available" -ForegroundColor Red
            }        Write-Host "  User Service (blocked during maintenance):" -ForegroundColor Yellow
        $userEndpoints = kubectl get endpointslices -n sample-app -l kubernetes.io/service-name=sample-app-user -o jsonpath='{.items[0].endpoints[?(@.conditions.ready==true)].addresses[0]}' 2>$null
        if ($userEndpoints) {
            Write-Host "    [OK] Ready endpoints: $userEndpoints" -ForegroundColor Green
        } else {
            Write-Host "    [WARNING] No ready endpoints (removed from load balancer)" -ForegroundColor Red
        }
    }
    
    'clean' {
        Write-Header "Cleaning up"
        
        if (-not $Force) {
            Write-Host "[WARNING] This will delete the entire sample-app namespace and stop Minikube." -ForegroundColor Yellow
            $confirmation = Read-Host "Are you sure? (yes/no)"
            if ($confirmation -ne "yes") {
                Write-Host "Cleanup cancelled." -ForegroundColor Gray
                exit 0
            }
        }
        
        if (Test-NamespaceExists) {
            Write-Host "Deleting namespace..." -ForegroundColor Yellow
            kubectl delete namespace sample-app --timeout=60s
        } else {
            Write-Host "[OK] Namespace already deleted" -ForegroundColor Green
        }
        
        if (Test-MinikubeRunning) {
            Write-Host "`nStopping Minikube..." -ForegroundColor Yellow
            minikube stop
        } else {
            Write-Host "[OK] Minikube already stopped" -ForegroundColor Green
        }
        
        Write-Host ""
        Write-Host "[OK] Cleanup complete!" -ForegroundColor Green
    }
}

Write-Host ""
