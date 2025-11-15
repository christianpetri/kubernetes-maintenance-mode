# Disable maintenance mode by updating the ConfigMap

Write-Host "🚀 Disabling maintenance mode..." -ForegroundColor Yellow

oc patch configmap app-config -n demo-503 -p '{\"data\":{\"MAINTENANCE_MODE\":\"false\"}}'

Write-Host "✅ Maintenance mode disabled" -ForegroundColor Green
Write-Host "📝 Restarting user pods to pick up the change..." -ForegroundColor Cyan

oc rollout restart deployment/demo-app-user -n demo-503

Write-Host "⏳ Waiting for rollout to complete..." -ForegroundColor Cyan
oc rollout status deployment/demo-app-user -n demo-503

Write-Host ""
Write-Host "✅ Application is back to normal operation!" -ForegroundColor Green
Write-Host "   - All users can now access the application" -ForegroundColor White
