# Active User Tracking & Graceful Drain

## Overview

This document explains how the production-grade user session tracking and graceful drain system works.

## Problem: How do you shut down pods with active users?

In production systems, simply killing pods can:
- ❌ Lose unsaved user work
- ❌ Break WebSocket connections without warning
- ❌ Cause "connection refused" errors
- ❌ Result in poor user experience

## Solution: Graceful Drain with User Notification

### 1. Session Tracking

Every user session is tracked with:
- `session_id`: Unique identifier (UUID)
- `user`: Username (default: "anonymous")
- `login_time`: When user started session
- `last_activity`: Last request timestamp
- `pod`: Which pod is serving them

```python
ACTIVE_SESSIONS = {
    "session_123": {
        "user": "john",
        "login_time": datetime(2025, 11, 16, 10, 30, 0),
        "last_activity": datetime(2025, 11, 16, 10, 35, 0),
        "pod": "sample-app-user-abc123"
    }
}
```

### 2. Real-Time Notifications (SSE)

Server-Sent Events (SSE) allow server → client push notifications:

```javascript
// Client connects to /events endpoint
const eventSource = new EventSource('/events');

// Server sends drain notification
eventSource.addEventListener('drain', function(e) {
    const data = JSON.parse(e.data);
    // Show "Server shutting down in 60s" banner
    // Start countdown timer
    // Auto-redirect to /logout after timeout
});
```

**Why SSE instead of WebSockets?**
- ✅ Simpler (just HTTP, no binary protocol)
- ✅ Auto-reconnects built-in
- ✅ Works through proxies/firewalls
- ✅ Perfect for one-way notifications

### 3. Graceful Shutdown Flow

**Two Scenarios for User Notification:**

#### Scenario A: Maintenance Mode Activation (ConfigMap)

When admin enables maintenance mode via ConfigMap:

```
1. Admin patches ConfigMap
   └─> kubectl patch configmap app-config -p '{"data":{"MAINTENANCE_MODE":"true"}}'

2. Admin restarts user pods
   └─> kubectl delete pods -l tier=user

3. Monitor thread detects change (checks every 5s)
   └─> is_maintenance_mode() returns True

4. Send SSE drain notification to all connected users
   └─> "Maintenance mode activated. Please save your work and logout."

5. User browsers show countdown banner
   └─> Red banner: "⚠️ Maintenance mode activated"
   └─> 60-second countdown timer
   └─> Auto-logout after countdown

6. Readiness probe fails (/ready returns 503)
   └─> Pods removed from Service endpoints

7. New users get static 503 page
   └─> "We'll be back soon" maintenance page

8. Admin monitors /admin/users dashboard
   └─> Watches active session count → 0

9. Safe to perform upgrade!
```

#### Scenario B: Pod Deletion (SIGTERM)

When Kubernetes sends SIGTERM (pod deletion/scale-down):

```
1. Set SHUTTING_DOWN flag
   └─> Stop accepting new sessions

2. Count active users
   └─> Print to stderr: "10 active users detected"

3. Send SSE drain notification
   └─> Each client shows countdown banner
   └─> "Server shutting down in 60s. Please save your work and logout."

4. Wait 60 seconds for graceful logout
   └─> Print every 10s: "7 users remaining (50s left)..."

5. Force-close remaining sessions
   └─> Track forced_logouts_total metric
   └─> Clear Redis session keys

6. Wait 15s for endpoint propagation
   └─> Let kube-proxy/Ingress update routing

7. Exit cleanly
   └─> sys.exit(0)
```

**Timeline (Scenario B):**
```
T+0s:  SIGTERM received
       "⚠️ Server shutting down in 60s - please save and logout"
T+10s: 8 users remaining...
T+20s: 6 users remaining...
T+30s: 4 users remaining...
T+40s: 2 users remaining...
T+50s: 1 user remaining...
T+60s: Force-close 1 remaining session
T+75s: Exit (after endpoint propagation)
```

**Key Difference:**
- **Scenario A**: Persistent maintenance (until ConfigMap changed back)
- **Scenario B**: Temporary shutdown (single pod restart/scale-down)### 4. Admin Dashboard

View active sessions in real-time:

```
GET /admin/users
```

Shows:
- Total active sessions count
- User details (session ID, username)
- Which pod they're connected to
- Login time and last activity
- Session duration

**Auto-refreshes every 5 seconds** to show real-time drain progress.

### 5. Metrics (Prometheus)

```
GET /metrics
```

Exposes:
```prometheus
# Current active sessions
active_sessions_total 12

# Drain notifications sent (lifetime)
drain_notifications_sent 45

# Users who logged out after notification
graceful_logouts_total 38

# Sessions force-closed after timeout
forced_logouts_total 7

# Total logins since startup
total_logins 523
```

**Alerting Example:**
```yaml
- alert: HighForcedLogoutRate
  expr: rate(forced_logouts_total[5m]) > 0.1
  annotations:
    summary: "Users not logging out gracefully"
    description: "{{ $value }} forced logouts/sec - increase drain timeout?"
```

## Production Patterns

### Pattern 1: Redis for Cross-Pod Sessions

In production with multiple pods:
```python
import redis

redis_client = redis.Redis(host='redis', port=6379)

def track_session(session_id, user):
    redis_client.hset(f"session:{session_id}", mapping={
        "user": user,
        "login_time": datetime.now().isoformat(),
        "pod": os.getenv("HOSTNAME")
    })
    redis_client.expire(f"session:{session_id}", 3600)  # 1 hour TTL
```

**Benefits:**
- ✅ All pods see same session data
- ✅ Sessions survive pod restarts
- ✅ Automatic expiry (TTL)
- ✅ Admin dashboard shows ALL users across ALL pods

### Pattern 2: Sticky Sessions (Session Affinity)

Configure Ingress for session stickiness:
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  annotations:
    nginx.ingress.kubernetes.io/affinity: "cookie"
    nginx.ingress.kubernetes.io/session-cookie-name: "route"
    nginx.ingress.kubernetes.io/session-cookie-expires: "3600"
```

**Benefits:**
- User always routes to same pod
- Simplifies session management
- Better for WebSocket connections

### Pattern 3: Pod Disruption Budget

Prevent too many pods draining simultaneously:
```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: sample-app-user-pdb
  namespace: sample-app
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app: sample-app
      tier: user
```

**Effect:**
- Kubernetes drains pods one at a time
- Always keeps at least 1 pod serving traffic
- Prevents "all pods down" scenario during rolling update

## Scale-Down Coordination

When scaling down (e.g., night-time low traffic):

```bash
# Scale down from 5 → 2 replicas
kubectl scale deployment sample-app-user --replicas=2 -n sample-app

# What happens:
# 1. Kubernetes marks 3 pods for deletion
# 2. Each pod receives SIGTERM
# 3. Each pod notifies its users (SSE)
# 4. Users see "60s to save work" countdown
# 5. Monitor drain progress:
kubectl get pods -n sample-app -w

# 6. Check metrics:
curl http://localhost:9090/metrics | grep logout
```

**Monitoring During Scale-Down:**
1. Open admin dashboard: http://localhost:9092/admin/users
2. See active sessions per pod
3. Watch sessions decrease as users logout
4. Verify graceful_logouts_total increases
5. Minimal forced_logouts_total = good UX

## Testing Locally

### 1. Start the app
```bash
python app.py
```

### 2. Open multiple browser tabs
```
http://localhost:8080/
```
Each tab = new session

### 3. View active sessions
```
http://localhost:8080/admin/users
```
See all connected sessions

### 4. Trigger graceful shutdown
```bash
# Send SIGTERM (simulates Kubernetes pod deletion)
# Windows PowerShell:
Stop-Process -Name python -Signal SIGTERM

# Linux/Mac:
kill -TERM $(pgrep -f "python app.py")
```

### 5. Observe behavior
- All browser tabs show "Server shutting down" banner
- Countdown starts at 60 seconds
- Manual logout: click "Logout Now"
- Auto-logout: wait for countdown to reach 0
- Check terminal: see drain progress logs

## Deployment to Kubernetes

### 1. Build and deploy
```bash
# Build image
minikube docker-env | Invoke-Expression
docker build -t sample-app:latest .

# Deploy
kubectl apply -f kubernetes/

# Verify
kubectl get pods -n sample-app
```

### 2. Port forward to test
```bash
# User service
kubectl port-forward -n sample-app svc/sample-app-user-service 9090:80

# Admin service
kubectl port-forward -n sample-app svc/sample-app-admin-service 9092:80
```

### 3. Test drain in Kubernetes
```bash
# Delete a user pod to trigger drain
kubectl delete pod -n sample-app -l tier=user --wait=false

# Watch logs in real-time
kubectl logs -n sample-app -l tier=user -f

# Expected output:
# [GRACEFUL SHUTDOWN] Received SIGTERM signal
# [GRACEFUL SHUTDOWN] 3 active users detected
# [GRACEFUL SHUTDOWN] Sending drain notification to 3 users...
# [GRACEFUL SHUTDOWN] Waiting 60s for users to logout gracefully...
# [GRACEFUL SHUTDOWN] 2 users remaining (50s left)...
# [GRACEFUL SHUTDOWN] 1 user remaining (40s left)...
# [GRACEFUL SHUTDOWN] 0 users remaining (30s left)...
# [GRACEFUL SHUTDOWN] Waiting 15s for endpoint removal to propagate...
# [GRACEFUL SHUTDOWN] Shutting down cleanly...
```

## Configuration

### Adjust Drain Timeout

Increase user logout window from 60s → 120s:

```python
# In graceful_shutdown() function:
print(f"[GRACEFUL SHUTDOWN] Waiting 120s for users to logout gracefully...", file=sys.stderr)
for i in range(120, 0, -10):
    time.sleep(10)
    # ...
```

Update Kubernetes deployment:
```yaml
spec:
  terminationGracePeriodSeconds: 150  # 120s + 15s + 15s buffer
```

### Disable Auto-Logout

Remove auto-redirect in frontend:
```javascript
// Comment out this line:
// window.location.href = '/logout?reason=drain';
```

Users must manually click "Logout Now" button.

## Production Considerations

### 1. Long-Running Tasks
For users with:
- File uploads in progress
- Video rendering
- Data exports

**Solution:** Check task status before logout:
```python
@app.before_request
def check_active_tasks():
    session_id = session.get("session_id")
    if has_active_tasks(session_id):
        # Don't force-close this session
        # Wait for tasks to complete
        pass
```

### 2. WebSocket Connections

For real-time features (chat, live updates):
- Use **Rainbow Deployments** (see main docs)
- Don't kill old deployment until all WebSockets closed
- Monitor connection count:
  ```bash
  kubectl get pods -n sample-app -o wide
  # Keep old deployment at scale=1 until websocket_connections=0
  ```

### 3. Database Transactions

Ensure transactions complete before shutdown:
```python
def graceful_shutdown(signum, frame):
    # Wait for DB connections to close
    db_pool.wait_for_all_connections_closed(timeout=30)
    # Then proceed with drain...
```

## FAQ

**Q: Why 60 seconds? Isn't that too long?**  
A: 60s gives users time to:
- Finish typing a form
- Save a document
- Complete a file upload
- Read the warning message

**Q: What if users ignore the warning?**  
A: Sessions are force-closed after timeout. Data is auto-saved (if implemented). Forced logout is tracked in metrics for monitoring.

**Q: Does this work with autoscaling?**  
A: Yes! When HPA scales down, pods receive SIGTERM and drain gracefully. Just ensure `terminationGracePeriodSeconds` is set properly.

**Q: How do I see drain progress across all pods?**  
A: Query Prometheus metrics:
```promql
sum(active_sessions_total) by (pod)
```

Or use admin dashboard with Redis for cross-pod visibility.

## References

- [Kubernetes Pod Lifecycle](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/#pod-termination)
- [Graceful Shutdown Best Practices](https://learnkube.com/graceful-shutdown)
- [Pod Disruption Budgets](https://kubernetes.io/docs/concepts/workloads/pods/disruptions/)
- [Server-Sent Events (MDN)](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events)
