# Maintenance Mode Demo - Kubernetes Edition

A demonstration of implementing maintenance mode in Kubernetes with 503 Service Unavailable responses
for regular users while **guaranteeing admin access remains available** during maintenance windows.

## Key Innovation: Admin Always Accessible

This demo solves a critical problem: **How do you disable maintenance mode if the readiness check
prevents all pods from receiving traffic?**

**Solution**: Separate deployments with different readiness behaviors:

- **User pods**: Return 503 from `/ready` during maintenance → removed from Service (no traffic)
- **Admin pods**: Always return 200 from `/ready` → stay in Service (always accessible)

This ensures administrators can **always access the control panel** to disable maintenance mode,
even when user traffic is blocked.

## Features

- **Dual-tier Architecture**: Separate user and admin deployments with independent readiness logic
- **Admin Always Ready**: Admin pods never fail readiness checks, preventing operational lockout
- **Graceful Degradation**: User pods removed from load balancer during maintenance (no restarts)
- **503 Error Handling**: Proper HTTP 503 responses with Retry-After headers
- **ConfigMap-Based Toggle**: Simple `kubectl patch` to enable/disable maintenance
- **Modern UI**: Clean, demo-ready interface with Kubernetes metrics

## Prerequisites

- **Minikube** installed (v1.30+)
- **Docker** installed and running
- **kubectl** configured
- Python 3.11+ (for local development)

## Architecture

```text
┌──────────────────────────────────────────────────────────┐
│              Kubernetes Cluster (Minikube)               │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────────┐         ┌───────────────────┐     │
│  │  User Ingress    │         │  Admin Ingress    │     │
│  │  (Public Access) │         │  (Admin Access)   │     │
│  └────────┬─────────┘         └─────────┬─────────┘     │
│           │                             │               │
│  ┌────────▼──────────┐         ┌────────▼─────────┐     │
│  │  User Service     │         │  Admin Service   │     │
│  │  (ClusterIP)      │         │  (ClusterIP)     │     │
│  └────────┬──────────┘         └────────┬─────────┘     │
│           │                             │               │
│  ┌────────▼──────────┐         ┌────────▼─────────┐     │
│  │ User Deployment   │         │ Admin Deployment │     │
│  │  (2 replicas)     │         │  (1 replica)     │     │
│  │                   │         │                  │     │
│  │ Readiness Logic:  │         │ Readiness Logic: │     │
│  │ ✗ FAILS when      │         │ ✓ ALWAYS 200     │     │
│  │   maintenance=true│         │   (guaranteed    │     │
│  │ ✗ Removed from LB │         │    admin access) │     │
│  └────────┬──────────┘         └────────┬─────────┘     │
│           │                             │               │
│           └──────────┬──────────────────┘               │
│                      │                                  │
│           ┌──────────▼──────────┐                       │
│           │   ConfigMap         │                       │
│           │   MAINTENANCE_MODE  │                       │
│           │   (true/false)      │                       │
│           └─────────────────────┘                       │
└──────────────────────────────────────────────────────────┘
```

**Critical Behavior During Maintenance:**

- User pods: Readiness probe returns 503 → Kubernetes marks as "Not Ready" → Removed from Service endpoints
- Admin pods: Readiness probe returns 200 → Always "Ready" → Always receives traffic
- Result: Users see 503 error, admins can always access control panel to disable maintenance

## Quick Start

### 1. Start Minikube

```powershell
minikube start --cpus=4 --memory=8192 --driver=docker
minikube status
```

### 2. Build and Deploy

```powershell
# Build the Docker image in Minikube's Docker environment
minikube docker-env | Invoke-Expression
docker build -t sample-app:latest .

# Deploy to Kubernetes
kubectl apply -f kubernetes/namespace.yaml
kubectl apply -f kubernetes/configmap.yaml
kubectl apply -f kubernetes/deployment.yaml
kubectl apply -f kubernetes/service.yaml
kubectl apply -f kubernetes/ingress.yaml

# Wait for pods to be ready
kubectl get pods -n sample-app -w
```

### 3. Access the Application

```powershell
# Port-forward user service (will show maintenance page when enabled)
kubectl port-forward -n sample-app svc/sample-app-user 9090:8080

# Port-forward admin service (ALWAYS accessible)
kubectl port-forward -n sample-app svc/sample-app-admin 9092:8080
```

Access at:

- **User endpoint**: <http://localhost:9090> (503 during maintenance)
- **Admin endpoint**: <http://localhost:9092> (always accessible)

### 4. Toggle Maintenance Mode

**Enable maintenance:**

```powershell
kubectl patch configmap app-config -n sample-app --type=json `
  -p '[{"op": "replace", "path": "/data/MAINTENANCE_MODE", "value": "true"}]'
kubectl rollout restart deployment -n sample-app
```

**Observe the behavior:**

```powershell
kubectl get pods -n sample-app
# You'll see:
# - Admin pods: 1/1 Ready (ALWAYS accessible)
# - User pods: 0/1 Not Ready (removed from Service)
```

**Disable maintenance:**

```powershell
kubectl patch configmap app-config -n sample-app --type=json `
  -p '[{"op": "replace", "path": "/data/MAINTENANCE_MODE", "value": "false"}]'
kubectl rollout restart deployment -n sample-app
```

## Understanding the Architecture

### Why Two Deployments?

The key innovation is using **separate deployments with different readiness probe behaviors**:

**User Deployment** (`sample-app-user`):

- Checks `MAINTENANCE_MODE` ConfigMap
- Returns 503 from `/ready` when maintenance is enabled
- Kubernetes marks pods as "Not Ready"
- Pods are **removed from Service** (no traffic routed)
- Pods stay **alive** (no restart, graceful degradation)

**Admin Deployment** (`sample-app-admin`):

- Has `X-Admin-Access=true` environment variable
- **Always returns 200** from `/ready` endpoint
- Kubernetes keeps pods as "Ready"
- Pods stay **in Service** (always receives traffic)
- Guarantees admin access to disable maintenance

### Health Probes Explained

**Liveness Probe** (`/health`):

- Purpose: Is the container alive and functioning?
- Both deployments: Always returns 200
- If fails: Kubernetes **restarts** the container
- During maintenance: Returns 200 (don't restart healthy pods)

**Readiness Probe** (`/ready`):

- Purpose: Can the pod serve traffic?
- User pods: Returns 503 during maintenance
- Admin pods: Always returns 200
- If fails: Kubernetes **removes from Service** (no traffic)
- During maintenance: User pods removed, admin pods stay

### Preventing Admin Lockout

**The Problem:** If all pods fail readiness checks, how do you disable maintenance mode?

**The Solution:** Admin pods use separate readiness logic:

```python
def is_admin_access():
    return os.environ.get('X-Admin-Access', '').lower() == 'true'

@app.route('/ready')
def ready():
    if is_admin_access():
        # Admin pods ALWAYS ready
        return jsonify({"status": "ready", "pod_type": "admin"}), 200
    
    if is_maintenance_mode():
        # User pods fail readiness during maintenance
        return jsonify({"status": "not_ready", "reason": "maintenance"}), 503
    
    return jsonify({"status": "ready", "pod_type": "user"}), 200
```

This ensures **administrators can always reach the control panel** to disable maintenance.

## Demo Script

### Full Demo Flow

1. **Show normal operation:**

   ```powershell
   # Check pod status (all ready)
   kubectl get pods -n sample-app
   # Output: All pods 1/1 Ready
   
   # Access user endpoint
   Start-Process http://localhost:9090  # Shows normal page
   ```

2. **Enable maintenance mode:**

   ```powershell
   kubectl patch configmap app-config -n sample-app --type=json `
     -p '[{"op": "replace", "path": "/data/MAINTENANCE_MODE", "value": "true"}]'
   kubectl rollout restart deployment -n sample-app
   Start-Sleep -Seconds 15
   ```

3. **Observe the critical behavior:**

   ```powershell
   kubectl get pods -n sample-app
   # Output:
   # sample-app-admin-xxx   1/1     Running   (ALWAYS READY)
   # sample-app-user-xxx    0/1     Running   (NOT READY - removed from Service)
   ```

4. **Verify traffic routing:**

   ```powershell
   # User endpoint - shows 503 maintenance page
   Start-Process http://localhost:9090
   
   # Admin endpoint - STILL ACCESSIBLE
   Start-Process http://localhost:9092  # Can disable maintenance from here!
   ```

5. **Disable maintenance from admin panel:**
   - Navigate to <http://localhost:9092>
   - Use the control panel to disable maintenance
   - Or use kubectl:

   ```powershell
   kubectl patch configmap app-config -n sample-app --type=json `
     -p '[{"op": "replace", "path": "/data/MAINTENANCE_MODE", "value": "false"}]'
   kubectl rollout restart deployment -n sample-app
   ```

6. **Verify restoration:**

   ```powershell
   kubectl get pods -n sample-app
   # Output: All pods back to 1/1 Ready
   
   Start-Process http://localhost:9090  # Shows normal page again
   ```

## Project Structure

```text
openshift-maintenance-demo/
├── app.py                          # Flask application with dual readiness logic
├── requirements.txt                # Python dependencies
├── pyproject.toml                  # Python project config + linting
├── Dockerfile                      # Container image
├── README.md                       # Main documentation
├── CONTRIBUTING.md                 # Developer guidelines
├── docs/
│   └── MAINTENANCE_DEMO.md         # Detailed architecture guide
├── kubernetes/                     # Kubernetes manifests (Minikube)
│   ├── namespace.yaml
│   ├── configmap.yaml
│   ├── deployment.yaml             # User + Admin deployments
│   ├── service.yaml
│   └── ingress.yaml
└── scripts/
    └── runme.ps1                   # Quick start script
```

## Development

### Local Testing

```powershell
# Install dependencies
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Run locally
$env:MAINTENANCE_MODE="false"
python app.py

# Test maintenance mode
$env:MAINTENANCE_MODE="true"
$env:X_ADMIN_ACCESS="true"  # Simulate admin pod
python app.py
```

### Code Quality

```powershell
# Install dev tools
pip install ruff mypy pre-commit

# Run linting
ruff check .
ruff format .
mypy app.py
```

## Troubleshooting

### Pods Not Ready After Maintenance Toggle

```powershell
# Check pod status
kubectl get pods -n sample-app

# Check pod logs
kubectl logs -n sample-app deployment/sample-app-user
kubectl logs -n sample-app deployment/sample-app-admin

# Verify ConfigMap
kubectl get configmap app-config -n sample-app -o yaml
```

### Port-Forward Connection Issues

```powershell
# Kill existing port-forwards
Get-Process kubectl | Stop-Process

# Restart port-forwards
kubectl port-forward -n sample-app svc/sample-app-user 9090:8080
kubectl port-forward -n sample-app svc/sample-app-admin 9092:8080
```

### Minikube Issues

```powershell
# Check Minikube status
minikube status

# Restart Minikube
minikube stop
minikube start --cpus=4 --memory=8192 --driver=docker

# Rebuild image in Minikube
minikube docker-env | Invoke-Expression
docker build -t sample-app:latest .
```

## Key Takeaways

1. **Admin Always Accessible**: Separate deployments with different readiness logic ensure admins can always disable maintenance
2. **Graceful Degradation**: User pods removed from Service (not restarted) during maintenance
3. **Clear HTTP Semantics**: 503 for maintenance, 200 for admin access
4. **ConfigMap-Based Toggle**: Simple `kubectl patch` to enable/disable maintenance
5. **Pod Status Verification**: `kubectl get pods` shows the architecture working (admin 1/1, user 0/1)

## Further Reading

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines and contribution workflow.

---

**Note**: This is a demonstration project for educational purposes.

## Contributing

Feel free to submit issues and enhancement requests!

## License

This is a demonstration project for educational purposes.
