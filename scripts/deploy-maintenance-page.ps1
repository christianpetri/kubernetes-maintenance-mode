# Deploy Custom 503 Maintenance Page
# Sets up beautiful maintenance page served by Ingress

Write-Host "`n🎨 Deploying Custom 503 Maintenance Page`n" -ForegroundColor Cyan

# Step 1: Deploy maintenance page service
Write-Host "Step 1: Deploying maintenance page service..." -ForegroundColor Yellow
kubectl apply -f kubernetes/maintenance-page-deployment.yaml

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to deploy maintenance page" -ForegroundColor Red
    exit 1
}

# Step 2: Wait for pod to be ready
Write-Host "`nStep 2: Waiting for maintenance page pod to be ready..." -ForegroundColor Yellow
kubectl wait --for=condition=ready pod -l app=maintenance-page -n sample-app --timeout=60s

if ($LASTEXITCODE -ne 0) {
    Write-Host "⚠️  Timeout waiting for pod, but continuing..." -ForegroundColor Yellow
}

# Step 3: Update Ingress with custom error page
Write-Host "`nStep 3: Updating Ingress configuration..." -ForegroundColor Yellow
kubectl apply -f kubernetes/ingress.yaml

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to update Ingress" -ForegroundColor Red
    exit 1
}

# Step 4: Verify deployment
Write-Host "`n📊 Deployment Status:`n" -ForegroundColor Cyan

Write-Host "Maintenance Page Pod:" -ForegroundColor Yellow
kubectl get pods -n sample-app -l app=maintenance-page

Write-Host "`nMaintenance Page Service:" -ForegroundColor Yellow
kubectl get svc -n sample-app maintenance-page

Write-Host "`nIngress Configuration:" -ForegroundColor Yellow
kubectl get ingress -n sample-app sample-app-ingress

# Step 5: Test the maintenance page directly
Write-Host "`n🧪 Testing maintenance page...`n" -ForegroundColor Cyan

$testPassed = $false
try {
    # Start port-forward in background
    $job = Start-Job -ScriptBlock {
        kubectl port-forward -n sample-app svc/maintenance-page 8889:80
    }
    
    Start-Sleep -Seconds 3
    
    $response = Invoke-WebRequest -Uri "http://localhost:8889" -UseBasicParsing -TimeoutSec 5
    if ($response.StatusCode -eq 200 -and $response.Content -match "Maintenance") {
        Write-Host "✅ Maintenance page is accessible!" -ForegroundColor Green
        $testPassed = $true
    }
} catch {
    Write-Host "⚠️  Could not test maintenance page: $($_.Exception.Message)" -ForegroundColor Yellow
} finally {
    # Stop the port-forward job
    if ($job) {
        Stop-Job -Job $job -ErrorAction SilentlyContinue
        Remove-Job -Job $job -ErrorAction SilentlyContinue
    }
}

# Step 6: Show how to test the complete flow
Write-Host "`n✨ Setup Complete!`n" -ForegroundColor Cyan

Write-Host "📝 How to test the custom 503 page:`n" -ForegroundColor Yellow

Write-Host "1️⃣  Make sure Ingress is enabled:" -ForegroundColor Cyan
Write-Host "   minikube addons enable ingress" -ForegroundColor White

Write-Host "`n2️⃣  Update your hosts file (as Administrator):" -ForegroundColor Cyan
Write-Host "   C:\Windows\System32\drivers\etc\hosts" -ForegroundColor White
Write-Host "   Add: $(minikube ip) sample-app.local" -ForegroundColor Green

Write-Host "`n3️⃣  Enable maintenance mode:" -ForegroundColor Cyan
Write-Host "   kubectl exec -n sample-app deployment/redis -- redis-cli SET maintenance_mode true" -ForegroundColor White

Write-Host "`n4️⃣  Wait 10 seconds for readiness probes..." -ForegroundColor Cyan

Write-Host "`n5️⃣  Visit in browser:" -ForegroundColor Cyan
Write-Host "   http://sample-app.local" -ForegroundColor White
Write-Host "   You'll see: 🔧 Beautiful gradient maintenance page!" -ForegroundColor Green

Write-Host "`n6️⃣  Verify Service endpoints are empty:" -ForegroundColor Cyan
Write-Host "   kubectl get endpoints -n sample-app sample-app-user" -ForegroundColor White

Write-Host "`n7️⃣  Disable maintenance:" -ForegroundColor Cyan
Write-Host "   kubectl exec -n sample-app deployment/redis -- redis-cli SET maintenance_mode false" -ForegroundColor White

Write-Host "`n8️⃣  Wait 10 seconds, then refresh browser" -ForegroundColor Cyan
Write-Host "   You'll see: Your Flask application! ✨" -ForegroundColor Green

Write-Host "`n📚 Documentation:" -ForegroundColor Cyan
Write-Host "   docs/CUSTOM_503_PAGES.md          - Complete guide" -ForegroundColor White
Write-Host "   docs/MAINTENANCE_PAGE_QUICK_REF.md - Quick reference" -ForegroundColor White
Write-Host "   docs/PRODUCTION_ROUTING.md         - Routing explained" -ForegroundColor White

Write-Host "`n🎯 Quick commands:" -ForegroundColor Cyan
Write-Host "   # Enable maintenance" -ForegroundColor Gray
Write-Host "   kubectl exec -n sample-app deployment/redis -- redis-cli SET maintenance_mode true" -ForegroundColor White
Write-Host "`n   # Check endpoints (should be empty)" -ForegroundColor Gray
Write-Host "   kubectl get endpoints -n sample-app sample-app-user" -ForegroundColor White
Write-Host "`n   # Disable maintenance" -ForegroundColor Gray
Write-Host "   kubectl exec -n sample-app deployment/redis -- redis-cli SET maintenance_mode false" -ForegroundColor White

Write-Host "`n" -ForegroundColor White
