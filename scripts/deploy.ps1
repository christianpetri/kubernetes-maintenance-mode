# Deploy all OpenShift resources

Write-Host "🚀 Deploying Demo 503 Application to OpenShift..." -ForegroundColor Cyan

# Create namespace
Write-Host "📦 Creating namespace..." -ForegroundColor Yellow
oc apply -f openshift/namespace.yaml

# Create ConfigMap
Write-Host "⚙️  Creating ConfigMap..." -ForegroundColor Yellow
oc apply -f openshift/configmap.yaml

# Create Deployments
Write-Host "🔧 Creating deployments..." -ForegroundColor Yellow
oc apply -f openshift/deployment.yaml

# Create Services
Write-Host "🌐 Creating services..." -ForegroundColor Yellow
oc apply -f openshift/service.yaml

# Create Routes
Write-Host "🛣️  Creating routes..." -ForegroundColor Yellow
oc apply -f openshift/route.yaml

# Create HPA
Write-Host "📊 Creating Horizontal Pod Autoscaler..." -ForegroundColor Yellow
oc apply -f openshift/hpa.yaml

Write-Host ""
Write-Host "✅ Deployment complete!" -ForegroundColor Green
Write-Host ""
Write-Host "📝 Getting route URLs..." -ForegroundColor Cyan
oc get routes -n demo-503

Write-Host ""
Write-Host "💡 Next steps:" -ForegroundColor Cyan
Write-Host "   1. Access the user route to see the normal application" -ForegroundColor White
Write-Host "   2. Access the admin route to see the admin panel" -ForegroundColor White
Write-Host "   3. Run .\scripts\enable-maintenance.ps1 to enable maintenance mode" -ForegroundColor White
Write-Host "   4. User traffic will get 503, but admin access remains" -ForegroundColor White
