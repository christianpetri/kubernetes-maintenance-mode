#!/usr/bin/env pwsh
# Deploy updated app.py to running Kubernetes pods

Write-Host "`n🚀 DEPLOYING APP UPDATE TO KUBERNETES`n" -ForegroundColor Cyan

Write-Host "Step 1: Copy new app.py to all pods..." -ForegroundColor Yellow

$pods = kubectl get pods -n sample-app -l app=sample-app -o jsonpath='{.items[*].metadata.name}'
foreach ($pod in $pods.Split(' ')) {
    if ($pod) {
        Write-Host "  Updating $pod..." -ForegroundColor Cyan
        kubectl cp ../app.py "sample-app/${pod}:/app/app.py"
    }
}

Write-Host "`nStep 2: Restart app processes..." -ForegroundColor Yellow
kubectl delete pods -n sample-app -l app=sample-app

Write-Host "`nStep 3: Wait for pods to restart..." -ForegroundColor Yellow
Start-Sleep -Seconds 10
kubectl wait --for=condition=ready pod -l app=sample-app -n sample-app --timeout=30s

Write-Host "`n✅ Verifying deployment..." -ForegroundColor Green
$lines = kubectl exec -n sample-app deployment/sample-app-user -- wc -l /app/app.py
Write-Host "Pod app.py: $lines"

if ($lines -match "482") {
    Write-Host "`n🎉 SUCCESS! New version deployed (482 lines)" -ForegroundColor Green
} else {
    Write-Host "`n⚠️  Warning: Expected 482 lines" -ForegroundColor Yellow
}

Write-Host "`n📊 Pod Status:" -ForegroundColor Cyan
kubectl get pods -n sample-app
