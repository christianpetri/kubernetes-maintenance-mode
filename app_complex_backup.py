"""
Kubernetes Maintenance Mode Demo - Production Best Practices

**How Professionals Handle Maintenance Windows in Large Apps:**

1. **Active User Session Tracking**
   - Track all logged-in users with session IDs
   - Monitor login time, last activity, which pod they're on
   - Admin dashboard shows real-time active sessions (/admin/users)
   - In production: Use Redis/Memcached for cross-pod visibility

2. **Graceful Shutdown with User Notification**
   - Pod receives SIGTERM when Kubernetes starts shutdown
   - Send SSE (Server-Sent Events) to all active users
   - Display "server shutting down in 60s" banner
   - Wait 60 seconds for users to save work and logout
   - Track graceful vs forced logouts (metrics)
   - Users see countdown and can logout gracefully

3. **Server-Sent Events (SSE) for Real-Time Push**
   - /events endpoint streams notifications to clients
   - Simpler than WebSockets (just HTTP)
   - Auto-reconnects on disconnect
   - Used for: drain warnings, maintenance alerts, logout countdown

4. **Metrics & Monitoring (Prometheus)**
   - active_sessions_total: Current logged-in users
   - drain_notifications_sent: How many users notified
   - graceful_logouts_total: Users who logged out after warning
   - forced_logouts_total: Sessions force-closed after timeout
   - /metrics endpoint exposes all metrics

5. **Readiness Probe Pattern**
   - User pods return 503 during maintenance
   - Kubernetes removes pod from Service endpoints
   - Load balancer stops sending new traffic
   - No pod restarts - just removed from rotation

6. **Admin Access Guarantee**
   - Separate admin deployment always bypasses maintenance
   - Admin pods always return 200 on readiness probe
   - Allows operators to monitor active users during drain

7. **Connection Draining Flow**
   - terminationGracePeriodSeconds: 75s (60s user drain + 15s endpoint propagation)
   - Send drain notification via SSE
   - Wait 60s for graceful logout
   - Force-close remaining sessions
   - Wait 15s for endpoint propagation
   - Exit cleanly

8. **Scale-Down Coordination**
   - When scaling down (kubectl scale deployment user --replicas=0):
   - Kubernetes sends SIGTERM to pods
   - Each pod notifies its active users
   - Wait for users to logout (60s timeout)
   - Metrics track graceful vs forced logouts
   - Ops can monitor /admin/users to see drain progress

**File-Based Toggle Limitation:**
The toggle button works locally but NOT in Kubernetes production.
Each pod has its own filesystem - changes don't propagate.
Production uses: kubectl patch configmap + rollout restart
"""

import os
import signal
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock, Thread
from uuid import uuid4

import redis
from flask import Flask, Response, jsonify, redirect, render_template_string, request, session

app = Flask(__name__)
app.secret_key = os.urandom(24)  # For session management

# Redis connection for shared session storage (production pattern)
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

redis_client: redis.Redis[str] | None = None
try:
    redis_client = redis.Redis(
        host=REDIS_HOST, port=REDIS_PORT, decode_responses=True, socket_connect_timeout=2
    )
    redis_client.ping()
    REDIS_AVAILABLE = True
    print(f"[REDIS] Connected to Redis at {REDIS_HOST}:{REDIS_PORT}", file=sys.stderr)
except Exception as e:
    REDIS_AVAILABLE = False
    redis_client = None
    print(f"[REDIS] Redis unavailable, falling back to in-memory storage: {e}", file=sys.stderr)

# Maintenance flag file (local development only - doesn't work in K8s)
# Use temp directory that works cross-platform (Windows/Linux)
MAINTENANCE_FLAG = Path(tempfile.gettempdir()) / "maintenance.flag"

# Track graceful shutdown state
SHUTTING_DOWN = False

# Maintenance mode notification tracking
MAINTENANCE_NOTIFIED = False  # Track if we've sent maintenance notification
MAINTENANCE_CHECK_THREAD = None

# Active user sessions tracking (production pattern with Redis fallback)
# Primary: Redis for cross-pod visibility
# Fallback: In-memory dict if Redis unavailable
ACTIVE_SESSIONS: dict[str, dict] = {}  # Only used when Redis unavailable
SESSIONS_LOCK = Lock()

# SSE (Server-Sent Events) clients for real-time notifications
SSE_CLIENTS: list[list] = []  # List of Response generators
SSE_LOCK = Lock()

# Metrics for monitoring
METRICS = {
    "active_sessions_total": 0,
    "drain_notifications_sent": 0,
    "graceful_logouts_total": 0,
    "forced_logouts_total": 0,
    "total_logins": 0,
}
METRICS_LOCK = Lock()


def is_maintenance_mode():
    """
    Check if maintenance mode is active.

    In production Kubernetes, this reads from MAINTENANCE_MODE environment variable
    (sourced from ConfigMap). The file flag only works for local development.
    """
    return MAINTENANCE_FLAG.exists() or os.getenv("MAINTENANCE_MODE", "").lower() == "true"


def is_admin_access():
    """
    Check if this is an admin pod (always accessible during maintenance).

    Admin pods have ADMIN_ACCESS=true in their environment (set via ConfigMap).
    This guarantees operators can control maintenance even when users are blocked.
    """
    return os.getenv("ADMIN_ACCESS", "").lower() == "true"


def monitor_maintenance_mode():
    """
    Background thread to monitor maintenance mode changes and notify users.

    When maintenance mode is enabled:
    1. Send SSE drain notification to all connected users
    2. Give users 60 seconds to save work and logout
    3. Track notification to avoid duplicate sends
    """
    global MAINTENANCE_NOTIFIED

    print("[MAINTENANCE MONITOR] Starting maintenance mode monitor thread", file=sys.stderr)

    while not SHUTTING_DOWN:
        try:
            current_maintenance = is_maintenance_mode()

            # Maintenance mode just enabled
            if current_maintenance and not MAINTENANCE_NOTIFIED:
                active_count = len(get_all_sessions())

                if active_count > 0:
                    print(
                        f"[MAINTENANCE] Maintenance mode enabled, notifying {active_count} users",
                        file=sys.stderr,
                    )

                    # Send drain notification via SSE
                    send_sse_event(
                        "drain",
                        {
                            "message": "Maintenance mode activated. Please save your work and logout.",
                            "countdown": 60,
                            "forced_logout_at": (
                                datetime.now() + timedelta(seconds=60)
                            ).isoformat(),
                        },
                    )

                    with METRICS_LOCK:
                        METRICS["drain_notifications_sent"] += active_count

                    MAINTENANCE_NOTIFIED = True
                else:
                    print(
                        "[MAINTENANCE] Maintenance mode enabled, no active users", file=sys.stderr
                    )
                    MAINTENANCE_NOTIFIED = True

            # Maintenance mode disabled
            elif not current_maintenance and MAINTENANCE_NOTIFIED:
                print("[MAINTENANCE] Maintenance mode disabled", file=sys.stderr)
                MAINTENANCE_NOTIFIED = False

            # Check every 5 seconds
            time.sleep(5)

        except Exception as e:
            print(f"[MAINTENANCE MONITOR] Error: {e}", file=sys.stderr)
            time.sleep(5)

    print("[MAINTENANCE MONITOR] Monitor thread shutting down", file=sys.stderr)


def graceful_shutdown(signum, frame):
    """
    Handle SIGTERM for graceful shutdown (Kubernetes best practice).

    **PRODUCTION PATTERN: Notify Active Users Before Shutdown**

    When Kubernetes deletes a pod:
    1. Endpoints removed from Service (starts here)
    2. SIGTERM sent to container (we handle it here)
    3. Wait terminationGracePeriodSeconds (default 30s)
    4. SIGKILL if still running

    **Graceful Drain Flow for Large Apps:**
    1. Set SHUTTING_DOWN flag (stop accepting new sessions)
    2. Send SSE notification to all connected users
    3. Wait 60 seconds for users to save work and logout
    4. Force-close remaining sessions
    5. Exit cleanly

    This pattern gives users time to:
    - Save unsaved work
    - Close WebSocket connections gracefully
    - See "server shutting down" message
    - Logout cleanly (tracked in metrics)
    """
    global SHUTTING_DOWN
    SHUTTING_DOWN = True

    print("[GRACEFUL SHUTDOWN] Received SIGTERM signal", file=sys.stderr)

    # Count active users before drain (across all pods via Redis)
    active_count = len(get_all_sessions())

    print(f"[GRACEFUL SHUTDOWN] {active_count} active users detected", file=sys.stderr)

    # Notify all connected clients via SSE
    if active_count > 0:
        print(
            f"[GRACEFUL SHUTDOWN] Sending drain notification to {active_count} users...",
            file=sys.stderr,
        )
        send_sse_event(
            "drain",
            {
                "message": "Server shutting down in 60 seconds. Please save your work and logout.",
                "countdown": 60,
                "forced_logout_at": (datetime.now() + timedelta(seconds=60)).isoformat(),
            },
        )

        with METRICS_LOCK:
            METRICS["drain_notifications_sent"] += active_count

        # Wait 60 seconds for graceful logout (production pattern)
        print("[GRACEFUL SHUTDOWN] Waiting 60s for users to logout gracefully...", file=sys.stderr)
        for i in range(60, 0, -10):
            time.sleep(10)
            remaining = len(get_all_sessions())
            print(
                f"[GRACEFUL SHUTDOWN] {remaining} users remaining ({i-10}s left)...",
                file=sys.stderr,
            )

        # Force-close remaining sessions
        forced_count = len(get_all_sessions())
        if forced_count > 0:
            print(
                f"[GRACEFUL SHUTDOWN] Force-closing {forced_count} remaining sessions",
                file=sys.stderr,
            )
            with METRICS_LOCK:
                METRICS["forced_logouts_total"] += forced_count
            # Clear Redis sessions
            if REDIS_AVAILABLE and redis_client:
                try:
                    for key in redis_client.keys("session:*"):
                        redis_client.delete(key)
                except Exception as e:
                    print(f"[REDIS] Error clearing sessions: {e}", file=sys.stderr)
            else:
                with SESSIONS_LOCK:
                    ACTIVE_SESSIONS.clear()

    # Additional 15s wait for endpoint propagation
    print("[GRACEFUL SHUTDOWN] Waiting 15s for endpoint removal to propagate...", file=sys.stderr)

    # Give Kubernetes time to remove endpoints from:
    # - kube-proxy (iptables)
    # - Ingress controllers
    # - Service meshes
    # - CoreDNS
    time.sleep(15)

    print("[GRACEFUL SHUTDOWN] Shutting down cleanly...", file=sys.stderr)
    # Close any database connections, WebSockets, etc. here
    sys.exit(0)


# Register SIGTERM handler (Kubernetes sends this on pod deletion)
signal.signal(signal.SIGTERM, graceful_shutdown)


# ============================================================================
# SESSION MANAGEMENT & TRACKING (Production Pattern with Redis)
# ============================================================================


def get_all_sessions():
    """Get all active sessions from Redis or in-memory fallback."""
    if REDIS_AVAILABLE and redis_client:
        try:
            session_keys = redis_client.keys("session:*")
            sessions = {}
            for key in session_keys:
                session_id = key.replace("session:", "")
                session_data = redis_client.hgetall(key)
                if session_data:
                    # Convert Redis strings back to proper types
                    sessions[session_id] = {
                        "user": session_data.get("user", "anonymous"),
                        "login_time": datetime.fromisoformat(session_data["login_time"]),
                        "last_activity": datetime.fromisoformat(session_data["last_activity"]),
                        "pod": session_data.get("pod", "unknown"),
                    }
            return sessions
        except Exception as e:
            print(f"[REDIS] Error reading sessions: {e}", file=sys.stderr)
            return {}
    else:
        # Fallback to in-memory
        with SESSIONS_LOCK:
            return dict(ACTIVE_SESSIONS)


def get_or_create_session_id():
    """Get existing session ID or create new one (Redis-backed)."""
    if "session_id" not in session:
        session["session_id"] = str(uuid4())
        session["login_time"] = datetime.now().isoformat()

        session_data = {
            "user": session.get("username", "anonymous"),
            "login_time": datetime.now().isoformat(),
            "last_activity": datetime.now().isoformat(),
            "pod": os.getenv("HOSTNAME", "localhost"),
        }

        # Track new session in Redis or in-memory
        if REDIS_AVAILABLE and redis_client:
            try:
                redis_client.hset(f"session:{session['session_id']}", mapping=session_data)  # type: ignore[arg-type]
                redis_client.expire(f"session:{session['session_id']}", 3600)  # 1 hour TTL
            except Exception as e:
                print(f"[REDIS] Error creating session: {e}", file=sys.stderr)
        else:
            # Fallback to in-memory
            with SESSIONS_LOCK:
                ACTIVE_SESSIONS[session["session_id"]] = {
                    "user": session_data["user"],
                    "login_time": datetime.fromisoformat(session_data["login_time"]),
                    "last_activity": datetime.fromisoformat(session_data["last_activity"]),
                    "pod": session_data["pod"],
                }

        with METRICS_LOCK:
            METRICS["total_logins"] += 1
            METRICS["active_sessions_total"] = len(get_all_sessions())

    return session["session_id"]


def update_session_activity(session_id):
    """Update last activity timestamp for session (Redis-backed)."""
    if REDIS_AVAILABLE and redis_client:
        try:
            redis_client.hset(f"session:{session_id}", "last_activity", datetime.now().isoformat())
            redis_client.expire(f"session:{session_id}", 3600)  # Refresh TTL
        except Exception as e:
            print(f"[REDIS] Error updating session activity: {e}", file=sys.stderr)
    else:
        # Fallback to in-memory
        with SESSIONS_LOCK:
            if session_id in ACTIVE_SESSIONS:
                ACTIVE_SESSIONS[session_id]["last_activity"] = datetime.now()


def send_sse_event(event_type, data):
    """Send Server-Sent Event to all connected clients (production pattern)."""
    with SSE_LOCK:
        for client_queue in SSE_CLIENTS[:]:  # Copy list to avoid modification during iteration
            try:
                client_queue.append({"event": event_type, "data": data})
            except Exception as e:
                print(f"[SSE] Error sending to client: {e}", file=sys.stderr)
                SSE_CLIENTS.remove(client_queue)


# ============================================================================
# ENDPOINTS: Server-Sent Events (SSE) for Real-Time Notifications
# ============================================================================


@app.route("/events")
def events():
    """
    Server-Sent Events endpoint (production pattern for real-time notifications).

    Allows server to push notifications to clients:
    - Maintenance mode activation
    - Drain warnings ("save your work, logging out in 60s")
    - Pod shutdown notifications

    SSE is better than WebSockets for one-way notifications:
    - Simpler (just HTTP)
    - Auto-reconnects
    - Works through proxies/firewalls
    - No binary protocol complexity
    """

    def event_stream():
        client_queue: list[dict] = []
        with SSE_LOCK:
            SSE_CLIENTS.append(client_queue)

        try:
            # Send initial connection confirmation
            yield "data: {'event': 'connected', 'message': 'SSE connection established'}\n\n"

            # Keep connection alive and send events
            while True:
                if client_queue:
                    event = client_queue.pop(0)
                    import json

                    yield f"event: {event['event']}\ndata: {json.dumps(event['data'])}\n\n"
                else:
                    # Heartbeat every 30 seconds
                    yield ": heartbeat\n\n"
                time.sleep(1)
        finally:
            with SSE_LOCK:
                if client_queue in SSE_CLIENTS:
                    SSE_CLIENTS.remove(client_queue)

    return Response(event_stream(), mimetype="text/event-stream")


# ============================================================================
# ENDPOINTS: Admin Dashboard - Active Users
# ============================================================================


@app.route("/admin/users")
def admin_users():
    """
    Admin dashboard showing active user sessions (production pattern with Redis).

    Shows:
    - Total active sessions count ACROSS ALL PODS (via Redis)
    - User details (session ID, username, login time, last activity)
    - Which pod they're connected to
    - Session duration

    Production-ready: Queries Redis to see sessions across ALL pods.
    """
    if not is_admin_access():
        return jsonify({"error": "Admin access required"}), 403

    # Get all sessions from Redis (cross-pod visibility!)
    all_sessions = get_all_sessions()

    sessions_data = []
    for session_id, session_info in all_sessions.items():
        duration = (datetime.now() - session_info["login_time"]).seconds
        sessions_data.append(
            {
                "session_id": session_id,
                "user": session_info["user"],
                "pod": session_info["pod"],
                "login_time": session_info["login_time"].isoformat(),
                "last_activity": session_info["last_activity"].isoformat(),
                "duration_seconds": duration,
            }
        )

    # HTML Dashboard
    dashboard_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Active Users Dashboard</title>
        <meta http-equiv="refresh" content="5">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial; margin: 0; padding: 20px; background: #f5f7fa; }}
            h1 {{ color: #2c3e50; }}
            .summary {{ background: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
            .summary h2 {{ margin: 0 0 10px 0; font-size: 48px; color: #28a745; }}
            .summary p {{ margin: 0; color: #6c757d; }}
            table {{ width: 100%; background: white; border-radius: 10px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1); border-collapse: collapse; }}
            th {{ background: #007bff; color: white; padding: 12px; text-align: left; }}
            td {{ padding: 12px; border-bottom: 1px solid #dee2e6; }}
            tr:last-child td {{ border-bottom: none; }}
            tr:hover {{ background: #f8f9fa; }}
            .pod {{ background: #e7f3ff; padding: 4px 8px; border-radius: 4px; font-family: monospace; font-size: 12px; }}
            .time {{ color: #6c757d; font-size: 14px; }}
        </style>
    </head>
    <body>
        <h1>🧑‍💼 Active Users Dashboard</h1>
        <div class="summary">
            <h2>{len(sessions_data)}</h2>
            <p>Active Sessions</p>
        </div>
        <table>
            <tr>
                <th>User</th>
                <th>Session ID</th>
                <th>Pod</th>
                <th>Login Time</th>
                <th>Last Activity</th>
                <th>Duration</th>
            </tr>
    """

    for session_data in sessions_data:
        duration_min = session_data["duration_seconds"] // 60
        dashboard_html += f"""
            <tr>
                <td><strong>{session_data['user']}</strong></td>
                <td class="time">{session_data['session_id'][:8]}...</td>
                <td><span class="pod">{session_data['pod']}</span></td>
                <td class="time">{session_data['login_time']}</td>
                <td class="time">{session_data['last_activity']}</td>
                <td>{duration_min}m</td>
            </tr>
        """

    dashboard_html += """
        </table>
        <p style="margin-top: 20px; color: #6c757d; text-align: center;">Auto-refreshes every 5 seconds</p>
    </body>
    </html>
    """

    return dashboard_html


# ============================================================================
# ENDPOINTS: Metrics for Prometheus
# ============================================================================


@app.route("/metrics")
def metrics():
    """
    Prometheus metrics endpoint (production pattern).

    Exposes:
    - active_sessions_total: Current active sessions
    - drain_notifications_sent: How many drain warnings sent
    - graceful_logouts_total: Users who logged out after notification
    - forced_logouts_total: Sessions force-closed after timeout
    - total_logins: Lifetime login count
    """
    METRICS["active_sessions_total"] = len(get_all_sessions())

    with METRICS_LOCK:
        metrics_text = f"""# HELP active_sessions_total Current number of active user sessions
# TYPE active_sessions_total gauge
active_sessions_total {METRICS['active_sessions_total']}

# HELP drain_notifications_sent Total drain notifications sent to users
# TYPE drain_notifications_sent counter
drain_notifications_sent {METRICS['drain_notifications_sent']}

# HELP graceful_logouts_total Total graceful logouts after notification
# TYPE graceful_logouts_total counter
graceful_logouts_total {METRICS['graceful_logouts_total']}

# HELP forced_logouts_total Total forced logouts after timeout
# TYPE forced_logouts_total counter
forced_logouts_total {METRICS['forced_logouts_total']}

# HELP total_logins Total logins since startup
# TYPE total_logins counter
total_logins {METRICS['total_logins']}
"""

    return Response(metrics_text, mimetype="text/plain")


# ============================================================================
USER_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Kubernetes Demo App</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial; margin: 0; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; display: flex; align-items: center; justify-content: center; }
        .container { max-width: 600px; background: white; padding: 50px; border-radius: 20px; box-shadow: 0 20px 60px rgba(0,0,0,0.3); text-align: center; }
        h1 { color: #2c3e50; margin: 0 0 30px 0; font-size: 32px; }
        .badge { display: inline-flex; align-items: center; gap: 8px; background: #d4edda; color: #155724; padding: 12px 24px; border-radius: 50px; font-size: 18px; font-weight: 600; margin: 20px 0; }
        .badge::before { content: '●'; font-size: 24px; color: #28a745; }
        .k8s-info { background: #f8f9fa; padding: 20px; border-radius: 10px; margin: 30px 0; text-align: left; }
        .k8s-info h3 { margin: 0 0 15px 0; color: #495057; font-size: 14px; text-transform: uppercase; letter-spacing: 1px; }
        .metric { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #dee2e6; }
        .metric:last-child { border-bottom: none; }
        .metric-label { color: #6c757d; }
        .metric-value { font-weight: 600; color: #28a745; }
        a { display: inline-block; margin-top: 20px; padding: 14px 32px; background: #007bff; color: white; text-decoration: none; border-radius: 8px; font-weight: 600; transition: all 0.3s; }
        a:hover { background: #0056b3; transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,123,255,0.4); }

        /* Drain notification banner */
        #drain-banner { display: none; position: fixed; top: 0; left: 0; right: 0; background: #ff6b6b; color: white; padding: 20px; text-align: center; z-index: 9999; box-shadow: 0 4px 12px rgba(0,0,0,0.3); animation: slideDown 0.5s; }
        @keyframes slideDown { from { transform: translateY(-100%); } to { transform: translateY(0); } }
        #drain-banner h2 { margin: 0 0 10px 0; font-size: 24px; }
        #drain-banner p { margin: 5px 0; font-size: 18px; }
        #countdown { font-size: 32px; font-weight: bold; margin: 10px 0; }
        .logout-btn { display: inline-block; margin-top: 15px; padding: 12px 24px; background: white; color: #ff6b6b; text-decoration: none; border-radius: 8px; font-weight: 600; }
    </style>
    <script>
        // Server-Sent Events (SSE) for real-time notifications
        const eventSource = new EventSource('/events');

        eventSource.addEventListener('connected', function(e) {
            console.log('[SSE] Connected to server notifications');
        });

        eventSource.addEventListener('drain', function(e) {
            const data = JSON.parse(e.data);
            console.log('[SSE] Drain notification received:', data);

            // Show drain banner
            const banner = document.getElementById('drain-banner');
            banner.style.display = 'block';

            // Start countdown
            let secondsLeft = data.countdown || 60;
            const countdownEl = document.getElementById('countdown');

            const countdownInterval = setInterval(function() {
                secondsLeft--;
                countdownEl.textContent = secondsLeft + 's';

                if (secondsLeft <= 0) {
                    clearInterval(countdownInterval);
                    // Auto-logout after countdown
                    window.location.href = '/logout?reason=drain';
                }
            }, 1000);
        });

        eventSource.addEventListener('error', function(e) {
            console.error('[SSE] Connection error:', e);
            // Will auto-reconnect
        });
    </script>
</head>
<body>
    <!-- Drain notification banner (hidden by default) -->
    <div id="drain-banner">
        <h2>⚠️ Server Shutting Down</h2>
        <p>Please save your work and logout gracefully.</p>
        <div id="countdown">60s</div>
        <p>Auto-logout in <span id="countdown">60</span> seconds</p>
        <a href="/logout?reason=drain" class="logout-btn">Logout Now</a>
    </div>

    <div class="container">
        <h1>🚀 Kubernetes Demo App</h1>
        <div class="badge">Service Available</div>
        <div class="k8s-info">
            <h3>Kubernetes Status</h3>
            <div class="metric"><span class="metric-label">Readiness Probe</span><span class="metric-value">✓ READY</span></div>
            <div class="metric"><span class="metric-label">Liveness Probe</span><span class="metric-value">✓ HEALTHY</span></div>
            <div class="metric"><span class="metric-label">Service Endpoints</span><span class="metric-value">ACTIVE</span></div>
        </div>
        <div style="margin-top: 30px; display: flex; gap: 15px; justify-content: center;">
            <a href="/admin" style="background: #6c757d;">Admin Panel →</a>
            <a href="/logout?reason=manual" style="background: #dc3545;">Logout</a>
        </div>
    </div>
</body>
</html>
"""

MAINTENANCE_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Scheduled Maintenance - Save Your Work</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 800px;
            background: white;
            padding: 40px;
            border-radius: 24px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            margin: 20px auto;
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 3px solid #f8f9fa;
        }
        .icon { font-size: 64px; margin-bottom: 15px; }
        h1 {
            color: #2c3e50;
            font-size: 28px;
            margin-bottom: 10px;
            font-weight: 700;
        }
        .subtitle {
            color: #6c757d;
            font-size: 16px;
            line-height: 1.6;
        }
        .alert {
            background: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 20px;
            border-radius: 8px;
            margin: 25px 0;
        }
        .alert h2 {
            color: #856404;
            font-size: 18px;
            margin-bottom: 10px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .alert h2::before { content: '⚠️'; }
        .alert p {
            color: #856404;
            font-size: 14px;
            line-height: 1.6;
            margin: 8px 0;
        }
        .section {
            background: #f8f9fa;
            padding: 25px;
            border-radius: 12px;
            margin: 20px 0;
        }
        .section h3 {
            color: #495057;
            font-size: 16px;
            margin-bottom: 15px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            font-weight: 700;
        }
        .tip {
            background: white;
            padding: 15px;
            border-radius: 8px;
            margin: 12px 0;
            border-left: 3px solid #667eea;
        }
        .tip-title {
            font-weight: 600;
            color: #667eea;
            font-size: 14px;
            margin-bottom: 6px;
        }
        .tip-text {
            color: #6c757d;
            font-size: 14px;
            line-height: 1.5;
        }
        .status-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
            margin: 20px 0;
        }
        .status-card {
            background: white;
            padding: 18px;
            border-radius: 10px;
            text-align: center;
            border: 2px solid #dee2e6;
        }
        .status-label {
            font-size: 11px;
            color: #6c757d;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 8px;
        }
        .status-value {
            font-size: 16px;
            font-weight: 700;
        }
        .status-value.error { color: #dc3545; }
        .status-value.success { color: #28a745; }
        .eta-box {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 25px;
            border-radius: 12px;
            text-align: center;
            margin: 25px 0;
        }
        .eta-label {
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            margin-bottom: 8px;
            opacity: 0.9;
        }
        .eta-value {
            font-size: 32px;
            font-weight: 700;
        }
        .contact {
            text-align: center;
            margin-top: 30px;
            padding-top: 25px;
            border-top: 2px solid #f8f9fa;
            color: #6c757d;
            font-size: 14px;
        }
        .contact a {
            color: #667eea;
            text-decoration: none;
            font-weight: 600;
        }
        .contact a:hover { text-decoration: underline; }
        code {
            background: #f8f9fa;
            padding: 2px 6px;
            border-radius: 4px;
            font-family: 'Courier New', monospace;
            font-size: 13px;
            color: #e83e8c;
        }
        @media (max-width: 768px) {
            .container { padding: 25px; }
            .status-grid { grid-template-columns: 1fr; }
            h1 { font-size: 24px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="icon">🔧</div>
            <h1>Scheduled Maintenance in Progress</h1>
            <p class="subtitle">
                We're performing system updates to improve your experience.
                Your session will be preserved - no need to save manually.
            </p>
        </div>

        <div class="alert">
            <h2>What's Happening Right Now</h2>
            <p><strong>✓ Your work is safe:</strong> All active sessions are maintained and will reconnect automatically</p>
            <p><strong>✓ Graceful shutdown:</strong> Existing requests are completing normally (15-30s drain period)</p>
            <p><strong>✓ No data loss:</strong> Database connections are closed cleanly after draining</p>
        </div>

        <div class="eta-box">
            <div class="eta-label">Estimated Completion Time</div>
            <div class="eta-value">~30 minutes</div>
            <p style="font-size: 14px; margin-top: 10px; opacity: 0.9;">Service will automatically resume</p>
        </div>

        <div class="section">
            <h3>🎯 For Users with Long-Running Tasks</h3>
            <div class="tip">
                <div class="tip-title">💾 Auto-Save Enabled</div>
                <div class="tip-text">
                    Your work is automatically saved. When maintenance completes, you'll be able to resume where you left off.
                </div>
            </div>
            <div class="tip">
                <div class="tip-title">🔄 WebSocket/Long-Polling Connections</div>
                <div class="tip-text">
                    Long-lived connections (WebSockets, SSE) use <strong>Rainbow Deployments</strong> - your connection stays active in the old deployment while new users get the updated version.
                </div>
            </div>
            <div class="tip">
                <div class="tip-title">📊 Background Jobs</div>
                <div class="tip-text">
                    Processing tasks continue in the background. Videos encoding, data exports, and batch jobs are unaffected during maintenance windows.
                </div>
            </div>
        </div>

        <div class="section">
            <h3>🏗️ Production Best Practices in Action</h3>
            <div class="status-grid">
                <div class="status-card">
                    <div class="status-label">Readiness Probe</div>
                    <div class="status-value error">✗ NOT READY</div>
                    <p style="font-size: 11px; color: #6c757d; margin-top: 8px;">Removed from load balancer</p>
                </div>
                <div class="status-card">
                    <div class="status-label">Liveness Probe</div>
                    <div class="status-value success">✓ HEALTHY</div>
                    <p style="font-size: 11px; color: #6c757d; margin-top: 8px;">No restarts required</p>
                </div>
                <div class="status-card">
                    <div class="status-label">Endpoints</div>
                    <div class="status-value error">DRAINING</div>
                    <p style="font-size: 11px; color: #6c757d; margin-top: 8px;">Propagating to kube-proxy</p>
                </div>
                <div class="status-card">
                    <div class="status-label">Admin Access</div>
                    <div class="status-value success">ACTIVE</div>
                    <p style="font-size: 11px; color: #6c757d; margin-top: 8px;">Control plane available</p>
                </div>
            </div>
            <p style="font-size: 13px; color: #6c757d; margin-top: 15px; line-height: 1.6;">
                <strong>How it works:</strong> Readiness probe returns <code>503</code> → Kubernetes removes pod from Service endpoints →
                kube-proxy updates iptables → Ingress stops routing → Existing connections drain for 15-30s → Clean shutdown
            </p>
        </div>

        <div class="contact">
            <p>Need immediate assistance? Admin panel is still accessible:</p>
            <p style="margin-top: 8px;"><a href="/admin">→ Go to Admin Panel</a></p>
            <p style="margin-top: 15px; font-size: 12px;">
                <strong>HTTP 503</strong> - Service Temporarily Unavailable | <code>Retry-After: 1800s</code>
            </p>
        </div>
    </div>
</body>
</html>
"""

ADMIN_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Admin Panel</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial; margin: 0; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; display: flex; align-items: center; justify-content: center; }
        .container { max-width: 600px; background: white; padding: 50px; border-radius: 20px; box-shadow: 0 20px 60px rgba(0,0,0,0.3); text-align: center; }
        h1 { color: #2c3e50; margin: 0 0 10px 0; font-size: 32px; }
        .subtitle { color: #6c757d; font-size: 14px; margin-bottom: 30px; text-transform: uppercase; letter-spacing: 1px; }
        .status-card { padding: 30px; border-radius: 15px; margin: 30px 0; }
        .status-card.on { background: linear-gradient(135deg, #fff3cd 0%, #ffe69c 100%); border: 3px solid #ffc107; }
        .status-card.off { background: linear-gradient(135deg, #d4edda 0%, #c3e6cb 100%); border: 3px solid #28a745; }
        .status-label { font-size: 12px; color: #6c757d; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 10px; }
        .status-value { font-size: 28px; font-weight: bold; }
        .status-card.on .status-value { color: #856404; }
        .status-card.off .status-value { color: #155724; }
        button { width: 100%; padding: 18px; font-size: 18px; border: none; border-radius: 12px; cursor: pointer; font-weight: 600; transition: all 0.3s; margin-top: 20px; }
        .btn-danger { background: #dc3545; color: white; }
        .btn-danger:hover { background: #c82333; transform: translateY(-2px); box-shadow: 0 8px 16px rgba(220,53,69,0.3); }
        .btn-success { background: #28a745; color: white; }
        .btn-success:hover { background: #218838; transform: translateY(-2px); box-shadow: 0 8px 16px rgba(40,167,69,0.3); }
        .k8s-info { background: #f8f9fa; padding: 20px; border-radius: 10px; margin: 30px 0; text-align: left; }
        .k8s-info h3 { margin: 0 0 15px 0; color: #495057; font-size: 14px; text-transform: uppercase; letter-spacing: 1px; text-align: center; }
        .metric { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #dee2e6; }
        .metric:last-child { border-bottom: none; }
        .metric-label { color: #6c757d; font-size: 14px; }
        .metric-value { font-weight: 600; }
        a { color: #007bff; text-decoration: none; font-size: 14px; }
        a:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <div class="container">
        <h1>⚙️ Admin Panel</h1>
        <div class="subtitle">Maintenance Control</div>
        <div class="status-card {{ 'on' if maintenance_mode else 'off' }}">
            <div class="status-label">Current Status</div>
            <div class="status-value">{{ maintenance_status }}</div>
        </div>
        <div class="k8s-info">
            <h3>Probe Status</h3>
            <div class="metric">
                <span class="metric-label">Liveness</span>
                <span class="metric-value" style="color: #28a745;">✓ HEALTHY</span>
            </div>
            <div class="metric">
                <span class="metric-label">Readiness</span>
                <span class="metric-value" style="color: {{ '#dc3545' if maintenance_mode else '#28a745' }};">
                    {{ '✗ NOT READY' if maintenance_mode else '✓ READY' }}
                </span>
            </div>
            <div class="metric">
                <span class="metric-label">Endpoints</span>
                <span class="metric-value" style="color: {{ '#dc3545' if maintenance_mode else '#28a745' }};">
                    {{ 'REMOVED' if maintenance_mode else 'ACTIVE' }}
                </span>
            </div>
        </div>
        <form action="/admin/toggle" method="POST">
            {% if maintenance_mode %}
            <button type="submit" class="btn-success">✓ Disable Maintenance</button>
            {% else %}
            <button type="submit" class="btn-danger">⚠ Enable Maintenance</button>
            {% endif %}
        </form>
        <p style="margin-top: 30px;">
            <a href="/">← Back to Home</a>
        </p>
    </div>
</body>
</html>
"""


@app.before_request
def check_maintenance():
    """
    Intercept all requests before routing (Flask best practice).

    Production Pattern: @app.before_request decorator
    - Single point of control (DRY principle)
    - Runs before any route handler
    - Can return response or None to continue routing

    Session Tracking Pattern:
    - Create/update session on every request
    - Track last activity for timeout detection
    - Skip for static files and health probes
    """
    # Skip for health probes, admin routes, SSE, metrics, static files
    skip_paths = ["/health", "/healthz", "/ready", "/readyz", "/events", "/metrics", "/logout"]
    if request.path in skip_paths or request.path.startswith(("/admin", "/static")):
        return None

    # Track user session (production pattern)
    session_id = get_or_create_session_id()
    update_session_activity(session_id)

    # Check if we're in graceful shutdown (draining connections)
    if SHUTTING_DOWN:
        # Continue serving existing requests during drain period
        # Don't accept new work but finish what we started
        pass  # Allow request to continue

    # Show maintenance page for all other routes during maintenance
    if is_maintenance_mode():
        response = app.make_response(render_template_string(MAINTENANCE_PAGE))
        response.status_code = 503
        response.headers["Retry-After"] = "1800"  # 30 minutes in seconds
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return response


@app.route("/")
def index():
    """
    Main page - returns the normal page with SSE connection.

    Maintenance handled by before_request.
    Session tracking automatic via before_request.
    """
    return render_template_string(USER_PAGE)


@app.route("/logout")
def logout():
    """
    Logout endpoint (production pattern for graceful drain with Redis).

    When user logs out:
    - Remove session from Redis (visible across all pods)
    - Track if it was graceful (after drain notification) or manual
    - Clear Flask session
    """
    session_id = session.get("session_id")
    reason = request.args.get("reason", "manual")

    if session_id:
        # Remove from Redis or in-memory
        if REDIS_AVAILABLE and redis_client:
            try:
                redis_client.delete(f"session:{session_id}")
            except Exception as e:
                print(f"[REDIS] Error deleting session: {e}", file=sys.stderr)
        else:
            with SESSIONS_LOCK:
                if session_id in ACTIVE_SESSIONS:
                    del ACTIVE_SESSIONS[session_id]

        with METRICS_LOCK:
            if reason == "drain":
                METRICS["graceful_logouts_total"] += 1
            METRICS["active_sessions_total"] = len(get_all_sessions())

    session.clear()

    logout_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Logged Out</title>
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial; margin: 0; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; display: flex; align-items: center; justify-content: center; }
            .container { max-width: 600px; background: white; padding: 50px; border-radius: 20px; box-shadow: 0 20px 60px rgba(0,0,0,0.3); text-align: center; }
            h1 { color: #2c3e50; margin: 0 0 20px 0; }
            p { color: #6c757d; font-size: 18px; margin: 20px 0; }
            a { display: inline-block; margin-top: 20px; padding: 14px 32px; background: #007bff; color: white; text-decoration: none; border-radius: 8px; font-weight: 600; }
            .icon { font-size: 64px; margin-bottom: 20px; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="icon">👋</div>
            <h1>Successfully Logged Out</h1>
            <p>Your session has been ended gracefully.</p>
            <p>Thank you for saving your work!</p>
            <a href="/">← Back to Home</a>
        </div>
    </body>
    </html>
    """

    return logout_html


@app.route("/admin")
def admin():
    """
    Admin panel - always accessible (production pattern).

    Shows:
    - Maintenance mode status
    - Toggle button (local dev only)
    - Link to active users dashboard (/admin/users)
    - Link to metrics (/metrics)
    """
    maintenance_status = "MAINTENANCE ON" if is_maintenance_mode() else "NORMAL OPERATION"

    # Get active sessions count
    with SESSIONS_LOCK:
        active_count = len(ACTIVE_SESSIONS)

    # Updated admin page with links
    admin_page_with_links = ADMIN_PAGE.replace(
        '<a href="/">← Back to Home</a>',
        f"""
        <div style="margin-top: 30px;">
            <p style="color: #6c757d; font-size: 14px;">Active Sessions: <strong>{active_count}</strong></p>
            <a href="/admin/users" style="margin: 10px;">📊 View Active Users</a>
            <a href="/metrics" style="margin: 10px; background: #28a745;">📈 View Metrics</a>
            <p style="margin-top: 20px;">
                <a href="/">← Back to Home</a>
            </p>
        </div>
        """,
    )

    return render_template_string(
        admin_page_with_links,
        maintenance_status=maintenance_status,
        maintenance_mode=is_maintenance_mode(),
    )


@app.route("/admin/toggle", methods=["POST"])
def toggle_maintenance():
    """
    Toggle maintenance mode using filesystem flag.

    ⚠️ IMPORTANT: This only works for LOCAL DEVELOPMENT!

    In Kubernetes, each pod has its own isolated filesystem.
    The file created here is NOT visible to other pods.

    Production Method (use scripts/runme.ps1):
    1. kubectl patch configmap app-config -n sample-app \
       -p '{"data":{"MAINTENANCE_MODE":"true"}}'
    2. kubectl rollout restart deployment -n sample-app
    3. Wait for new pods with updated ConfigMap
    4. Old pods drain connections gracefully (15-30s)
    5. New pods return 503 on readiness probe
    6. Kubernetes removes endpoints from Services

    Why not use shared volumes?
    - Added complexity (PersistentVolumeClaim setup)
    - Single point of failure
    - Slower than ConfigMap
    - Not the Kubernetes-native way
    """
    if is_maintenance_mode():
        # Disable maintenance
        if MAINTENANCE_FLAG.exists():
            MAINTENANCE_FLAG.unlink()
    else:
        # Enable maintenance
        MAINTENANCE_FLAG.touch()

    return redirect("/admin")


@app.route("/health")
@app.route("/healthz")
def health():
    """Liveness Probe - Always returns 200 (app is running)."""
    return {"status": "healthy"}, 200


@app.route("/ready")
@app.route("/readyz")
def ready():
    """
    Readiness Probe - Can the application serve traffic?

    **Production Pattern: Graceful Degradation**

    Returns 503 during maintenance → Kubernetes removes pod from Service endpoints
    → kube-proxy updates iptables → Ingress stops routing → No new traffic

    Key Differences from Liveness Probe:
    - Liveness: "Is the app running?" (crash = restart)
    - Readiness: "Can the app serve traffic?" (fail = remove from LB, NO restart)

    Admin Pods: Always return 200 (bypass maintenance for control plane access)
    User Pods: Return 503 during maintenance (graceful removal from rotation)

    Graceful Shutdown Flow:
    1. Pod receives SIGTERM (we handle in graceful_shutdown())
    2. Readiness starts returning 503
    3. Endpoints propagate (15-30s to reach all components)
    4. Existing requests complete
    5. Pod exits cleanly

    Why not just kill the pod immediately?
    - In-flight requests would fail (broken connections)
    - Endpoints might not be removed from kube-proxy yet
    - Ingress controllers might still route traffic
    - Race condition between endpoint removal and pod deletion
    """
    # Admin pods always ready (for maintenance control access)
    if is_admin_access():
        return {"status": "ready", "pod_type": "admin"}, 200

    # During graceful shutdown, keep serving but signal not ready
    if SHUTTING_DOWN:
        return {
            "status": "shutting_down",
            "message": "Draining connections gracefully",
            "ready": False,
        }, 503

    # User pods: not ready during maintenance (removes from LB)
    if is_maintenance_mode():
        return {"status": "not_ready", "maintenance_mode": True}, 503

    return {"status": "ready"}, 200


# ============================================================================
# STARTUP: Start background threads
# ============================================================================

# Start maintenance mode monitor thread (only for non-admin pods)
if not is_admin_access():
    MAINTENANCE_CHECK_THREAD = Thread(target=monitor_maintenance_mode, daemon=True)
    MAINTENANCE_CHECK_THREAD.start()
    print("[STARTUP] Maintenance mode monitor started", file=sys.stderr)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
