# Kubernetes/OpenShift Probes: Liveness vs Readiness

## Overview

This demo shows the critical difference between **liveness probes** and **readiness probes** in Kubernetes/OpenShift.

## Probe Types

### 🔴 Liveness Probe - "Is the container alive?"

**Purpose**: Detect when an application is in an unrecoverable state

**Common API Names**:

- `/health`
- `/healthz` (Kubernetes convention)
- `/livez`
- `/alive`

**What happens if it fails?**

- ⚠️ **Container is RESTARTED** by Kubernetes/OpenShift
- Restart counter increments
- Pod may enter CrashLoopBackOff if it fails repeatedly

**When should it fail?**

- Application deadlock
- Process crash
- Memory leak causing OOM
- Unrecoverable error state
- Thread pool exhaustion

**When should it NOT fail?**

- ❌ Temporary unavailability (use readiness instead)
- ❌ Maintenance mode (use readiness instead)
- ❌ Dependencies temporarily down (use readiness instead)
- ❌ Application warming up (use readiness instead)

### 🟢 Readiness Probe - "Can the container serve traffic?"

**Purpose**: Determine if the application is ready to accept requests

**Common API Names**:

- `/ready`
- `/readyz` (Kubernetes convention)
- `/healthz/ready`
- `/status`

**What happens if it fails?**

- ✅ **Pod is REMOVED from Service endpoints** (load balancer)
- No traffic is routed to this pod
- Container keeps running (NO restart)
- Can become ready again when condition resolves

**When should it fail?**

- ✅ Maintenance mode (this demo!)
- ✅ Database connection lost
- ✅ Required dependencies unavailable
- ✅ Application still warming up/initializing
- ✅ Rate limit exceeded
- ✅ Disk full

**When should it NOT fail?**

- Container is genuinely broken (use liveness instead)

## Demo Implementation

### Maintenance Mode Behavior

#### User Pods (during maintenance)

```bash
GET /health  → 200 OK (still alive, don't restart!)
GET /ready   → 503 Service Unavailable (not ready for traffic)
```

**Result**: Pods removed from Service, users get 503, but pods keep running

#### Admin Pods (during maintenance)

```bash
GET /health  → 200 OK (alive)
GET /ready   → 200 OK (ready - admin always has access)
```

**Result**: Admin pods remain in Service and serve traffic

## Testing Locally

```bash
# Test liveness probe (should always be healthy)
curl http://localhost:8888/health
curl http://localhost:8888/healthz

# Test readiness probe (depends on maintenance mode)
curl http://localhost:8888/ready
curl http://localhost:8888/readyz

# Enable maintenance mode
curl -X POST http://localhost:8888/admin/toggle-maintenance

# Test readiness again - should now return 503
curl http://localhost:8888/ready
```

## OpenShift Configuration

```yaml
livenessProbe:
  httpGet:
    path: /health        # or /healthz
    port: 8080
  initialDelaySeconds: 10
  periodSeconds: 10
  timeoutSeconds: 3
  failureThreshold: 3    # Restart after 3 consecutive failures

readinessProbe:
  httpGet:
    path: /ready         # or /readyz
    port: 8080
  initialDelaySeconds: 5
  periodSeconds: 5
  timeoutSeconds: 3
  failureThreshold: 2    # Remove from Service after 2 failures
```

## Probe Parameters Explained

| Parameter | Description | Typical Values |
|-----------|-------------|----------------|
| `initialDelaySeconds` | Wait before first probe | 5-30s |
| `periodSeconds` | How often to probe | 5-10s |
| `timeoutSeconds` | Probe timeout | 1-5s |
| `failureThreshold` | Failures before action | 2-3 |
| `successThreshold` | Successes to recover | 1 (readiness can be >1) |

## Best Practices

### ✅ Do

- Keep liveness checks simple and fast
- Use readiness for dependency checks
- Return 200 for healthy, 5xx for unhealthy
- Include diagnostic info in response body
- Use standard endpoint names (`/healthz`, `/readyz`)

### ❌ Don't

- Don't fail liveness for temporary issues
- Don't make probes depend on external services (liveness)
- Don't use the same endpoint for both probes (usually)
- Don't set timeouts too low
- Don't restart containers for maintenance (use readiness)

## Real-World Scenarios

### Scenario 1: Database Connection Lost

```text
Liveness: ✅ 200 (app process is alive)
Readiness: ❌ 503 (can't serve requests without DB)
Result: Pod removed from load balancer, waits for DB recovery
```

### Scenario 2: Application Deadlock

```text
Liveness: ❌ timeout (app not responding)
Readiness: ❌ timeout (app not responding)
Result: Container restarted by Kubernetes
```

### Scenario 3: Planned Maintenance (This Demo!)

```text
Liveness: ✅ 200 (app is healthy)
Readiness: ❌ 503 (deliberately not accepting user traffic)
Result: User pods removed from Service, show 503 to users
```

## Monitoring in OpenShift

```bash
# Check probe status
oc describe pod <pod-name> -n demo-503

# Watch for probe failures
oc get events -n demo-503 --watch

# Check readiness status
oc get pods -n demo-503 -o wide
# Look for READY column: 0/1 means readiness probe failing
```

## Common Kubernetes Probe Names

According to Kubernetes community conventions:

| Probe Type | Common Paths | Notes |
|------------|--------------|-------|
| Liveness | `/healthz`, `/health`, `/livez` | Check process health |
| Readiness | `/readyz`, `/ready`, `/healthz/ready` | Check traffic readiness |
| Startup | `/startupz`, `/startup` | Check initial startup (k8s 1.16+) |

**Note**: The `z` suffix (e.g., `/healthz`) comes from Google's internal conventions
and is widely adopted in the Kubernetes ecosystem.
