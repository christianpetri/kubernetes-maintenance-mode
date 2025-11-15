# Quick Reference: Local Deployment

## Choose Your Tool

| Tool | Use Case | Setup Time | Resources | Best For |
|------|----------|------------|-----------|----------|
| **kind** | Full K8s testing | 2 min | Low | Development & Testing |
| **Docker Compose** | Quick app test | 30 sec | Minimal | Application Testing |
| **OpenShift Local** | True OpenShift | 10 min | High (8GB+) | OpenShift-specific features |
| **minikube** | Feature-rich K8s | 3 min | Medium | Advanced K8s features |

## Quick Commands

### kind (Recommended)

```bash
# Install (macOS)
brew install kind kubectl

# Install (Windows)
choco install kind kubernetes-cli

# Deploy
./local-deploy.sh           # Linux/macOS
.\local-deploy.ps1          # Windows

# Access
kubectl port-forward -n demo-503 svc/demo-app-user 8080:8080

# Clean up
kind delete cluster --name demo-503-cluster
```

### Docker Compose

```bash
# Normal mode
docker-compose up

# Maintenance mode
docker-compose up web-maintenance

# Clean up
docker-compose down
```

## Test Probes

```bash
# Get pod name
POD=$(kubectl get pod -n demo-503 -l tier=user -o jsonpath='{.items[0].metadata.name}')

# Test liveness (should always return 200)
kubectl exec -n demo-503 -it $POD -- curl localhost:8080/healthz

# Test readiness (200 normal, 503 during maintenance)
kubectl exec -n demo-503 -it $POD -- curl localhost:8080/readyz
```

## Maintenance Mode

### Enable

```bash
kubectl patch configmap app-config -n demo-503 -p '{"data":{"MAINTENANCE_MODE":"true"}}'
kubectl rollout restart deployment/demo-app-user -n demo-503
```

### Disable

```bash
kubectl patch configmap app-config -n demo-503 -p '{"data":{"MAINTENANCE_MODE":"false"}}'
kubectl rollout restart deployment/demo-app-user -n demo-503
```

## Monitor

```bash
# View pods
kubectl get pods -n demo-503 -w

# View logs
kubectl logs -f -n demo-503 -l app=demo-app

# Check HPA
kubectl get hpa -n demo-503

# View events
kubectl get events -n demo-503 --sort-by='.lastTimestamp'
```

## Probe Endpoints (Kubernetes Standard)

| Endpoint | Type | Purpose | Status Codes |
|----------|------|---------|--------------|
| `/health` or `/healthz` | Liveness | Is container alive? | 200=healthy, 5xx=restart |
| `/ready` or `/readyz` | Readiness | Can serve traffic? | 200=ready, 503=remove from LB |
| `/startup` or `/startupz` | Startup | Has started? | 200=started, 5xx=still starting |

**Note**: The "z" suffix (`/healthz`, `/readyz`) is the Google/Kubernetes convention.

## Documentation

- **LOCAL_DEPLOYMENT.md** - Complete deployment guide
- **PROBES.md** - Liveness vs Readiness explanation
- **PROBE_COMPARISON.md** - Side-by-side comparison
- **README.md** - Full project documentation

## Troubleshooting

### Pods not starting?

```bash
kubectl describe pod -n demo-503 <pod-name>
kubectl logs -n demo-503 <pod-name>
```

### Can't access app?

```bash
# Use port-forward
kubectl port-forward -n demo-503 svc/demo-app-user 8080:8080
```

### Need to rebuild?

```bash
docker build -t demo-503:latest .
kind load docker-image demo-503:latest --name demo-503-cluster
kubectl rollout restart deployment/demo-app-user -n demo-503
```

## Access URLs

### kind cluster

- <http://localhost:8080> (via port-forward)
- <http://localhost:8080/admin>

### Docker Compose Ports

- <http://localhost:8888> (normal)
- <http://localhost:8081> (maintenance mode)
- <http://localhost:8888/admin>

---

**Need help?** See [LOCAL_DEPLOYMENT.md](LOCAL_DEPLOYMENT.md) for detailed instructions.
