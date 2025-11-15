#!/bin/bash
# Deploy all OpenShift resources

echo "🚀 Deploying Demo 503 Application to OpenShift..."

# Create namespace
echo "📦 Creating namespace..."
oc apply -f openshift/namespace.yaml

# Create ConfigMap
echo "⚙️  Creating ConfigMap..."
oc apply -f openshift/configmap.yaml

# Create Deployments
echo "🔧 Creating deployments..."
oc apply -f openshift/deployment.yaml

# Create Services
echo "🌐 Creating services..."
oc apply -f openshift/service.yaml

# Create Routes
echo "🛣️  Creating routes..."
oc apply -f openshift/route.yaml

# Create HPA
echo "📊 Creating Horizontal Pod Autoscaler..."
oc apply -f openshift/hpa.yaml

echo ""
echo "✅ Deployment complete!"
echo ""
echo "📝 Getting route URLs..."
oc get routes -n demo-503

echo ""
echo "💡 Next steps:"
echo "   1. Access the user route to see the normal application"
echo "   2. Access the admin route to see the admin panel"
echo "   3. Run ./scripts/enable-maintenance.sh to enable maintenance mode"
echo "   4. User traffic will get 503, but admin access remains"
