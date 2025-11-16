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
            Write-Host "✓ Minikube is already running" -ForegroundColor Green
        } else {
            Write-Host "Starting Minikube..." -ForegroundColor Yellow
            minikube start --cpus=4 --memory=8192 --driver=docker
            if ($LASTEXITCODE -ne 0) {
                Write-Host "❌ Failed to start Minikube" -ForegroundColor Red
                exit 1
            }
        }
        
        Write-Host "`nBuilding Docker image in Minikube..." -ForegroundColor Yellow
        minikube docker-env | Invoke-Expression
        docker build -t sample-app:latest .
        if ($LASTEXITCODE -ne 0) {
            Write-Host "❌ Failed to build Docker image" -ForegroundColor Red
            exit 1
        }
        
        Write-Host "`nDeploying to Kubernetes..." -ForegroundColor Yellow
        kubectl apply -f kubernetes/namespace.yaml
        kubectl apply -f kubernetes/configmap.yaml
        kubectl apply -f kubernetes/deployment.yaml
        kubectl apply -f kubernetes/service.yaml
        kubectl apply -f kubernetes/ingress.yaml
        
        Write-Host "`nWaiting for pods to be ready..." -ForegroundColor Yellow
        Write-Host "  (Note: Only admin and user pods in normal mode will be ready)" -ForegroundColor Gray
        
        # Wait for admin pod first (always ready)
        kubectl wait --for=condition=ready pod -l app=sample-app,tier=admin -n sample-app --timeout=120s
        
        # Check if we're in maintenance mode
        $maintenanceMode = kubectl get configmap app-config -n sample-app -o jsonpath='{.data.MAINTENANCE_MODE}'
        if ($maintenanceMode -ne "true") {
            # Only wait for user pods if not in maintenance mode
            kubectl wait --for=condition=ready pod -l app=sample-app,tier=user -n sample-app --timeout=120s
        }
        
        Write-Host "`n✅ Setup complete!" -ForegroundColor Green
        Write-Host "`nTo access the application, run:" -ForegroundColor Cyan
        Write-Host "  User:  kubectl port-forward -n sample-app svc/sample-app-user 9090:8080" -ForegroundColor White
        Write-Host "  Admin: kubectl port-forward -n sample-app svc/sample-app-admin 9092:8080" -ForegroundColor White
    }
    
    'enable' {
        Write-Header "Enabling Maintenance Mode"
        
        if (-not (Test-NamespaceExists)) {
            Write-Host "❌ Namespace 'sample-app' not found. Run setup first." -ForegroundColor Red
            exit 1
        }
        
        kubectl patch configmap app-config -n sample-app --type=json `
            -p '[{"op": "replace", "path": "/data/MAINTENANCE_MODE", "value": "true"}]'
        kubectl rollout restart deployment -n sample-app
        
        Write-Host "`nWaiting for rollout to complete..." -ForegroundColor Yellow
        kubectl rollout status deployment sample-app-admin -n sample-app --timeout=60s
        kubectl rollout status deployment sample-app-user -n sample-app --timeout=60s
        
        Write-Host "`n✅ Maintenance mode enabled!" -ForegroundColor Green
        Write-Host "`nPod status:" -ForegroundColor Cyan
        kubectl get pods -n sample-app
        
        Write-Host "`n📝 Expected behavior:" -ForegroundColor Yellow
        Write-Host "  - Admin pods: 1/1 Ready (ALWAYS accessible)" -ForegroundColor Green
        Write-Host "  - User pods:  0/1 Not Ready (removed from Service)" -ForegroundColor Red
    }
    
    'disable' {
        Write-Header "Disabling Maintenance Mode"
        
        if (-not (Test-NamespaceExists)) {
            Write-Host "❌ Namespace 'sample-app' not found. Run setup first." -ForegroundColor Red
            exit 1
        }
        
        kubectl patch configmap app-config -n sample-app --type=json `
            -p '[{"op": "replace", "path": "/data/MAINTENANCE_MODE", "value": "false"}]'
        kubectl rollout restart deployment -n sample-app
        
        Write-Host "`nWaiting for rollout to complete..." -ForegroundColor Yellow
        kubectl rollout status deployment sample-app-admin -n sample-app --timeout=60s
        kubectl rollout status deployment sample-app-user -n sample-app --timeout=60s
        
        Write-Host "`n✅ Maintenance mode disabled!" -ForegroundColor Green
        Write-Host "`nPod status:" -ForegroundColor Cyan
        kubectl get pods -n sample-app
        
        Write-Host "`n📝 All pods should be 1/1 Ready" -ForegroundColor Green
    }
    
    'status' {
        Write-Header "Current Status"
        
        if (-not (Test-NamespaceExists)) {
            Write-Host "❌ Namespace 'sample-app' not found. Run setup first." -ForegroundColor Red
            exit 1
        }
        
        $configMap = kubectl get configmap app-config -n sample-app -o jsonpath='{.data.MAINTENANCE_MODE}' 2>$null
        
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
            Write-Host "    ✓ Endpoints: $adminEndpoints" -ForegroundColor Green
        } else {
            Write-Host "    ✗ No endpoints available" -ForegroundColor Red
        }
        
        Write-Host "  User Service (blocked during maintenance):" -ForegroundColor Yellow
        $userEndpoints = kubectl get endpointslices -n sample-app -l kubernetes.io/service-name=sample-app-user -o jsonpath='{.items[0].endpoints[?(@.conditions.ready==true)].addresses[0]}' 2>$null
        if ($userEndpoints) {
            Write-Host "    ✓ Ready endpoints: $userEndpoints" -ForegroundColor Green
        } else {
            Write-Host "    ✗ No ready endpoints (removed from load balancer)" -ForegroundColor Red
        }
    }
    
    'clean' {
        Write-Header "Cleaning up"
        
        if (-not $Force) {
            Write-Host "⚠️  This will delete the entire sample-app namespace and stop Minikube." -ForegroundColor Yellow
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
            Write-Host "✓ Namespace already deleted" -ForegroundColor Green
        }
        
        if (Test-MinikubeRunning) {
            Write-Host "`nStopping Minikube..." -ForegroundColor Yellow
            minikube stop
        } else {
            Write-Host "✓ Minikube already stopped" -ForegroundColor Green
        }
        
        Write-Host "`n✅ Cleanup complete!" -ForegroundColor Green
    }
}

Write-Host ""
