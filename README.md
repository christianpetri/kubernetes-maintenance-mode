# Maintenance Mode Demo - Kubernetes Edition

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Kubernetes](https://img.shields.io/badge/Kubernetes-1.28+-blue.svg)](https://kubernetes.io/)
[![Flask](https://img.shields.io/badge/Flask-3.0+-green.svg)](https://flask.palletsprojects.com/)

Kubernetes maintenance mode using Flask's `@app.before_request` with 503 responses for users
while **guaranteeing admin access remains available**.

**Quick Links:**
[Architecture](#architecture) •
[Quick Start](#quick-start) •
[Flask Pattern](#flask-best-practice-pattern) •
[Troubleshooting](#troubleshooting)

## Table of Contents

- [Key Innovation](#key-innovation-admin-always-accessible)
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Understanding the Architecture](#understanding-the-architecture)
- [Demo Script](#demo-script)
- [Project Structure](#project-structure)
- [Development](#development)
- [Troubleshooting](#troubleshooting)
- [Key Takeaways](#key-takeaways)
- [Further Reading](#further-reading)

## Key Innovation: Admin Always Accessible

Solves: **How do you disable maintenance mode if readiness checks prevent all pods from receiving traffic?**

**Solution**: Separate deployments with different readiness behaviors:

- **User pods**: Return 503 from `/ready` during maintenance → removed from Service
- **Admin pods**: Always return 200 from `/ready` → stay in Service (always accessible)

## Flask Best Practice Pattern

Uses Flask's **`@app.before_request` decorator** (industry standard):

```python
@app.before_request
def check_maintenance():
    """Intercept all requests before routing - Flask standard pattern."""
    if request.path in ['/health', '/healthz', '/ready', '/readyz'] or request.path.startswith('/admin'):
        return None
    
    if is_maintenance_mode():
        return maintenance_response()  # 503 with proper headers
```

**Benefits:**

- Single point of maintenance control (DRY principle)
- Clean separation of concerns
- No duplicate logic in route handlers
- Follows Flask documentation patterns

## Features

- **Flask Best Practice**: `@app.before_request` decorator (industry standard pattern)
- **Admin Always Accessible**: Separate deployment ensures control panel availability
- **Graceful Degradation**: Pods removed from load balancer (no restarts needed)
- **Proper HTTP Semantics**: 503 with Retry-After and Cache-Control headers
- **ConfigMap Toggle**: Simple `kubectl patch` to enable/disable
- **Modern UI**: Clean interface with Kubernetes metrics

## What You'll Learn

This demo teaches practical Kubernetes patterns for production operations:

✅ **Kubernetes Readiness Probes** - How to use health checks to control traffic routing  
✅ **Service Endpoint Management** - Understanding how Kubernetes routes traffic to healthy pods  
✅ **Graceful Degradation** - Implementing maintenance mode without pod restarts  
✅ **Operational Safety** - Preventing admin lockout during maintenance windows  
✅ **ConfigMap-Based Configuration** - Dynamic application configuration in Kubernetes  
✅ **Multi-Deployment Architecture** - When to use separate deployments for different roles  

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

**Get started in 5 minutes:**

### 1. Clone the Repository

```powershell
git clone https://github.com/YourOrg/Demo_503.git
cd Demo_503
```

### 2. Setup the Environment

```powershell
.\scripts\runme.ps1 setup
```

This will:

- Start Minikube cluster (Docker driver, 4 CPUs, 8GB RAM)
- Build the Flask application Docker image
- Deploy user and admin services to Kubernetes
- Wait for all pods to be ready

### 3. Access the Application

Open your browser:

- **User Interface:** `http://localhost:30080`
- **Admin Interface:** `http://localhost:30080/admin`

### 4. Enable Maintenance Mode

```powershell
.\scripts\runme.ps1 enable
```

Result:

- User page shows: "503 - Maintenance Mode"
- Admin page still accessible and shows "Maintenance Mode is ON"

### 5. Disable Maintenance Mode

```powershell
.\scripts\runme.ps1 disable
```

Or use the admin panel button to toggle maintenance mode via UI.

### Additional Commands

```powershell
# Check maintenance status and pod health
.\scripts\runme.ps1 status

# Clean up everything
.\scripts\runme.ps1 clean
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

### Interactive Demonstration

**1. Show normal operation:**

```powershell
# Check pod status (all ready)
.\scripts\runme.ps1 status
# Output: Maintenance Mode is OFF, all pods 1/1 Ready

# Access the application
Start-Process http://localhost:30080  # Shows normal page
```

**2. Enable maintenance mode:**

```powershell
.\scripts\runme.ps1 enable
```

**3. Observe the critical behavior:**

```powershell
.\scripts\runme.ps1 status
# Output:
# Maintenance Mode is ON
# sample-app-admin-xxx   1/1     Running   (ALWAYS READY)
# sample-app-user-xxx    0/1     Running   (NOT READY - removed from Service)
```

**4. Verify traffic routing:**

- User endpoint: <http://localhost:30080> - shows 503 maintenance page
- Admin endpoint: <http://localhost:30080/admin> - STILL ACCESSIBLE
- Admin can disable maintenance from the control panel!

**5. Disable maintenance:**

```powershell
.\scripts\runme.ps1 disable
# Or click the button in admin panel at http://localhost:30080/admin
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

## Real-World Use Cases

This maintenance mode pattern is applicable to many production scenarios:

### 🔧 Planned Maintenance Windows

- Database migrations requiring application downtime
- Infrastructure upgrades (storage, network, security patches)
- Third-party service integrations causing temporary unavailability
- Admins need access to monitor progress and disable maintenance early if possible

### 🚀 Deployment Strategies

- Blue-green deployments with user-facing traffic paused
- Canary releases where new versions are tested by admins first
- Database schema changes requiring application-level coordination

### 🛡️ Emergency Response

- DDoS mitigation: Block public traffic while admins investigate
- Security incidents: Isolate user access while maintaining operational visibility
- Performance issues: Reduce load while diagnosing problems

### 🔄 Data Processing

- Batch processing jobs that require exclusive database access
- ETL operations that temporarily block user queries
- Cache rebuilding or reindexing operations

### 🏢 Enterprise Scenarios

- Compliance audits requiring system freeze
- Financial close periods with read-only data
- Legal holds where user modifications must be prevented

**Key Benefit:** In all cases, administrators retain full access to monitor, manage, and resolve issues
without being locked out by the maintenance mode itself.

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
