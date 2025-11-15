# Liveness vs Readiness Probe Comparison

## Quick Reference Table

| Aspect | Liveness Probe | Readiness Probe |
|--------|---------------|-----------------|
| **Question** | Is the container alive? | Can the container serve traffic? |
| **Common Names** | `/health`, `/healthz`, `/livez`, `/alive` | `/ready`, `/readyz`, `/healthz/ready` |
| **Success (200)** | Container is running normally | Ready to receive traffic |
| **Failure (5xx)** | Container is broken/deadlocked | Temporarily unable to serve requests |
| **Action on Failure** | 🔴 **RESTART** the container | 🟡 **REMOVE** from Service endpoints |
| **Restart Count** | Increments | No change |
| **Pod Status** | May enter CrashLoopBackOff | Pod continues running |
| **Traffic Impact** | All traffic stops during restart | Traffic redirected to other pods |

## Maintenance Mode Demonstration

### Normal Operation

```text
┌─────────────────────────┐
│    User Pod (Normal)    │
├─────────────────────────┤
│ GET /health → 200 ✅    │
│ GET /ready  → 200 ✅    │
│                         │
│ Status: In Service      │
│ Receives Traffic: YES   │
└─────────────────────────┘
```

### Maintenance Mode

```text
┌─────────────────────────┐
│  User Pod (Maintenance) │
├─────────────────────────┤
│ GET /health → 200 ✅    │  ← Still alive!
│ GET /ready  → 503 ❌    │  ← Not ready for traffic
│                         │
│ Status: Out of Service  │
│ Receives Traffic: NO    │
│ Container: RUNNING      │  ← NOT restarted
└─────────────────────────┘
```

## Real-World Testing

### Test Normal Mode

```bash
# Both probes should return 200
curl http://localhost:8888/health
curl http://localhost:8888/ready

# Response (both):
{
  "status": "healthy/ready",
  "probe_type": "liveness/readiness",
  "maintenance_mode": false,
  "message": "Application is running/ready"
}
```

### Test Maintenance Mode

```bash
# Liveness still returns 200 (app is alive)
curl http://localhost:8081/health

# Response:
{
  "status": "healthy",
  "probe_type": "liveness",
  "maintenance_mode": true,
  "message": "Application process is running"
}

# Readiness returns 503 (not ready for traffic)
curl http://localhost:8081/ready

# Response:
HTTP/1.1 503 Service Unavailable
{
  "status": "not_ready",
  "probe_type": "readiness",
  "maintenance_mode": true,
  "message": "Application is in maintenance mode - not accepting user traffic"
}
```

## When to Use Each Probe

### Use Liveness Probe When

- ✅ Detecting application deadlocks
- ✅ Identifying memory leaks causing crashes
- ✅ Finding thread pool exhaustion
- ✅ Catching unrecoverable error states
- ✅ Monitoring critical process health

### Use Readiness Probe When

- ✅ **Maintenance mode** (this demo!)
- ✅ Waiting for database connections
- ✅ Loading configuration from external sources
- ✅ Warming up caches
- ✅ Checking dependent service availability
- ✅ Rate limiting or throttling

## Kubernetes Behavior

### Liveness Probe Failure Sequence

```text
1. Probe fails (timeout or 5xx)
2. Failure threshold reached (e.g., 3 failures)
3. Container marked as unhealthy
4. Kubernetes terminates container
5. Restart counter increments
6. New container starts
7. InitialDelaySeconds wait period
8. Probes resume
```

### Readiness Probe Failure Sequence

```text
1. Probe fails (timeout or 5xx)
2. Failure threshold reached (e.g., 2 failures)
3. Pod marked as not ready
4. Pod removed from Service endpoints
5. Load balancer stops routing traffic
6. Container continues running
7. Probes continue checking
8. When probe succeeds, pod re-added to Service
```

## OpenShift/Kubernetes Configuration Examples

### Conservative Settings (Production)

```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8080
  initialDelaySeconds: 30    # Give app time to start
  periodSeconds: 10          # Check every 10 seconds
  timeoutSeconds: 5          # Wait 5 seconds for response
  failureThreshold: 3        # Restart after 3 failures
  successThreshold: 1        # 1 success = healthy

readinessProbe:
  httpGet:
    path: /ready
    port: 8080
  initialDelaySeconds: 5     # Check readiness quickly
  periodSeconds: 5           # Frequent checks
  timeoutSeconds: 3          # Shorter timeout OK
  failureThreshold: 2        # Remove from Service after 2 failures
  successThreshold: 1        # Back in Service after 1 success
```

### Aggressive Settings (Development)

```yaml
livenessProbe:
  httpGet:
    path: /healthz
    port: 8080
  initialDelaySeconds: 10
  periodSeconds: 5
  timeoutSeconds: 2
  failureThreshold: 2

readinessProbe:
  httpGet:
    path: /readyz
    port: 8080
  initialDelaySeconds: 3
  periodSeconds: 3
  timeoutSeconds: 2
  failureThreshold: 1
```

## Best Practices

### DO ✅

- Keep probe endpoints lightweight (< 100ms response time)
- Use different paths for liveness and readiness
- Return 200 for success, 5xx for failure
- Include diagnostic information in response body
- Test probe behavior in staging environment
- Monitor probe failure rates in production

### DON'T ❌

- Don't fail liveness for temporary issues (use readiness)
- Don't check external dependencies in liveness probe
- Don't restart containers for planned maintenance
- Don't set timeouts too low (causes false positives)
- Don't use the same endpoint for both probes (usually)
- Don't forget to adjust probes for slow-starting apps

## Monitoring and Debugging

### Check Probe Status

```bash
# OpenShift
oc describe pod <pod-name> -n demo-503

# Kubernetes
kubectl describe pod <pod-name> -n demo-503
```

### Watch for Events

```bash
# Look for "Unhealthy" or "Readiness probe failed"
oc get events -n demo-503 --watch
```

### View Pod Status

```bash
# READY column shows 0/1 when readiness fails
oc get pods -n demo-503 -o wide
```

## Common Gotchas

1. **InitialDelaySeconds too short**: Container not ready, liveness probe fails immediately
2. **Timeout too short**: Network latency causes false failures
3. **FailureThreshold too low**: Temporary issues cause unnecessary restarts
4. **Same endpoint for both**: Can't differentiate between alive and ready
5. **External dependencies in liveness**: Cascade failures across services

## Summary

**Liveness Probe**: "Is the app fundamentally broken?"

- Failure = restart container
- Use for detecting deadlocks, crashes, unrecoverable errors

**Readiness Probe**: "Can the app handle requests right now?"

- Failure = remove from load balancer
- Use for maintenance mode, dependency issues, warming up

**This Demo**: Shows how readiness probe enables graceful maintenance mode without restarting containers!
