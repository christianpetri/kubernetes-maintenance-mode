# Kubernetes Maintenance Mode Demo

A practical guide demonstrating maintenance mode implementation with proper 503 behavior
while **guaranteeing admin access remains available**.

## Critical Architecture Pattern

**The Problem**: How do you disable maintenance mode if readiness checks prevent all pods from receiving traffic?

**The Solution**: Separate deployments with different readiness probe behaviors:

- **User Pods**: Return 503 from `/ready` during maintenance → Removed from Service
- **Admin Pods**: Always return 200 from `/ready` → Stay in Service (always accessible)

This pattern ensures **administrators can always access the control panel** to disable maintenance mode.

---

## Quick Start (Minikube)

### Prerequisites

```powershell
# Install Minikube and kubectl
winget install Kubernetes.minikube
winget install Kubernetes.kubectl

# Start Minikube
minikube start --cpus=4 --memory=8192 --driver=docker
```

### Deploy the Application

```powershell
# Build image in Minikube's Docker
minikube docker-env | Invoke-Expression
docker build -t sample-app:latest .

# Deploy to Kubernetes
kubectl apply -f kubernetes/namespace.yaml
kubectl apply -f kubernetes/configmap.yaml
kubectl apply -f kubernetes/deployment.yaml
kubectl apply -f kubernetes/service.yaml

# Wait for pods
kubectl get pods -n sample-app -w
```

### Access the Application

```powershell
# Terminal 1: User service (blocked during maintenance)
kubectl port-forward -n sample-app svc/sample-app-user 9090:8080

# Terminal 2: Admin service (ALWAYS accessible)
kubectl port-forward -n sample-app svc/sample-app-admin 9092:8080
```

- User endpoint: <http://localhost:9090>
- Admin endpoint: <http://localhost:9092>

---

## Demo Flow

### 1. Enable Maintenance Mode

```powershell
kubectl patch configmap app-config -n sample-app --type=json `
  -p '[{"op": "replace", "path": "/data/MAINTENANCE_MODE", "value": "true"}]'
kubectl rollout restart deployment -n sample-app
Start-Sleep -Seconds 15
```

### 2. Verify Pod Status

```powershell
kubectl get pods -n sample-app
```

**Expected output:**

```text
NAME                                READY   STATUS    RESTARTS   AGE
sample-app-admin-xxx                1/1     Running   0          20s
sample-app-user-yyy                 0/1     Running   0          20s
```

**Critical observation:**

- Admin pod: **1/1 Ready** (stays in Service, always accessible)
- User pod: **0/1 Not Ready** (removed from Service, no user traffic)

### 3. Test Access

```powershell
# User endpoint - Returns 503
Invoke-WebRequest http://localhost:9090 -UseBasicParsing
# Status: 503 Service Unavailable

# Admin endpoint - STILL WORKS
Invoke-WebRequest http://localhost:9092 -UseBasicParsing
# Status: 200 OK (can disable maintenance from here!)
```

### 4. Disable Maintenance

From admin panel at <http://localhost:9092>, or via kubectl:

```powershell
kubectl patch configmap app-config -n sample-app --type=json `
  -p '[{"op": "replace", "path": "/data/MAINTENANCE_MODE", "value": "false"}]'
kubectl rollout restart deployment -n sample-app
```

---

## Architecture Details

### Application Code (app.py)

```python
def is_admin_access():
    """Check if this pod has admin privileges"""
    return os.environ.get('X-Admin-Access', '').lower() == 'true'

def is_maintenance_mode():
    """Check if maintenance mode is enabled"""
    return os.environ.get('MAINTENANCE_MODE', 'false').lower() == 'true'

@app.route('/ready')
def ready():
    """Readiness probe - determines if pod receives traffic"""
    if is_admin_access():
        # Admin pods ALWAYS ready (guaranteed access)
        return jsonify({"status": "ready", "pod_type": "admin"}), 200
    
    if is_maintenance_mode():
        # User pods fail readiness during maintenance
        return jsonify({"status": "not_ready", "reason": "maintenance"}), 503
    
    return jsonify({"status": "ready", "pod_type": "user"}), 200

@app.route('/health')
def health():
    """Liveness probe - always returns 200 (don't restart healthy pods)"""
    return jsonify({"status": "healthy"}), 200
```

### Kubernetes Deployments

**User Deployment:**

```yaml
env:
- name: MAINTENANCE_MODE
  valueFrom:
    configMapKeyRef:
      name: app-config
      key: MAINTENANCE_MODE
readinessProbe:
  httpGet:
    path: /ready
    port: 8080
  # Returns 503 when MAINTENANCE_MODE=true
  # Pod marked "Not Ready" → Removed from Service
```

**Admin Deployment:**

```yaml
env:
- name: X-Admin-Access
  value: "true"
- name: MAINTENANCE_MODE
  value: "false"  # Ignored by admin readiness logic
readinessProbe:
  httpGet:
    path: /ready
    port: 8080
  # ALWAYS returns 200 (admin check bypasses maintenance)
  # Pod stays "Ready" → Always in Service
```

---

## Key Concepts

### Readiness vs Liveness Probes

| Probe Type | Endpoint | Purpose | Failure Action | During Maintenance |
|------------|----------|---------|----------------|-------------------|
| **Liveness** | `/health` | Is container alive? | **Restart** pod | ✅ Returns 200 |
| **Readiness** | `/ready` | Can serve traffic? | **Remove** from Service | User: ❌ 503, Admin: ✅ 200 |

**Critical difference:**

- Liveness failure → Pod dies and restarts
- Readiness failure → Pod stays alive but removed from load balancer

### Why This Pattern Works

1. **Graceful Degradation**: User pods stay running (no restart) but don't receive traffic
2. **Admin Always Accessible**: Admin pods stay in Service, can always reach control panel
3. **No Operational Lockout**: Even during maintenance, admins can disable it
4. **Clear Status**: `kubectl get pods` shows readiness state (1/1 vs 0/1)

---

## Troubleshooting

### Admin Pods Not Accessible

```powershell
# Check admin pod has correct env var
kubectl get pod -n sample-app -l app=sample-app,tier=admin -o yaml | Select-String -Pattern "X-Admin-Access"

# Should output: value: "true"
```

### User Pods Not Failing Readiness

```powershell
# Check ConfigMap
kubectl get configmap app-config -n sample-app -o yaml

# Verify MAINTENANCE_MODE: "true"
```

### Pods Not Restarting After ConfigMap Change

```powershell
# ConfigMap changes require pod restart
kubectl rollout restart deployment -n sample-app

# Watch rollout progress
kubectl rollout status deployment sample-app-user -n sample-app
kubectl rollout status deployment sample-app-admin -n sample-app
```

---

## Cleanup

```powershell
# Delete namespace (removes everything)
kubectl delete namespace sample-app

# Stop Minikube
minikube stop
```

---

## Lessons Learned

1. **Separate Deployments**: Critical for different readiness behaviors
2. **Environment Variables**: Use to distinguish pod types (admin vs user)
3. **Readiness ≠ Liveness**: Readiness removes from Service, liveness restarts pod
4. **ConfigMap Pattern**: Easy to toggle maintenance without code changes
5. **Graceful Degradation**: Pods stay alive during maintenance (no restart)
6. **Operational Safety**: Admin access guaranteed even during maintenance

---

## Real-World Considerations

### Production Enhancements

1. **Authentication**: Add proper auth to admin endpoints (OAuth, API keys)
2. **Monitoring**: Alert when pods are in Not Ready state for extended periods
3. **Logging**: Log maintenance mode changes for audit trail
4. **Database Maintenance**: Coordinate with database read-only mode
5. **External Dependencies**: Consider upstream/downstream service impacts

### Scaling Patterns

```yaml
# Add HPA for user deployment
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: sample-app-user-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: sample-app-user
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

---

## References

- [Kubernetes Probes Documentation](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/)
- [HTTP 503 Service Unavailable](https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/503)
- [Graceful Shutdown in Kubernetes](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/)
