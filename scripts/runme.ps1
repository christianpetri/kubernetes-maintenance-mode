#!/usr/bin/env pwsh
# Kubernetes Maintenance Mode Demo - Quick Start Script

param(
    [Parameter()]
    [ValidateSet('setup', 'enable', 'disable', 'status', 'clean')]
    [string]$Action = 'status'
)

$ErrorActionPreference = 'Stop'

function Write-Header {
    param([string]$Text)
    Write-Host "`n=== $Text ===" -ForegroundColor Cyan
}

switch ($Action) {
    'setup' {
        Write-Header "Setting up Minikube cluster and deploying application"
        
        Write-Host "Starting Minikube..." -ForegroundColor Yellow
        minikube start --cpus=4 --memory=8192 --driver=docker
        
        Write-Host "`nBuilding Docker image in Minikube..." -ForegroundColor Yellow
        minikube docker-env | Invoke-Expression
        docker build -t sample-app:latest .
        
        Write-Host "`nDeploying to Kubernetes..." -ForegroundColor Yellow
        kubectl apply -f kubernetes/namespace.yaml
        kubectl apply -f kubernetes/configmap.yaml
        kubectl apply -f kubernetes/deployment.yaml
        kubectl apply -f kubernetes/service.yaml
        kubectl apply -f kubernetes/ingress.yaml
        
        Write-Host "`nWaiting for pods to be ready..." -ForegroundColor Yellow
        kubectl wait --for=condition=ready pod -l app=sample-app -n sample-app --timeout=120s
        
        Write-Host "`n✅ Setup complete!" -ForegroundColor Green
        Write-Host "`nTo access the application, run:" -ForegroundColor Cyan
        Write-Host "  User:  kubectl port-forward -n sample-app svc/sample-app-user 9090:8080" -ForegroundColor White
        Write-Host "  Admin: kubectl port-forward -n sample-app svc/sample-app-admin 9092:8080" -ForegroundColor White
    }
    
    'enable' {
        Write-Header "Enabling Maintenance Mode"
        
        kubectl patch configmap app-config -n sample-app --type=json `
            -p '[{"op": "replace", "path": "/data/MAINTENANCE_MODE", "value": "true"}]'
        kubectl rollout restart deployment -n sample-app
        
        Write-Host "`nWaiting for rollout to complete..." -ForegroundColor Yellow
        Start-Sleep -Seconds 15
        
        Write-Host "`n✅ Maintenance mode enabled!" -ForegroundColor Green
        Write-Host "`nPod status:" -ForegroundColor Cyan
        kubectl get pods -n sample-app
        
        Write-Host "`n📝 Expected behavior:" -ForegroundColor Yellow
        Write-Host "  - Admin pods: 1/1 Ready (ALWAYS accessible)" -ForegroundColor Green
        Write-Host "  - User pods:  0/1 Not Ready (removed from Service)" -ForegroundColor Red
    }
    
    'disable' {
        Write-Header "Disabling Maintenance Mode"
        
        kubectl patch configmap app-config -n sample-app --type=json `
            -p '[{"op": "replace", "path": "/data/MAINTENANCE_MODE", "value": "false"}]'
        kubectl rollout restart deployment -n sample-app
        
        Write-Host "`nWaiting for rollout to complete..." -ForegroundColor Yellow
        Start-Sleep -Seconds 15
        
        Write-Host "`n✅ Maintenance mode disabled!" -ForegroundColor Green
        Write-Host "`nPod status:" -ForegroundColor Cyan
        kubectl get pods -n sample-app
        
        Write-Host "`n📝 All pods should be 1/1 Ready" -ForegroundColor Green
    }
    
    'status' {
        Write-Header "Current Status"
        
        $configMap = kubectl get configmap app-config -n sample-app -o jsonpath='{.data.MAINTENANCE_MODE}'
        
        Write-Host "`nMaintenance Mode: " -NoNewline -ForegroundColor Cyan
        if ($configMap -eq "true") {
            Write-Host "ENABLED" -ForegroundColor Red
        } else {
            Write-Host "DISABLED" -ForegroundColor Green
        }
        
        Write-Host "`nPod Status:" -ForegroundColor Cyan
        kubectl get pods -n sample-app
        
        Write-Host "`nService Endpoints:" -ForegroundColor Cyan
        kubectl get endpointslices -n sample-app -o wide
    }
    
    'clean' {
        Write-Header "Cleaning up"
        
        Write-Host "Deleting namespace..." -ForegroundColor Yellow
        kubectl delete namespace sample-app
        
        Write-Host "`nStopping Minikube..." -ForegroundColor Yellow
        minikube stop
        
        Write-Host "`n✅ Cleanup complete!" -ForegroundColor Green
    }
}

Write-Host ""
