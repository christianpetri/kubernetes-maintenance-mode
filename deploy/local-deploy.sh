#!/bin/bash
# Deploy OpenShift demo to local kind cluster
# Reference: https://kind.sigs.k8s.io/docs/user/quick-start/

set -e

echo "🚀 Deploying OpenShift Maintenance Demo to Local Kind Cluster"
echo "================================================================"

# Check if kind is installed
if ! command -v kind &> /dev/null; then
    echo "❌ kind is not installed"
    echo "📦 Install kind: https://kind.sigs.k8s.io/docs/user/quick-start/#installation"
    echo ""
    echo "Quick install options:"
    echo "  macOS:   brew install kind"
    echo "  Linux:   curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.30.0/kind-linux-amd64"
    echo "           chmod +x ./kind && sudo mv ./kind /usr/local/bin/kind"
    echo "  Windows: choco install kind"
    exit 1
fi

# Check if kubectl is installed
if ! command -v kubectl &> /dev/null; then
    echo "❌ kubectl is not installed"
    echo "📦 Install kubectl: https://kubernetes.io/docs/tasks/tools/"
    exit 1
fi

# Check if Docker is running
if ! docker info &> /dev/null; then
    echo "❌ Docker is not running"
    echo "🐳 Please start Docker Desktop or Docker daemon"
    exit 1
fi

# Create kind cluster if it doesn't exist
if kind get clusters | grep -q "demo-503-cluster"; then
    echo "✅ Kind cluster 'demo-503-cluster' already exists"
else
    echo "📦 Creating kind cluster..."
    kind create cluster --config kind-cluster.yaml --wait 5m
    echo "✅ Kind cluster created"
fi

# Set kubectl context to kind cluster
kubectl cluster-info --context kind-demo-503-cluster

echo ""
echo "🏗️  Building and loading Docker image into kind cluster..."
docker build -t demo-503:latest .

# Load image into kind cluster
kind load docker-image demo-503:latest --name demo-503-cluster
echo "✅ Image loaded into cluster"

echo ""
echo "📦 Deploying Kubernetes manifests..."

# Convert OpenShift manifests to standard Kubernetes
# (Routes -> Ingress, etc.)

# Create namespace
kubectl apply -f openshift/namespace.yaml

# Create ConfigMap
kubectl apply -f openshift/configmap.yaml

# Create Deployments (works as-is for Kubernetes)
kubectl apply -f openshift/deployment.yaml

# Create Services (works as-is for Kubernetes)
kubectl apply -f openshift/service.yaml

# Create Ingress (converted from OpenShift Routes)
kubectl apply -f kubernetes/ingress.yaml

# Create HPA (works as-is for Kubernetes)
kubectl apply -f openshift/hpa.yaml

echo ""
echo "⏳ Waiting for pods to be ready..."
kubectl wait --for=condition=ready pod -l app=demo-app -n demo-503 --timeout=120s

echo ""
echo "✅ Deployment complete!"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 Cluster Status:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
kubectl get nodes
echo ""
kubectl get pods -n demo-503 -o wide
echo ""
kubectl get svc -n demo-503
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🌐 Access Applications:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  User App:  http://localhost:8080"
echo "  Admin App: http://localhost:8080/admin"
echo ""
echo "  Alternatively, use port-forward:"
echo "    kubectl port-forward -n demo-503 svc/demo-app-user 8080:8080"
echo "    kubectl port-forward -n demo-503 svc/demo-app-admin 8081:8080"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🧪 Test Probes:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Liveness:  kubectl exec -n demo-503 -it \$(kubectl get pod -n demo-503 -l tier=user -o jsonpath='{.items[0].metadata.name}') -- curl localhost:8080/healthz"
echo "  Readiness: kubectl exec -n demo-503 -it \$(kubectl get pod -n demo-503 -l tier=user -o jsonpath='{.items[0].metadata.name}') -- curl localhost:8080/readyz"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔧 Maintenance Mode:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Enable:  kubectl patch configmap app-config -n demo-503 -p '{\"data\":{\"MAINTENANCE_MODE\":\"true\"}}'"
echo "  Disable: kubectl patch configmap app-config -n demo-503 -p '{\"data\":{\"MAINTENANCE_MODE\":\"false\"}}'"
echo "  Restart: kubectl rollout restart deployment/demo-app-user -n demo-503"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📝 Useful Commands:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  View logs:     kubectl logs -f -n demo-503 -l app=demo-app"
echo "  Describe pods: kubectl describe pods -n demo-503"
echo "  Get events:    kubectl get events -n demo-503 --sort-by='.lastTimestamp'"
echo "  Shell into pod: kubectl exec -it -n demo-503 \$(kubectl get pod -n demo-503 -l tier=user -o jsonpath='{.items[0].metadata.name}') -- /bin/bash"
echo ""
echo "  Delete cluster: kind delete cluster --name demo-503-cluster"
echo ""
