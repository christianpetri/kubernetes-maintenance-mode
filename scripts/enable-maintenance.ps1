# Enable maintenance mode by updating the ConfigMap

Write-Host "🔧 Enabling maintenance mode..." -ForegroundColor Yellow

oc patch configmap app-config -n demo-503 -p '{\"data\":{\"MAINTENANCE_MODE\":\"true\"}}'

Write-Host "✅ Maintenance mode enabled" -ForegroundColor Green
Write-Host "📝 Restarting user pods to pick up the change..." -ForegroundColor Cyan

oc rollout restart deployment/demo-app-user -n demo-503

Write-Host "⏳ Waiting for rollout to complete..." -ForegroundColor Cyan
oc rollout status deployment/demo-app-user -n demo-503

Write-Host ""
Write-Host "✅ Maintenance mode is now active!" -ForegroundColor Green
Write-Host "   - User traffic will receive 503 errors" -ForegroundColor White
Write-Host "   - Admin access remains available" -ForegroundColor White
