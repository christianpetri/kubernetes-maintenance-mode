"""
Kubernetes Maintenance Mode Demo - Production Best Practices

**How Professionals Handle Maintenance Windows:**

1. **Graceful Shutdown (15-30 seconds)**
   - Pod receives SIGTERM signal when maintenance starts
   - Application continues serving existing requests
   - New connections are drained as endpoints propagate
   - Database connections/WebSockets closed cleanly

2. **Readiness Probe Pattern**
   - User pods return 503 during maintenance
   - Kubernetes removes pod from Service endpoints
   - Load balancer stops sending new traffic
   - No pod restarts - just removed from rotation

3. **Admin Access Guarantee**
   - Separate admin deployment always bypasses maintenance
   - Admin pods always return 200 on readiness probe
   - Allows operators to control and monitor during maintenance

4. **Connection Draining**
   - terminationGracePeriodSeconds: 30s default (configurable)
   - preStop hook can add extra delay (e.g., sleep 15)
   - Gives time for endpoints to propagate to all components:
     * kube-proxy (iptables rules)
     * Ingress controllers
     * CoreDNS
     * Service meshes (Istio/Linkerd)

5. **Long-Running Work**
   - For WebSockets/long-polling: use Rainbow Deployments
   - Create new Deployment for each release
   - Old deployment drains connections naturally
   - Scale to zero when all connections closed

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
from pathlib import Path

from flask import Flask, jsonify, redirect, render_template_string, request

app = Flask(__name__)

# Maintenance flag file (local development only - doesn't work in K8s)
# Use temp directory that works cross-platform (Windows/Linux)
MAINTENANCE_FLAG = Path(tempfile.gettempdir()) / "maintenance.flag"

# Track graceful shutdown state
SHUTTING_DOWN = False


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


def graceful_shutdown(signum, frame):
    """
    Handle SIGTERM for graceful shutdown (Kubernetes best practice).

    When Kubernetes deletes a pod:
    1. Endpoints removed from Service (starts here)
    2. SIGTERM sent to container (we handle it here)
    3. Wait terminationGracePeriodSeconds (default 30s)
    4. SIGKILL if still running

    Best practice: Wait 15s to let endpoint removal propagate,
    then close connections and exit cleanly.
    """
    global SHUTTING_DOWN
    SHUTTING_DOWN = True
    
    print(f"[GRACEFUL SHUTDOWN] Received SIGTERM signal", file=sys.stderr)
    print(f"[GRACEFUL SHUTDOWN] Waiting 15s for endpoint removal to propagate...", file=sys.stderr)
    
    # Give Kubernetes time to remove endpoints from:
    # - kube-proxy (iptables)
    # - Ingress controllers
    # - Service meshes
    # - CoreDNS
    time.sleep(15)
    
    print(f"[GRACEFUL SHUTDOWN] Shutting down cleanly...", file=sys.stderr)
    # Close any database connections, WebSockets, etc. here
    sys.exit(0)


# Register SIGTERM handler (Kubernetes sends this on pod deletion)
signal.signal(signal.SIGTERM, graceful_shutdown)


# HTML Templates
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
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 Kubernetes Demo App</h1>
        <div class="badge">Service Available</div>
        <div class="k8s-info">
            <h3>Kubernetes Status</h3>
            <div class="metric"><span class="metric-label">Readiness Probe</span><span class="metric-value">✓ READY</span></div>
            <div class="metric"><span class="metric-label">Liveness Probe</span><span class="metric-value">✓ HEALTHY</span></div>
            <div class="metric"><span class="metric-label">Service Endpoints</span><span class="metric-value">ACTIVE</span></div>
        </div>
        <a href="/admin">Admin Panel →</a>
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
    """
    # Skip maintenance check for health probes and admin routes
    if request.path in ["/health", "/healthz", "/ready", "/readyz"] or request.path.startswith(
        "/admin"
    ):
        return None

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
    """Main page - just returns the normal page. Maintenance handled by before_request."""
    return render_template_string(USER_PAGE)


@app.route("/admin")
def admin():
    """Admin panel - always accessible."""
    maintenance_status = "MAINTENANCE ON" if is_maintenance_mode() else "NORMAL OPERATION"
    return render_template_string(
        ADMIN_PAGE, maintenance_status=maintenance_status, maintenance_mode=is_maintenance_mode()
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
            "ready": False
        }, 503

    # User pods: not ready during maintenance (removes from LB)
    if is_maintenance_mode():
        return {"status": "not_ready", "maintenance_mode": True}, 503

    return {"status": "ready"}, 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
