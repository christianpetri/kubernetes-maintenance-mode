# Kubernetes Maintenance Mode Demo

Practical guide for implementing maintenance mode using Flask's `@app.before_request` decorator with guaranteed admin access.

## Architecture Pattern

**Problem**: How do you disable maintenance mode if readiness checks block all traffic?

**Solution**: Separate deployments with different readiness behaviors:

- **User Pods**: Return 503 from `/ready` → Removed from load balancer
- **Admin Pods**: Always return 200 from `/ready` → Always accessible

## Flask Implementation Pattern

**Uses `@app.before_request` decorator** (Flask industry standard):

```python
@app.before_request
def check_maintenance():
    """Intercept all requests before routing."""
    # Skip probes and admin routes
    if request.path in ['/health', '/healthz', '/ready', '/readyz'] or request.path.startswith('/admin'):
        return None
    
    # Return 503 for user routes during maintenance
    if is_maintenance_mode():
        response = app.make_response(render_template_string(MAINTENANCE_PAGE))
        response.status_code = 503
        response.headers["Retry-After"] = "300"  # 5 minutes
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return response
```

**Benefits**: Single point of control, follows Flask patterns, no duplicate logic.

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

### Application Code Structure

```python
# Flask best practice: @app.before_request intercepts ALL requests before routing
@app.before_request
def check_maintenance():
    if request.path in ['/health', '/healthz', '/ready', '/readyz'] or request.path.startswith('/admin'):
        return None  # Skip maintenance check
    if is_maintenance_mode():
        return maintenance_response()  # 503 with proper headers

# Readiness probe: Different behavior for user vs admin pods
@app.route('/ready')
def ready():
    if is_admin_access():  # Admin pods always ready
        return {"status": "ready", "pod_type": "admin"}, 200
    if is_maintenance_mode():  # User pods fail during maintenance
        return {"status": "not_ready", "maintenance_mode": True}, 503
    return {"status": "ready"}, 200

# Liveness probe: Always 200 (don't restart healthy pods)
@app.route('/health')
def health():
    return {"status": "healthy"}, 200
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
