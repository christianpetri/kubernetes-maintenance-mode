# Local Kubernetes/OpenShift Deployment Guide

This guide shows you how to deploy the OpenShift Maintenance Mode Demo on your local machine using industry-standard tools.

## Deployment Options

### Option 1: kind (Kubernetes in Docker) - **Recommended**

**What is kind?**

- Official Kubernetes tool for running local clusters using Docker
- Used by Kubernetes developers for testing
- Lightweight, fast, and follows Kubernetes standards
- Reference: <https://kind.sigs.k8s.io/>

**Why kind?**

- ✅ Multi-node cluster support
- ✅ Most similar to production Kubernetes/OpenShift
- ✅ Officially supported by Kubernetes project
- ✅ Fast cluster creation (<2 minutes)
- ✅ Works on Windows, macOS, and Linux

### Option 2: Docker Compose - **Simple Testing**

**What is Docker Compose?**

- Simple containerized testing environment
- No Kubernetes features (probes, HPA, services)
- Good for quick application testing
- Reference: <https://docs.docker.com/compose/>

**Why Docker Compose?**

- ✅ Fastest to set up
- ✅ No additional tools required
- ✅ Good for development
- ❌ No Kubernetes features
- ❌ Not representative of production

### Option 3: OpenShift Local (CRC) - **Official OpenShift**

**What is OpenShift Local?**

- Official Red Hat tool (formerly CodeReady Containers)
- Full OpenShift cluster on your laptop
- Requires significant resources (8GB RAM minimum)
- Reference: <https://developers.redhat.com/products/openshift-local>

**Why OpenShift Local?**

- ✅ True OpenShift experience
- ✅ Includes OpenShift-specific features
- ✅ Best for OpenShift-specific testing
- ❌ Resource intensive
- ❌ Slower to start

### Option 4: minikube - **Popular Alternative**

**What is minikube?**

- Established local Kubernetes tool
- Feature-rich with many addons
- Supports multiple drivers (Docker, VM, etc.)
- Reference: <https://minikube.sigs.k8s.io/>

**Why minikube?**

- ✅ Mature and stable
- ✅ Many built-in addons
- ✅ Excellent documentation
- ❌ Slightly slower than kind
- ❌ More complex configuration

## 📋 Prerequisites

### For kind (Recommended)

1. **Docker Desktop** or Docker Engine
   - Windows: <https://docs.docker.com/desktop/install/windows-install/>
   - macOS: <https://docs.docker.com/desktop/install/mac-install/>
   - Linux: <https://docs.docker.com/engine/install/>

2. **kubectl** (Kubernetes CLI)

   ```bash
   # macOS
   brew install kubectl

   # Windows (Chocolatey)
   choco install kubernetes-cli

   # Linux
   curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
   chmod +x kubectl
   sudo mv kubectl /usr/local/bin/
   ```

3. **kind** (Kubernetes in Docker)

   ```bash
   # macOS
   brew install kind

   # Windows (Chocolatey)
   choco install kind

   # Linux
   curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.30.0/kind-linux-amd64
   chmod +x ./kind
   sudo mv ./kind /usr/local/bin/kind

   # Or install with Go
   go install sigs.k8s.io/kind@v0.30.0
   ```

## Quick Start with kind

### 1. Deploy the Cluster

**Linux/macOS:**

```bash
chmod +x local-deploy.sh
./local-deploy.sh
```

**Windows (PowerShell):**

```powershell
.\local-deploy.ps1
```

### 2. Access the Application

The script will output URLs, but typically:

- **User App**: <http://localhost:8080>
- **Admin App**: <http://localhost:8080/admin>

Or use port-forwarding:

```bash
# Forward user service to port 8080
kubectl port-forward -n demo-503 svc/demo-app-user 8080:8080

# Forward admin service to port 8081 (in another terminal)
kubectl port-forward -n demo-503 svc/demo-app-admin 8081:8080
```

### 3. Test Liveness and Readiness Probes

```bash
# Get a user pod name
POD_NAME=$(kubectl get pod -n demo-503 -l tier=user -o jsonpath='{.items[0].metadata.name}')

# Test liveness probe (should return 200)
kubectl exec -n demo-503 -it $POD_NAME -- curl -s localhost:8080/healthz

# Test readiness probe (should return 200 normally, 503 during maintenance)
kubectl exec -n demo-503 -it $POD_NAME -- curl -s localhost:8080/readyz
```

### 4. Enable Maintenance Mode

```bash
# Patch ConfigMap to enable maintenance
kubectl patch configmap app-config -n demo-503 -p '{"data":{"MAINTENANCE_MODE":"true"}}'

# Restart user pods to pick up the change
kubectl rollout restart deployment/demo-app-user -n demo-503

# Watch rollout
kubectl rollout status deployment/demo-app-user -n demo-503
```

### 5. Test Maintenance Mode

```bash
# Readiness probe should now return 503
kubectl exec -n demo-503 -it $POD_NAME -- curl -s -w "\nHTTP Code: %{http_code}\n" localhost:8080/readyz

# Liveness probe should still return 200
kubectl exec -n demo-503 -it $POD_NAME -- curl -s -w "\nHTTP Code: %{http_code}\n" localhost:8080/healthz
```

### 6. Disable Maintenance Mode

```bash
# Patch ConfigMap to disable maintenance
kubectl patch configmap app-config -n demo-503 -p '{"data":{"MAINTENANCE_MODE":"false"}}'

# Restart user pods
kubectl rollout restart deployment/demo-app-user -n demo-503
```

## Monitoring and Debugging

### View Cluster Status

```bash
# Get nodes
kubectl get nodes

# Get all pods in demo-503 namespace
kubectl get pods -n demo-503 -o wide

# Get services
kubectl get svc -n demo-503

# Get HPA status
kubectl get hpa -n demo-503
```

### View Logs

```bash
# Follow logs from all user pods
kubectl logs -f -n demo-503 -l tier=user

# Follow logs from admin pods
kubectl logs -f -n demo-503 -l tier=admin

# View logs from specific pod
kubectl logs -n demo-503 <pod-name>
```

### Check Probe Status

```bash
# Describe pod to see probe status
kubectl describe pod -n demo-503 <pod-name>

# Watch events for probe failures
kubectl get events -n demo-503 --sort-by='.lastTimestamp' --watch
```

### Shell into Pod

```bash
# Get interactive shell
kubectl exec -it -n demo-503 <pod-name> -- /bin/bash

# Or use short syntax
POD=$(kubectl get pod -n demo-503 -l tier=user -o jsonpath='{.items[0].metadata.name}')
kubectl exec -it -n demo-503 $POD -- /bin/bash
```

## Advanced Configuration

### Cluster Configuration

The `kind-cluster.yaml` file defines:

- Multi-node cluster (1 control-plane + 2 workers)
- Port mappings for local access
- Node labels for pod placement
- Resource limits

You can customize:

```yaml
nodes:
- role: control-plane
  extraPortMappings:
  - containerPort: 80
    hostPort: 8080  # Change this to use different port
  - containerPort: 443
    hostPort: 8443
```

### Probe Endpoints

Following Kubernetes conventions (from Google/Kubernetes standards):

| Endpoint | Purpose | Standard Name |
|----------|---------|---------------|
| `/health` | Liveness probe | `/healthz` (with "z") |
| `/ready` | Readiness probe | `/readyz` (with "z") |
| `/startup` | Startup probe | `/startupz` (with "z") |

**Why the "z" suffix?**
The "z" suffix comes from Google's internal naming conventions and is widely adopted
in the Kubernetes ecosystem. Both versions are supported in this demo.

### Ingress Configuration

The `kubernetes/ingress.yaml` converts OpenShift Routes to standard Kubernetes Ingress:

- Uses nginx ingress controller
- Maps paths to services
- Supports host-based routing

## 🧹 Cleanup

### Delete the Cluster

```bash
# Delete kind cluster
kind delete cluster --name demo-503-cluster

# Verify deletion
kind get clusters
```

### Remove Docker Images

```bash
# Remove demo image
docker rmi demo-503:latest

# Clean up unused images
docker system prune -a
```

## 🐛 Troubleshooting

### Cluster Won't Create

**Problem**: kind create cluster fails

**Solutions**:

```bash
# Check Docker is running
docker info

# Check if cluster already exists
kind get clusters

# Delete existing cluster and retry
kind delete cluster --name demo-503-cluster
```

### Pods Not Ready

**Problem**: Pods stuck in "Pending" or "ImagePullBackOff"

**Solutions**:

```bash
# Check pod status
kubectl describe pod -n demo-503 <pod-name>

# Verify image was loaded
kind load docker-image demo-503:latest --name demo-503-cluster

# Check events
kubectl get events -n demo-503
```

### Can't Access Application

**Problem**: localhost:8080 not accessible

**Solutions**:

```bash
# Use port-forward instead
kubectl port-forward -n demo-503 svc/demo-app-user 8080:8080

# Check service exists
kubectl get svc -n demo-503

# Check ingress
kubectl get ingress -n demo-503
```

### Probes Failing

**Problem**: Liveness or readiness probes failing

**Solutions**:

```bash
# Check probe configuration
kubectl describe pod -n demo-503 <pod-name>

# Test probe manually
kubectl exec -n demo-503 -it <pod-name> -- curl -v localhost:8080/healthz

# Check pod logs
kubectl logs -n demo-503 <pod-name>
```

## Additional Resources

### Official Documentation

- **kind**: <https://kind.sigs.k8s.io/docs/>
- **kubectl**: <https://kubernetes.io/docs/reference/kubectl/>
- **Kubernetes Probes**: <https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/>
- **Ingress**: <https://kubernetes.io/docs/concepts/services-networking/ingress/>

### Probe Naming Conventions

- Kubernetes API Health: <https://kubernetes.io/docs/reference/using-api/health-checks/>
- `/healthz` - Standard liveness endpoint (Google convention)
- `/readyz` - Standard readiness endpoint (Google convention)
- `/livez` - Alternative liveness endpoint
- `/startupz` - Startup probe endpoint (K8s 1.16+)

### Alternative Tools

- **minikube**: <https://minikube.sigs.k8s.io/>
- **OpenShift Local (CRC)**: <https://developers.redhat.com/products/openshift-local>
- **k3s**: <https://k3s.io/> (lightweight Kubernetes)
- **MicroShift**: <https://microshift.io/> (Red Hat's lightweight OpenShift)

## 🎓 Learning Resources

### Kubernetes Basics

- Official Tutorial: <https://kubernetes.io/docs/tutorials/kubernetes-basics/>
- Interactive Learning: <https://www.katacoda.com/courses/kubernetes>

### OpenShift Basics

- OpenShift Learning Portal: <https://learn.openshift.com/>
- OpenShift Interactive Lab: <https://developers.redhat.com/developer-sandbox>

### Best Practices

- Health Checks: <https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/#container-probes>
- Resource Management: <https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/>
- 12-Factor Apps: <https://12factor.net/>

## 💡 Tips and Tricks

### Speed Up Development

```bash
# Auto-rebuild and reload on code changes
while inotifywait -e modify app.py; do
    docker build -t demo-503:latest .
    kind load docker-image demo-503:latest --name demo-503-cluster
    kubectl rollout restart deployment/demo-app-user -n demo-503
done
```

### Quick Testing

```bash
# Create alias for common commands
alias k='kubectl'
alias kd='kubectl -n demo-503'
alias kdp='kubectl -n demo-503 get pods'
alias kdl='kubectl -n demo-503 logs -f'

# Use in commands
kdp  # Get pods in demo-503 namespace
kdl <pod-name>  # Follow logs
```

### Port Forward Multiple Services

```bash
# Terminal 1: User service
kubectl port-forward -n demo-503 svc/demo-app-user 8080:8080

# Terminal 2: Admin service
kubectl port-forward -n demo-503 svc/demo-app-admin 8081:8080

# Terminal 3: Watch pods
watch kubectl get pods -n demo-503
```

---

**Ready to deploy?** Run `./local-deploy.sh` (Linux/macOS) or `.\local-deploy.ps1` (Windows)
and you'll have a local Kubernetes cluster with your maintenance mode demo running in minutes!
