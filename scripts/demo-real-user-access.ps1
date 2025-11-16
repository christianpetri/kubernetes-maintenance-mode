# Demo Real User Access
# Shows how production users experience maintenance mode (via Ingress)

# Change to project root directory
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptPath
Set-Location $projectRoot

Write-Host "`n Setting up REAL user access demo`n" -ForegroundColor Cyan

# Step 1: Enable Ingress
Write-Host "Step 1: Enabling Ingress addon in Minikube..." -ForegroundColor Yellow
minikube addons enable ingress
if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to enable Ingress addon" -ForegroundColor Red
    exit 1
}

# Step 2: Deploy Ingress
Write-Host "`nStep 2: Deploying Ingress configuration..." -ForegroundColor Yellow
kubectl apply -f kubernetes/ingress.yaml
if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to deploy Ingress" -ForegroundColor Red
    exit 1
}

# Step 3: Wait for Ingress Controller
Write-Host "`nStep 3: Waiting for Ingress Controller to be ready..." -ForegroundColor Yellow
kubectl wait --namespace ingress-nginx --for=condition=ready pod --selector=app.kubernetes.io/component=controller --timeout=120s

# Step 4: Get Minikube IP
Write-Host "`nStep 4: Getting Minikube IP..." -ForegroundColor Yellow
$minikubeIp = minikube ip
Write-Host "Minikube IP: $minikubeIp" -ForegroundColor Green

# Step 5: Update hosts file
Write-Host "`nStep 5: Updating hosts file..." -ForegroundColor Yellow
$hostsPath = "$env:SystemRoot\System32\drivers\etc\hosts"

# Check if running as admin
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if ($isAdmin) {
    $hosts = Get-Content $hostsPath | Where-Object { $_ -notmatch "sample-app.local" }
    $hosts += ""
    $hosts += "# Sample App Demo (added by demo-real-user-access.ps1)"
    $hosts += "$minikubeIp sample-app.local"
    $hosts += "$minikubeIp admin.sample-app.local"
    $hosts | Set-Content $hostsPath
    Write-Host "Hosts file updated!" -ForegroundColor Green
} else {
    Write-Host "Not running as Administrator - cannot update hosts file automatically" -ForegroundColor Yellow
    Write-Host "`nPlease run this command as Administrator, OR manually add to:" -ForegroundColor Yellow
    Write-Host "$hostsPath" -ForegroundColor White
    Write-Host "`nAdd these lines:" -ForegroundColor Yellow
    Write-Host "$minikubeIp sample-app.local" -ForegroundColor White
    Write-Host "$minikubeIp admin.sample-app.local" -ForegroundColor White
    Write-Host "`nPress Enter when done..." -ForegroundColor Cyan
    Read-Host
}

# Step 6: Test connectivity
Write-Host "`n Testing connectivity...`n" -ForegroundColor Cyan
Write-Host "Waiting 10 seconds for Ingress to be fully ready..." -ForegroundColor Gray
Start-Sleep -Seconds 10

Write-Host "`nTest 1: User access (should work if maintenance OFF)" -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "http://sample-app.local" -UseBasicParsing -TimeoutSec 5
    Write-Host "User site accessible! Status: $($response.StatusCode)" -ForegroundColor Green
} catch {
    Write-Host "User site returned: $($_.Exception.Message)" -ForegroundColor Yellow
    Write-Host "   (This is expected if maintenance mode is ON)" -ForegroundColor Gray
}

Write-Host "`nTest 2: Admin access (should always work)" -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "http://admin.sample-app.local" -UseBasicParsing -TimeoutSec 5
    Write-Host "Admin site accessible! Status: $($response.StatusCode)" -ForegroundColor Green
} catch {
    Write-Host "Admin site not accessible: $($_.Exception.Message)" -ForegroundColor Red
}

# Step 7: Show demo instructions
Write-Host "`n Setup complete! How to demo:`n" -ForegroundColor Cyan

Write-Host "1. Test normal operation:" -ForegroundColor Yellow
Write-Host "   Open browser: http://sample-app.local" -ForegroundColor White

Write-Host "`n2. Enable maintenance mode:" -ForegroundColor Yellow
Write-Host "   kubectl exec -n sample-app deployment/redis -- redis-cli SET maintenance_mode true" -ForegroundColor White

Write-Host "`n3. Wait 10 seconds for readiness probes..." -ForegroundColor Yellow

Write-Host "`n4. Refresh browser:" -ForegroundColor Yellow
Write-Host "   http://sample-app.local" -ForegroundColor White
Write-Host "   You should see: 503 Service Temporarily Unavailable" -ForegroundColor Red

Write-Host "`n5. Admin still works:" -ForegroundColor Yellow
Write-Host "   http://admin.sample-app.local" -ForegroundColor White

Write-Host "`n6. Disable maintenance:" -ForegroundColor Yellow
Write-Host "   kubectl exec -n sample-app deployment/redis -- redis-cli SET maintenance_mode false" -ForegroundColor White

Write-Host "`n7. Wait 10 seconds, then refresh browser" -ForegroundColor Yellow

Write-Host "`n Monitor the drain:" -ForegroundColor Cyan
Write-Host "   kubectl get endpoints -n sample-app sample-app-user" -ForegroundColor White

Write-Host ""
