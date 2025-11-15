# Full Demo (Copy-Paste Ready)

Two parts:

1) Tomcat + Java Filter (standalone, no K8s)
2) Kubernetes + OpenShift YAML (cluster version)

---

## 1. Standalone Tomcat Demo (localhost)

### `MaintenanceFilter.java`

```java
// src/main/java/com/example/filter/MaintenanceFilter.java
package com.example.filter;

import jakarta.servlet.*;
import jakarta.servlet.http.HttpServletResponse;
import java.io.File;
import java.io.IOException;

public class MaintenanceFilter implements Filter {
      private static final String MAINTENANCE_FLAG = "/tmp/maint.on";
      private static final String ADMIN_PATH = "/admin";

      @Override
      public void doFilter(ServletRequest req, ServletResponse res, FilterChain chain)
                  throws IOException, ServletException {
            HttpServletResponse response = (HttpServletResponse) res;
            String uri = ((jakarta.servlet.http.HttpServletRequest) req).getRequestURI();

            if (new File(MAINTENANCE_FLAG).exists() && !uri.startsWith(ADMIN_PATH)) {
                  response.setStatus(503);
                  response.getWriter().write("{\"error\": \"Service in maintenance mode\"}");
                  return;
            }
            chain.doFilter(req, res);
      }
}
```

### `web.xml` (add to `WEB-INF`)

```xml
<filter>
      <filter-name>MaintenanceFilter</filter-name>
      <filter-class>com.example.filter.MaintenanceFilter</filter-class>
      </filter>
<filter-mapping>
      <filter-name>MaintenanceFilter</filter-name>
      <url-pattern>/*</url-pattern>
</filter-mapping>
```

### `maintenance.html` (static fallback)

```html
<!-- src/main/webapp/maintenance.html -->
<!DOCTYPE html>
<html>
<head><title>Maintenance</title></head>
<body style="font-family: sans-serif; text-align: center; margin-top: 100px;">
   <h1>The application is in maintenance mode</h1>
   <p>Please come back later.</p>
</body>
</html>
```

### How to Run (Terminal)

```bash
# 1. Build WAR
mvn clean package

# 2. Start Tomcat
./startup.sh

# 3. Enable maintenance
touch /tmp/maint.on

# 4. Test
curl http://localhost:8080/api/status
# → 503 + JSON

curl http://localhost:8080/admin/status
# → 200 + normal response
```

---

## 2. Kubernetes / OpenShift YAML Demo

### `deployment.yaml`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
   name: sample-app
spec:
   replicas: 2
   selector:
      matchLabels:
         app: sample-app
   template:
      metadata:
         labels:
            app: sample-app
      spec:
         containers:
         - name: app
            image: your-registry/sample-app:latest
            ports:
            - containerPort: 8080
            readinessProbe:
               httpGet:
                  path: /system/status
                  port: 8080
               initialDelaySeconds: 30
               periodSeconds: 10
            livenessProbe:
               httpGet:
                  path: /ping
                  port: 8080
               initialDelaySeconds: 120
```

### `service.yaml`

```yaml
apiVersion: v1
kind: Service
metadata:
   name: sample-app-service
spec:
   selector:
      app: sample-app
   ports:
      - port: 80
         targetPort: 8080
```

### `route-normal.yaml` (OpenShift)

```yaml
apiVersion: route.openshift.io/v1
kind: Route
metadata:
   name: sample-app-normal
spec:
   host: example.com
   to:
      kind: Service
      name: sample-app-service
   port:
      targetPort: 8080
   # Honors readiness → 503 = drained
```

### `route-admin.yaml` (OpenShift – bypass readiness)

```yaml
apiVersion: route.openshift.io/v1
kind: Route
metadata:
   name: sample-app-admin
spec:
   host: admin.example.com
   to:
      kind: Service
      name: sample-app-service
   port:
      targetPort: 8080
   # Ignores readiness → always reachable
   tls:
      termination: edge
```

---

## Demo Script (Run in 60 seconds)

```bash
# 1. Deploy
oc apply -f deployment.yaml,service.yaml,route-normal.yaml,route-admin.yaml

# 2. Enter maintenance mode
oc exec deploy/sample-app -- touch /tmp/maint.on

# 3. Test
curl -H "Host: example.com" http://$(oc get route sample-app-normal -o jsonpath='{.spec.host}')
# → 503

curl -H "Host: admin.example.com" http://$(oc get route sample-app-admin -o jsonpath='{.spec.host}')/admin/status
# → 200 + full access
```

---

## Summary for Tech Lead

> You said: "503 kills admin access"

Reality:

- example.com → 503 → drained
- admin.example.com → 200 → full access
- Same app. Same code. Just routing rules.
- Works on Tomcat standalone and Kubernetes.
- 503 is a signal, not a shutdown.


## OpenShift Maintenance Mode Demo (503)

A demonstration of implementing maintenance mode in OpenShift with 503 Service Unavailable responses
for regular users while maintaining admin access during maintenance windows.

## Features

- **Dual-tier Architecture**: Separate user and admin pods running the same application
- **Maintenance Mode Toggle**: ConfigMap-based maintenance mode that affects only user traffic
- **503 Error Handling**: Proper HTTP 503 responses during maintenance
- **Admin Access Preservation**: Admin interface remains accessible during maintenance
- **Horizontal Pod Autoscaling**: Automatic scaling based on CPU and memory usage
- **Health Checks**: Kubernetes liveness and readiness probes
- **Docker Compose Support**: Local testing with Docker

## Prerequisites

- OpenShift CLI (`oc`) installed and configured
- Docker and Docker Compose (for local testing)
- Python 3.11+ (for local development)
- Access to an OpenShift cluster

## Architecture

```text
┌────────────────────────────────────────────────────┐
│                  OpenShift Cluster                 │
├────────────────────────────────────────────────────┤
│                                                    │
│  ┌───────────────────┐      ┌──────────────────┐   │
│  │   User Route      │      │   Admin Route    │   │
│  │  (Public Access)  │      │ (Admin Access)   │   │
│  └─────────┬─────────┘      └────────┬─────────┘   │
│            │                         │             │
│  ┌─────────▼─────────┐      ┌────────▼─────────┐   │
│  │   User Service    │      │  Admin Service   │   │
│  └─────────┬─────────┘      └────────┬─────────┘   │
│            │                         │             │
│  ┌─────────▼─────────┐      ┌────────▼─────────┐   │
│  │  User Deployment  │      │ Admin Deployment │   │
│  │  (2-10 replicas)  │      │   (1 replica)    │   │
│  │  + HPA enabled    │      │                  │   │
│  └─────────┬─────────┘      └────────┬─────────┘   │
│            │                         │             │
│            └──────────┬──────────────┘             │
│                       │                            │
│            ┌──────────▼──────────┐                 │
│            │   ConfigMap         │                 │
│            │   MAINTENANCE_MODE  │                 │
│            └─────────────────────┘                 │
└────────────────────────────────────────────────────┘
```

## Quick Start

### Local Deployment with kind (Recommended)

**Deploy to your local machine using kind (Kubernetes in Docker):**

See [LOCAL_DEPLOYMENT.md](docs/LOCAL_DEPLOYMENT.md) for complete guide.

**Quick start:**

```bash
# Linux/macOS
./deploy/local-deploy.sh

# Windows (PowerShell)
.\deploy\local-deploy.ps1
```

This creates a local Kubernetes cluster and deploys the full application with:

- Multi-node cluster (1 control-plane + 2 workers)
- Liveness and readiness probes
- Horizontal Pod Autoscaling
- ConfigMap-based maintenance mode

### Local Testing with Docker

1. **Build and run normally:**

   ```bash
   docker-compose up
   ```

   Access at <http://localhost:8888>

   Test probes:

   ```bash
   curl http://localhost:8888/health   # Liveness: 200 OK
   curl http://localhost:8888/ready    # Readiness: 200 OK
   ```

2. **Test maintenance mode:**

   ```bash
   docker-compose up web-maintenance
   ```

   Access at <http://localhost:8081> (will show 503)

   Test probes during maintenance:

   ```bash
   curl http://localhost:8081/health   # Liveness: 200 OK (still alive!)
   curl http://localhost:8081/ready    # Readiness: 503 (not ready for traffic)
   ```

### Understanding Liveness vs Readiness Probes

See [PROBES.md](docs/PROBES.md) for detailed explanation.

**Quick Summary:**

- **Liveness** (`/health`, `/healthz`): Is the container alive? (Restart if fails)
- **Readiness** (`/ready`, `/readyz`): Can it serve traffic? (Remove from Service if fails)

**During Maintenance:**

- ✅ Liveness returns 200 (app is healthy, don't restart)
- ❌ Readiness returns 503 (not ready for user traffic, remove from load balancer)

### Deploy to OpenShift

1. **Build and push the container image:**

   ```bash
   # Build the image
   docker build -t demo-503:latest .
   
   # Tag for your registry
   docker tag demo-503:latest <your-registry>/demo-503:latest
   
   # Push to registry
   docker push <your-registry>/demo-503:latest
   ```

2. **Update the image reference in `openshift/deployment.yaml`:**

   ```yaml
   image: <your-registry>/demo-503:latest
   ```

3. **Deploy to OpenShift:**

   **Linux/macOS:**

   ```bash
   chmod +x scripts/*.sh
   ./scripts/deploy.sh
   ```

   **Windows (PowerShell):**

   ```powershell
   .\scripts\deploy.ps1
   ```

4. **Get the route URLs:**

   ```bash
   oc get routes -n demo-503
   ```

## 🔧 Maintenance Mode Operations

### Enable Maintenance Mode

When you need to perform maintenance, enable maintenance mode to return 503 errors to regular users:

**Linux/macOS:**

```bash
./scripts/enable-maintenance.sh
```

**Windows (PowerShell):**

```powershell
.\scripts\enable-maintenance.ps1
```

**What happens:**

- User route returns HTTP 503 with maintenance page
- Admin route continues to work normally
- User pods are restarted to pick up the configuration change

### Disable Maintenance Mode

After maintenance is complete, restore normal operation:

**Linux/macOS:**

```bash
./scripts/disable-maintenance.sh
```

**Windows (PowerShell):**

```powershell
.\scripts\disable-maintenance.ps1
```

**What happens:**

- User route returns to normal operation
- All users can access the application again
- User pods are restarted to pick up the configuration change

### Manual Toggle

You can also manually update the ConfigMap:

```bash
# Enable maintenance mode
oc patch configmap app-config -n demo-503 -p '{"data":{"MAINTENANCE_MODE":"true"}}'

# Disable maintenance mode
oc patch configmap app-config -n demo-503 -p '{"data":{"MAINTENANCE_MODE":"false"}}'

# Restart user pods to apply changes
oc rollout restart deployment/demo-app-user -n demo-503
```

## Monitoring and Scaling

### Check Pod Status

```bash
oc get pods -n demo-503
```

### View HPA Status

```bash
oc get hpa -n demo-503
```

### Watch Pod Scaling

```bash
oc get hpa demo-app-user-hpa -n demo-503 --watch
```

### View Logs

```bash
# User pods
oc logs -f deployment/demo-app-user -n demo-503

# Admin pods
oc logs -f deployment/demo-app-admin -n demo-503
```

## Testing

### Test User Route (Normal)

```bash
curl -i https://demo-app-user-demo-503.apps.your-cluster.com
# Should return 200 OK
```

### Test User Route (Maintenance)

```bash
# After enabling maintenance mode
curl -i https://demo-app-user-demo-503.apps.your-cluster.com
# Should return 503 Service Unavailable
```

### Test Admin Route

```bash
curl -i https://admin-demo-503.apps.your-cluster.com/admin
# Should always return 200 OK
```

### Health Endpoints

```bash
# Health check
curl https://demo-app-user-demo-503.apps.your-cluster.com/health

# Readiness check
curl https://demo-app-user-demo-503.apps.your-cluster.com/ready
```

## Project Structure

```text
openshift-maintenance-demo/
├── app.py                          # Flask application
├── requirements.txt                # Python dependencies
├── pyproject.toml                  # Python project config + linting
├── Dockerfile                      # Container image
├── docker-compose.yml              # Local testing
├── .gitignore                      # Git ignore patterns
├── .markdownlint.json              # Markdown linting rules
├── .pre-commit-config.yaml         # Pre-commit hooks
├── README.md                       # Main documentation
├── CONTRIBUTING.md                 # Developer guidelines
├── docs/                           # Documentation
│   ├── PROBES.md                   # Probe explanation
│   ├── PROBE_COMPARISON.md         # Quick reference
│   ├── LOCAL_DEPLOYMENT.md         # Deployment guide
│   └── QUICKSTART.md               # Quick start guide
├── deploy/                         # Deployment scripts
│   ├── kind-cluster.yaml           # Kind cluster config
│   ├── local-deploy.sh             # Linux/macOS deploy
│   └── local-deploy.ps1            # Windows deploy
├── openshift/                      # OpenShift manifests
│   ├── namespace.yaml
│   ├── configmap.yaml
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── route.yaml
│   └── hpa.yaml
├── kubernetes/                     # Kubernetes manifests
│   └── ingress.yaml
├── scripts/                        # Maintenance scripts
│   ├── deploy.sh / deploy.ps1
│   ├── enable-maintenance.sh / .ps1
│   └── disable-maintenance.sh / .ps1
└── .github/
    ├── workflows/
    │   └── lint.yml                # CI/CD linting
    └── copilot-instructions.md
```

## Key Concepts

### ConfigMap-Based Configuration

The maintenance mode is controlled by a ConfigMap (`app-config`) that stores the
`MAINTENANCE_MODE` environment variable. This allows dynamic configuration changes
without rebuilding container images.

### Separate Deployments

Two separate deployments run the same container image:

- **User Deployment**: Reads `MAINTENANCE_MODE` from ConfigMap, scales 2-10 pods
- **Admin Deployment**: Always has `MAINTENANCE_MODE=false`, runs 1 pod

### 503 Response

When maintenance mode is enabled, the user deployment returns HTTP 503 (Service Unavailable)
with a maintenance page. This is the correct HTTP status code for temporary service interruptions.

### Horizontal Pod Autoscaling

The user deployment uses HPA to automatically scale between 2-10 pods based on:

- CPU utilization (target: 70%)
- Memory utilization (target: 80%)

## Development

### Code Quality Tools

This project uses modern Python and Markdown linting tools:

**Python:**

- **Ruff** - Fast all-in-one linter and formatter (replaces flake8, black, isort, etc.)
- **mypy** - Static type checking

**Markdown:**

- **markdownlint** - Markdown style and syntax checking

**Setup:**

```bash
# Install development tools
pip install ruff mypy pre-commit

# Install pre-commit hooks (runs automatically on git commit)
pre-commit install

# Run linting manually
ruff check .          # Check Python code
ruff format .         # Format Python code
mypy app.py           # Type check Python
markdownlint '**/*.md' --fix  # Fix Markdown
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed development guidelines.

## Customization

### Change Maintenance Page

Edit the `MAINTENANCE_PAGE` template in `app.py` to customize the maintenance message.

### Adjust Scaling Parameters

Modify `openshift/hpa.yaml` to change:

- Min/max replicas
- CPU/memory thresholds
- Scale up/down behavior

### Add Authentication

Enhance the admin route with proper authentication by modifying `app.py`
to check headers, tokens, or integrate with OpenShift OAuth.

## Notes

- The admin deployment intentionally ignores the maintenance mode ConfigMap to ensure administrative access is always available
- Pod restarts are required after ConfigMap changes because environment variables are set at pod creation time
- The HPA requires the Metrics Server to be installed in your OpenShift cluster
- Update the route hostnames in `openshift/route.yaml` to match your cluster domain

## Contributing

Feel free to submit issues and enhancement requests!

## License

This is a demonstration project for educational purposes.
