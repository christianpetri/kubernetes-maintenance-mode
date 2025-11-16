# Scripts Directory

PowerShell automation scripts for managing the Kubernetes maintenance mode demo.

## Quick Reference

| Script | Purpose | Usage |
|--------|---------|-------|
| `runme.ps1` | Main automation script | `.\runme.ps1 -Action setup` |
| `teardown.ps1` | Complete teardown with multiple modes | `.\teardown.ps1` |
| `test-endpoints.ps1` | Comprehensive endpoint testing | `.\test-endpoints.ps1` |

---

## Detailed Documentation

### runme.ps1

**Main automation script** - Handles full lifecycle management.

**Actions:**

```powershell
# Initial setup (build + deploy everything)
.\runme.ps1 -Action setup

# Enable maintenance mode
.\runme.ps1 -Action enable

# Disable maintenance mode
.\runme.ps1 -Action disable

# Check current status
.\runme.ps1 -Action status

# Clean up everything (basic)
.\runme.ps1 -Action clean
```

**What it does:**

- **setup**: Starts Minikube, enables ingress, builds Docker image, deploys all Kubernetes resources
- **enable**: Sets maintenance mode ON via Redis
- **disable**: Sets maintenance mode OFF via Redis
- **status**: Shows pod status, endpoints, and maintenance mode state
- **clean**: Deletes namespace and stops Minikube (basic cleanup)

**Prerequisites:** Docker Desktop running, Minikube installed

---

### teardown.ps1

**Complete teardown script** - Safe cleanup with multiple options.

**Usage:**

```powershell
# Basic teardown (delete namespace, stop Minikube)
.\teardown.ps1

# Keep Minikube running (only delete namespace)
.\teardown.ps1 -KeepMinikube

# Deep clean (delete everything including Minikube data)
.\teardown.ps1 -DeepClean

# Force without confirmation
.\teardown.ps1 -Force

# Combined options
.\teardown.ps1 -DeepClean -Force
```

**What it does:**

1. Stops all port-forward processes
2. Deletes sample-app namespace (waits for completion)
3. Stops Minikube cluster (unless -KeepMinikube)
4. With -DeepClean: Deletes Minikube data and Docker images

**When to use:**

- End of demo session: `.\teardown.ps1`
- Between demos (keep Minikube): `.\teardown.ps1 -KeepMinikube`
- Complete reset: `.\teardown.ps1 -DeepClean`

**Prerequisites:** None (works even if resources partially exist)

---

### test-endpoints.ps1

**Comprehensive endpoint testing** - Verifies all functionality.

```powershell
# Test with tunnel URLs from runme.ps1 setup
.\test-endpoints.ps1

# Test with custom URLs
.\test-endpoints.ps1 -UserServiceUrl "http://localhost:52876" -AdminServiceUrl "http://localhost:52875"
```

**Test Coverage:**

1. Redis connection working
2. Maintenance toggle (ON/OFF)
3. Readiness probe responding correctly
4. Service endpoints updating
5. Pods becoming Ready/NotReady
6. Admin access always available
7. User access blocked during maintenance

**Output:** Pass/fail for each test with detailed diagnostics

**Prerequisites:** Service tunnels running (opened by `runme.ps1 setup`)

---

### test-all-buttons.ps1

**Test all admin UI buttons** - Automated UI testing.

```powershell
.\test-all-buttons.ps1
```

**What it tests:**

- Enable/disable maintenance buttons
- Health check endpoint
- Readiness probe endpoint
- Admin dashboard access
- User routes during maintenance

**Prerequisites:** Service tunnel to admin service (opened by runme.ps1 setup)

---

## Common Workflows

### First-Time Setup

```powershell
# 1. Start Docker Desktop (wait for it to be ready)

# 2. Run automated setup
.\runme.ps1 -Action setup

# 3. Access via service tunnels
# Check the tunnel windows for access URLs (usually 127.0.0.1:xxxxx)
```

### Demo Workflow

```powershell
# 1. Setup and deploy
.\runme.ps1 -Action setup

# 2. Access application via service tunnels
# Check the tunnel windows for auto-assigned URLs (e.g., http://127.0.0.1:52511)

# 3. Enable maintenance mode
# Option A: Via admin panel button
# Option B: Via CLI
.\runme.ps1 -Action enable

# 4. Verify behavior
.\test-endpoints.ps1

# 5. Disable maintenance mode
.\runme.ps1 -Action disable
```

### Development Workflow

```powershell
# 1. Edit app.py

# 2. Rebuild image and restart pods
.\runme.ps1 -Action setup

# 3. Test changes
.\test-endpoints.ps1

# 4. If issues, check logs
kubectl logs -n sample-app deployment/sample-app-user --tail=50
```

### Troubleshooting

```powershell
# Check overall status
.\runme.ps1 -Action status

# Run comprehensive tests
.\test-endpoints.ps1

# Check specific pod logs
kubectl logs -n sample-app deployment/sample-app-user
kubectl logs -n sample-app deployment/sample-app-admin
kubectl logs -n sample-app deployment/redis

# Restart everything
kubectl rollout restart deployment -n sample-app --all
```

---

## Script Design Principles

1. **Idempotent** - Safe to run multiple times
2. **Verbose** - Clear output showing what's happening
3. **Error handling** - Fails fast with clear error messages
4. **Color-coded** - Easy to see status at a glance
   - Cyan: Headers
   - Yellow: In progress
   - Green: Success
   - Red: Errors
5. **Documented** - Comments explain each step

---

## Cleanup

```powershell
# Basic cleanup (delete namespace, stop Minikube)
.\teardown.ps1

# Keep Minikube running
.\teardown.ps1 -KeepMinikube -Force

# Nuclear option (delete everything)
.\teardown.ps1 -DeepClean -Force
```

---

## Dependencies

All scripts require:

- PowerShell 7+ (included in Windows 10/11)
- Docker Desktop (running)
- Minikube
- kubectl

Install dependencies:

```powershell
winget install Docker.DockerDesktop
winget install Kubernetes.minikube
winget install Kubernetes.kubectl
```
