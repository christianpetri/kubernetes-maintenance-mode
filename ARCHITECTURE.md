# Architecture: Clean Separation of DEV and OPS

## Design Philosophy

**DEV Responsibility:** Build an app that returns 503 when told to  
**OPS Responsibility:** Use Kubernetes to control traffic routing based on health checks

---

## Action Map

```text
┌─────────────────────────────────────────────────────────────────┐
│                         DEV LAYER                                │
│                   (Application Logic)                            │
└─────────────────────────────────────────────────────────────────┘

    ┌─────────────────────┐
    │   Flask App         │
    │   (app.py)          │
    └──────────┬──────────┘
               │
               ├──> [1] Health Check (/health)
               │    └─> Always 200 OK
               │
               ├──> [2] Readiness Check (/ready)
               │    ├─> Read: /tmp/maintenance flag
               │    ├─> Admin pods: Always 200
               │    └─> User pods: 503 if maintenance=true
               │
               ├──> [3] Before Request Hook
               │    ├─> Check: maintenance flag?
               │    ├─> Exempt: /health, /ready, /admin/*
               │    └─> Return: 503 with Retry-After header
               │
               ├──> [4] User Routes (/)
               │    └─> Blocked by [3] if maintenance=true
               │
               └──> [5] Admin Routes (/admin/*)
                    └─> Always accessible (exempt from [3])

┌─────────────────────────────────────────────────────────────────┐
│                         OPS LAYER                                │
│                   (Kubernetes Control)                           │
└─────────────────────────────────────────────────────────────────┘

    ┌─────────────────────┐
    │   ConfigMap         │
    │   maintenance=false │
    └──────────┬──────────┘
               │ Mounted at: /config/maintenance
               │
    ┌──────────┴───────────┬────────────────────┐
    │                      │                    │
    ▼                      ▼                    ▼
┌─────────┐          ┌─────────┐          ┌─────────┐
│ User    │          │ User    │          │ Admin   │
│ Pod 1   │          │ Pod 2   │          │ Pod 1   │
└────┬────┘          └────┬────┘          └────┬────┘
     │                    │                    │
     │ Readiness Probe    │ Readiness Probe    │ Readiness Probe
     │ GET /ready         │ GET /ready         │ GET /ready
     │                    │                    │
     └────────────────────┴────────────────────┘
                          │
                          ▼
              ┌────────────────────┐
              │   Service          │
              │   (Load Balancer)  │
              └────────┬───────────┘
                       │
                       │ Routes traffic only to
                       │ pods returning 200
                       │
                       ▼
              ┌────────────────────┐
              │   Ingress          │
              │   (External)       │
              └────────────────────┘
```

---

## Flow: Enable Maintenance Mode

```text
OPS ACTION                          DEV RESPONSE                    K8S REACTION
─────────────────────────────────────────────────────────────────────────────

1. kubectl patch configmap
   maintenance=true
                                    ↓
2. File appears at                  App reads /config/maintenance
   /config/maintenance              └─> is_maintenance_mode() = True
                                    ↓
3. Readiness probe                  GET /ready
   hits user pods                   ├─> Admin pods: 200 (always)
                                    └─> User pods: 503
                                    ↓
4.                                                                  K8s sees 503
                                                                    └─> Removes user pods from Service
                                    ↓
5. New user requests                GET /
   arrive at Service                ├─> Routed ONLY to admin pods
                                    └─> (user pods no longer in endpoints)
                                    ↓
6. Existing user                    @app.before_request
   connections hit                  └─> Returns 503 Service Unavailable
   user pods                            with Retry-After: 300
```

---

## Clear Responsibilities

### DEV (Application Code)

**Job:** Respond correctly when asked about health  

✅ **Simple contract:**

1. `/health` → Always return 200 (app is running)
2. `/ready` → Return 200 or 503 based on config file
3. `@app.before_request` → Return 503 to users if maintenance flag exists
4. `/admin/*` → Always exempt from maintenance check

**That's it.** No complex orchestration, no distributed state management.

### OPS (Kubernetes)

**Job:** Control traffic routing based on health checks

✅ **Kubernetes does the heavy lifting:**

1. Watches readiness probe responses
2. Adds/removes pods from Service endpoints automatically
3. ConfigMap provides centralized config distribution
4. Ingress routes external traffic to healthy endpoints

---

## What Makes This Clean

### ❌ **NOT Doing (Complexity Removed)**

- ~~Session replication~~  
  *Demo doesn't track sessions. Focus is on maintenance mode pattern.*

- ~~SSE for maintenance alerts~~  
  *Removed. Just return 503, let client retry.*

### ✅ **Optional: Redis for Demo Mode**

- Used for button state sync across pods during live demos
- Shows instant cross-pod behavior (better presentation)
- Production still uses ConfigMap (proper Kubernetes pattern)

- ~~Graceful shutdown SSE~~  
  *Removed. SIGTERM already handled by K8s termination grace period.*

- ~~Monitoring thread~~  
  *Removed. Poll on each request is simpler.*

- ~~Active user tracking~~  
  *Optional feature, not core to maintenance demo.*

### ✅ **Clean Demo Focus**

```python
@app.before_request
def check_maintenance():
    """One decorator controls maintenance for entire app."""
    if request.path.startswith('/admin') or request.path in ['/health', '/ready']:
        return None  # Admin and health checks always pass
    
    if is_maintenance_mode():
        return render_template('503.html'), 503, {
            'Retry-After': '300',
            'Cache-Control': 'no-cache'
        }
```

**That's the entire maintenance logic.** Clean, simple, testable.

---

## File Structure Simplification

```text
demo/
├── app.py                  # 300 lines (was 1289!)
│   ├── Health checks
│   ├── Readiness logic
│   ├── Maintenance decorator
│   ├── User routes
│   └── Admin routes
│
├── kubernetes/
│   ├── configmap.yaml      # maintenance flag
│   ├── deployment.yaml     # user + admin pods
│   ├── service.yaml        # load balancer
│   └── ingress.yaml        # external access
│
├── templates/
│   ├── index.html          # User page
│   ├── admin.html          # Admin dashboard
│   └── 503.html            # Maintenance page
│
└── README.md               # Quick start guide
```

---

## Testing the Flow

### 1. Normal Operation

```bash
curl http://localhost:9090/        # → User page (200)
curl http://localhost:9092/admin   # → Admin page (200)
```

### 2. Enable Maintenance

```bash
kubectl patch configmap sample-app-config -n sample-app \
  -p '{"data":{"maintenance":"true"}}'
```

### 3. Verify Behavior

```bash
# Wait 10s for readiness probe cycle
sleep 10

# User endpoint returns 503
curl -i http://localhost:9090/
# → HTTP/1.1 503 Service Unavailable
# → Retry-After: 300

# Admin still works
curl http://localhost:9092/admin
# → Admin Dashboard (200)
```

### 4. Check Kubernetes

```bash
kubectl get endpoints -n sample-app sample-app-user
# → Shows 0 pods (removed from service)

kubectl get endpoints -n sample-app sample-app-admin
# → Shows 1 pod (still in service)
```

---

## The Magic: Two Deployments

```yaml
# User Deployment
readinessProbe:
  httpGet:
    path: /ready
  # Returns 503 during maintenance → removed from Service

# Admin Deployment  
env:
  - name: ADMIN_ACCESS
    value: "true"
readinessProbe:
  httpGet:
    path: /ready
  # Always returns 200 → stays in Service
```

**Result:** Admin can toggle maintenance mode ON/OFF because admin pods never lose Service membership.

---

## Summary

| Layer | Responsibility | Implementation |
|-------|---------------|----------------|
| **DEV** | Return 503 when told | `@app.before_request` + config file check |
| **OPS** | Control traffic routing | Readiness probes + Service endpoints |
| **Kubernetes** | Orchestration | ConfigMap + dual deployments |

**Clean separation = Simple to understand, test, and operate.**
