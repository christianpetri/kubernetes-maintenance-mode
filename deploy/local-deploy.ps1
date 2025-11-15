# Deploy OpenShift demo to local kind cluster (PowerShell)
# Reference: https://kind.sigs.k8s.io/docs/user/quick-start/

$ErrorActionPreference = "Stop"

Write-Host "🚀 Deploying OpenShift Maintenance Demo to Local Kind Cluster" -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan

# Check if kind is installed
if (!(Get-Command kind -ErrorAction SilentlyContinue)) {
    Write-Host "❌ kind is not installed" -ForegroundColor Red
    Write-Host "📦 Install kind: https://kind.sigs.k8s.io/docs/user/quick-start/#installation" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Quick install options:" -ForegroundColor Yellow
    Write-Host "  Windows: choco install kind" -ForegroundColor White
    Write-Host "  Or download: https://github.com/kubernetes-sigs/kind/releases" -ForegroundColor White
    exit 1
}

# Check if kubectl is installed
if (!(Get-Command kubectl -ErrorAction SilentlyContinue)) {
    Write-Host "❌ kubectl is not installed" -ForegroundColor Red
    Write-Host "📦 Install kubectl: https://kubernetes.io/docs/tasks/tools/" -ForegroundColor Yellow
    exit 1
}

# Check if Docker is running
try {
    docker info | Out-Null
} catch {
    Write-Host "❌ Docker is not running" -ForegroundColor Red
    Write-Host "🐳 Please start Docker Desktop" -ForegroundColor Yellow
    exit 1
}

# Create kind cluster if it doesn't exist
$clusterExists = kind get clusters | Select-String -Pattern "demo-503-cluster" -Quiet
if ($clusterExists) {
    Write-Host "✅ Kind cluster 'demo-503-cluster' already exists" -ForegroundColor Green
} else {
    Write-Host "📦 Creating kind cluster..." -ForegroundColor Yellow
    kind create cluster --config kind-cluster.yaml --wait 5m
    Write-Host "✅ Kind cluster created" -ForegroundColor Green
}

# Set kubectl context to kind cluster
kubectl cluster-info --context kind-demo-503-cluster

Write-Host ""
Write-Host "🏗️  Building and loading Docker image into kind cluster..." -ForegroundColor Yellow
docker build -t demo-503:latest .

# Load image into kind cluster
kind load docker-image demo-503:latest --name demo-503-cluster
Write-Host "✅ Image loaded into cluster" -ForegroundColor Green

Write-Host ""
Write-Host "📦 Deploying Kubernetes manifests..." -ForegroundColor Yellow

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

Write-Host ""
Write-Host "⏳ Waiting for pods to be ready..." -ForegroundColor Yellow
kubectl wait --for=condition=ready pod -l app=demo-app -n demo-503 --timeout=120s

Write-Host ""
Write-Host "✅ Deployment complete!" -ForegroundColor Green
Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "📊 Cluster Status:" -ForegroundColor Cyan
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
kubectl get nodes
Write-Host ""
kubectl get pods -n demo-503 -o wide
Write-Host ""
kubectl get svc -n demo-503
Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "🌐 Access Applications:" -ForegroundColor Cyan
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "  User App:  http://localhost:8080" -ForegroundColor White
Write-Host "  Admin App: http://localhost:8080/admin" -ForegroundColor White
Write-Host ""
Write-Host "  Alternatively, use port-forward:" -ForegroundColor Yellow
Write-Host "    kubectl port-forward -n demo-503 svc/demo-app-user 8080:8080" -ForegroundColor White
Write-Host "    kubectl port-forward -n demo-503 svc/demo-app-admin 8081:8080" -ForegroundColor White
Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "🧪 Test Probes:" -ForegroundColor Cyan
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "  Liveness:  kubectl exec -n demo-503 -it `$(kubectl get pod -n demo-503 -l tier=user -o jsonpath='{.items[0].metadata.name}') -- curl localhost:8080/healthz" -ForegroundColor White
Write-Host "  Readiness: kubectl exec -n demo-503 -it `$(kubectl get pod -n demo-503 -l tier=user -o jsonpath='{.items[0].metadata.name}') -- curl localhost:8080/readyz" -ForegroundColor White
Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "🔧 Maintenance Mode:" -ForegroundColor Cyan
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host '  Enable:  kubectl patch configmap app-config -n demo-503 -p ''{\"data\":{\"MAINTENANCE_MODE\":\"true\"}}\'\' -ForegroundColor White
Write-Host '  Disable: kubectl patch configmap app-config -n demo-503 -p ''{\"data\":{\"MAINTENANCE_MODE\":\"false\"}}\'\' -ForegroundColor White
Write-Host "  Restart: kubectl rollout restart deployment/demo-app-user -n demo-503" -ForegroundColor White
Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "📝 Useful Commands:" -ForegroundColor Cyan
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "  View logs:     kubectl logs -f -n demo-503 -l app=demo-app" -ForegroundColor White
Write-Host "  Describe pods: kubectl describe pods -n demo-503" -ForegroundColor White
Write-Host "  Get events:    kubectl get events -n demo-503 --sort-by='.lastTimestamp'" -ForegroundColor White
Write-Host "  Shell into pod: kubectl exec -it -n demo-503 `$(kubectl get pod -n demo-503 -l tier=user -o jsonpath='{.items[0].metadata.name}') -- /bin/bash" -ForegroundColor White
Write-Host ""
Write-Host "  Delete cluster: kind delete cluster --name demo-503-cluster" -ForegroundColor White
Write-Host ""
