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


# HTML Templates
USER_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Demo App</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial; margin: 0; background: #f5f5f5; }
        .container { max-width: 800px; margin: 50px auto; background: white; padding: 40px; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
        h1 { color: #2c3e50; margin: 0 0 20px 0; }
        .status { background: #d4edda; color: #155724; padding: 15px; border-radius: 6px; border-left: 4px solid #28a745; }
        .info { color: #666; margin-top: 20px; line-height: 1.6; }
        a { display: inline-block; margin-top: 20px; padding: 10px 20px; background: #007bff; color: white; text-decoration: none; border-radius: 6px; }
        a:hover { background: #0056b3; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Demo Application</h1>
        <div class="status">
            <strong>✓ Status:</strong> Application running normally
        </div>
        <div class="info">
            <p><strong>Demo entry point:</strong> During maintenance, end‑user requests return <span class="code">503</span>,
            but the <span class="code">readiness probe remains 200</span> so administrators can still access the app to end maintenance.</p>
            <p><strong>Current behavior:</strong> All traffic is being served normally.</p>
        </div>
        <a href="/admin">Admin Panel</a>
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
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial; margin: 0; background: #fff3cd; }
        .container { max-width: 800px; margin: 50px auto; background: white; padding: 40px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); }
        h1 { color: #856404; margin: 0 0 20px 0; }
        .warning { background: #fff3cd; color: #856404; padding: 15px; border-radius: 6px; border-left: 4px solid #ffc107; margin: 20px 0; }
        .info { background: #d1ecf1; color: #0c5460; padding: 15px; border-radius: 6px; margin: 20px 0; }
        /* Improve readability of inline badges and prevent awkward wrapping */
        .code {
            background: #f8f9fa;
            color: #e83e8c;
            font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace;
            font-size: 0.95em;
            padding: 2px 8px;
            border: 1px solid #e2e3e5;
            border-radius: 6px;
            display: inline-block;
            white-space: nowrap;
            line-height: 1.2;
            vertical-align: baseline;
        }
        .info ul { margin: 10px 0; padding-left: 20px; }
        .info li { margin: 6px 0; }
        p { line-height: 1.6; color: #333; }
        a { display: inline-block; margin-top: 20px; padding: 10px 20px; background: #007bff; color: white; text-decoration: none; border-radius: 6px; }
        a:hover { background: #0056b3; }
    </style>
</head>
<body>
    <div class="container">
        <h1>⚠️ Scheduled Maintenance</h1>
        <div class="warning">
            <strong>Service Unavailable</strong><br>
            The application is currently in maintenance mode.
        </div>
        <div class="info">
            <strong>What's happening:</strong>
            <ul style="margin: 10px 0;">
                <li>HTTP Status: <span class="code">503 Service Unavailable</span></li>
                <li>Retry-After: <span class="code">120 seconds</span></li>
                <li>Readiness Probe: <span class="code">READY (200)</span> to keep admin access</li>
                <li>End‑user endpoints return 503; admin remains accessible</li>
            </ul>
        </div>
        <p>This demonstrates graceful degradation in OpenShift where pods report "not ready" during maintenance, removing them from the load balancer without killing the containers.</p>
        <a href="/admin">Admin Panel</a>
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
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial; margin: 0; background: #f5f5f5; }
        .container { max-width: 800px; margin: 50px auto; background: white; padding: 40px; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
        h1 { color: #2c3e50; margin: 0 0 10px 0; }
        .subtitle { color: #666; font-size: 14px; margin-bottom: 30px; }
        .status { padding: 20px; border-radius: 8px; margin: 20px 0; }
        .status.on { background: #fff3cd; border: 2px solid #ffc107; }
        .status.off { background: #d4edda; border: 2px solid #28a745; }
        .status-label { font-size: 14px; color: #666; text-transform: uppercase; letter-spacing: 1px; }
        .status-value { font-size: 24px; font-weight: bold; margin-top: 5px; }
        .status.on .status-value { color: #856404; }
        .status.off .status-value { color: #155724; }
        button { padding: 15px 30px; font-size: 16px; border: none; border-radius: 6px; cursor: pointer; font-weight: 600; }
        .btn-danger { background: #dc3545; color: white; }
        .btn-danger:hover { background: #c82333; }
        .btn-success { background: #28a745; color: white; }
        .btn-success:hover { background: #218838; }
        .info-box { background: #f8f9fa; padding: 20px; border-radius: 6px; margin-top: 30px; border-left: 4px solid #007bff; }
        .info-box h3 { margin: 0 0 10px 0; color: #2c3e50; }
        .info-box ul { margin: 10px 0; padding-left: 20px; }
        .info-box li { margin: 5px 0; color: #555; }
        a { color: #007bff; text-decoration: none; }
        a:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Admin Panel</h1>
        <div class="subtitle">Maintenance Mode Control</div>
        <div class="info-box" style="margin-top:10px">
            <h3 style="margin-top:0">Entry point</h3>
            <ul>
                <li>During maintenance, end‑user routes return <span class="code">503</span>.</li>
                <li>Readiness stays <span class="code">200</span> so admins can reach this page and end maintenance.</li>
            </ul>
        </div>
        <div class="status {{ 'on' if maintenance_mode else 'off' }}">
            <div class="status-label">Current Status</div>
            <div class="status-value">{{ maintenance_status }}</div>
        </div>
        <form action="/admin/toggle" method="POST">
            {% if maintenance_mode %}
            <button type="submit" class="btn-success">
                ✓ Disable Maintenance Mode
            </button>
            {% else %}
            <button type="submit" class="btn-danger">
                ⚠ Enable Maintenance Mode
            </button>
            {% endif %}
        </form>
        <div class="info-box">
            <h3>How it works:</h3>
            <ul>
                <li><strong>Liveness probe (/health):</strong> Always returns 200 - app is alive</li>
                <li><strong>Readiness probe (/ready):</strong> Returns 503 during maintenance</li>
                <li><strong>Result:</strong> Pod removed from Service, traffic stops, no restart</li>
                <li><strong>State storage:</strong> Filesystem flag shared across Gunicorn workers</li>
            </ul>
        </div>
        <p style="margin-top: 30px; color: #666;">
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

    Returns 503 during maintenance mode.
    OpenShift removes the pod from Service endpoints (no restart).
    """
    if is_maintenance_mode():
        return {
            "status": "not_ready",
            "probe_type": "readiness",
            "maintenance_mode": True,
            "message": "Application in maintenance mode",
        }, 503

    return {
        "status": "ready",
        "probe_type": "readiness",
        "maintenance_mode": False,
    }, 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
