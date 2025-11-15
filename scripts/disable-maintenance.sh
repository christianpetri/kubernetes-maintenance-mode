#!/bin/bash
# Disable maintenance mode by updating the ConfigMap

echo "🚀 Disabling maintenance mode..."

oc patch configmap app-config -n demo-503 -p '{"data":{"MAINTENANCE_MODE":"false"}}'

echo "✅ Maintenance mode disabled"
echo "📝 Restarting user pods to pick up the change..."

oc rollout restart deployment/demo-app-user -n demo-503

echo "⏳ Waiting for rollout to complete..."
oc rollout status deployment/demo-app-user -n demo-503

echo ""
echo "✅ Application is back to normal operation!"
echo "   - All users can now access the application"
