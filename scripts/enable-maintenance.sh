#!/bin/bash
# Enable maintenance mode by updating the ConfigMap

echo "🔧 Enabling maintenance mode..."

oc patch configmap app-config -n demo-503 -p '{"data":{"MAINTENANCE_MODE":"true"}}'

echo "✅ Maintenance mode enabled"
echo "📝 Restarting user pods to pick up the change..."

oc rollout restart deployment/demo-app-user -n demo-503

echo "⏳ Waiting for rollout to complete..."
oc rollout status deployment/demo-app-user -n demo-503

echo ""
echo "✅ Maintenance mode is now active!"
echo "   - User traffic will receive 503 errors"
echo "   - Admin access remains available"
