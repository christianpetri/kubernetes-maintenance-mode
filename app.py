"""
OpenShift Maintenance Mode Demo

Demonstrates 503 error handling with graceful degradation:
- Liveness probe: Always healthy (app is running)
- Readiness probe: Returns 503 during maintenance (removes from load balancer)
- Filesystem flag: Shared state across all Gunicorn workers
"""

import os
from pathlib import Path

from flask import Flask, redirect, render_template_string

app = Flask(__name__)

# Maintenance flag file (shared across all workers)
MAINTENANCE_FLAG = Path("/tmp/maintenance.flag")


def is_maintenance_mode():
    """Check maintenance mode via filesystem flag or environment variable."""
    return MAINTENANCE_FLAG.exists() or os.getenv("MAINTENANCE_MODE", "").lower() == "true"


def is_admin_access():
    """Check if this is an admin pod (always accessible)."""
    return os.getenv("X-Admin-Access", "").lower() == "true"


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
<html>
<head>
    <title>Maintenance Mode</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial; margin: 0; background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); min-height: 100vh; display: flex; align-items: center; justify-content: center; }
        .container { max-width: 600px; background: white; padding: 50px; border-radius: 20px; box-shadow: 0 20px 60px rgba(0,0,0,0.3); text-align: center; }
        h1 { color: #721c24; margin: 0 0 30px 0; font-size: 32px; }
        .badge { display: inline-flex; align-items: center; gap: 8px; background: #fff3cd; color: #856404; padding: 12px 24px; border-radius: 50px; font-size: 18px; font-weight: 600; margin: 20px 0; border: 2px solid #ffc107; }
        .badge::before { content: '⚠'; font-size: 24px; }
        .k8s-info { background: #f8f9fa; padding: 20px; border-radius: 10px; margin: 30px 0; text-align: left; }
        .k8s-info h3 { margin: 0 0 15px 0; color: #495057; font-size: 14px; text-transform: uppercase; letter-spacing: 1px; }
        .metric { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #dee2e6; }
        .metric:last-child { border-bottom: none; }
        .metric-label { color: #6c757d; }
        .metric-value { font-weight: 600; color: #dc3545; }
        .metric-value.ok { color: #28a745; }
        a { display: inline-block; margin-top: 20px; padding: 14px 32px; background: #007bff; color: white; text-decoration: none; border-radius: 8px; font-weight: 600; transition: all 0.3s; }
        a:hover { background: #0056b3; transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,123,255,0.4); }
        .note { color: #6c757d; font-size: 14px; margin-top: 20px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔧 Maintenance Mode</h1>
        <div class="badge">Service Unavailable (503)</div>
        <div class="k8s-info">
            <h3>Kubernetes Status</h3>
            <div class="metric"><span class="metric-label">Readiness Probe</span><span class="metric-value">✗ NOT READY</span></div>
            <div class="metric"><span class="metric-label">Liveness Probe</span><span class="metric-value ok">✓ HEALTHY</span></div>
            <div class="metric"><span class="metric-label">Service Endpoints</span><span class="metric-value">REMOVED</span></div>
        </div>
        <p class="note">Pod removed from load balancer without restart</p>
        <a href="/admin">Admin Panel →</a>
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


@app.route("/")
def index():
    """Main page - shows maintenance message if mode is active."""
    if is_maintenance_mode():
        # Return 503 with Retry-After header (best practice)
        return render_template_string(MAINTENANCE_PAGE), 503, {"Retry-After": "120"}
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
    """Toggle maintenance mode using filesystem flag."""
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
    """
    Liveness Probe - Is the application alive?

    Returns 200 if process is running (even during maintenance).
    OpenShift restarts the container only if this fails.
    """
    return {
        "status": "healthy",
        "probe_type": "liveness",
        "maintenance_mode": is_maintenance_mode(),
    }, 200


@app.route("/ready")
@app.route("/readyz")
def ready():
    """
    Readiness Probe - Can the application serve traffic?

    CRITICAL BEHAVIOR:
    - Admin pods: ALWAYS return 200 (stay in Service for admin access)
    - User pods: Return 503 during maintenance (removed from Service)
    
    This allows admins to access the app and disable maintenance even when
    user pods are removed from the load balancer.
    """
    # Admin pods always ready (critical for maintenance control)
    if is_admin_access():
        return {
            "status": "ready",
            "probe_type": "readiness",
            "pod_type": "admin",
            "maintenance_mode": is_maintenance_mode(),
            "message": "Admin pod always ready for maintenance control",
        }, 200
    
    # User pods: not ready during maintenance
    if is_maintenance_mode():
        return {
            "status": "not_ready",
            "probe_type": "readiness",
            "pod_type": "user",
            "maintenance_mode": True,
            "message": "User pod not ready - maintenance mode active",
        }, 503

    return {
        "status": "ready",
        "probe_type": "readiness",
        "pod_type": "user",
        "maintenance_mode": False,
    }, 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
