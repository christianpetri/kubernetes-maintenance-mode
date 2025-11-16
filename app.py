"""
Kubernetes Maintenance Mode Demo - Clean & Simple

DEV Responsibility: Return 503 when maintenance flag exists
OPS Responsibility: Use Kubernetes readiness probes to control traffic routing

Core Pattern:
  1. ConfigMap holds maintenance flag
  2. App reads flag from /config/maintenance (mounted volume)
  3. Readiness probe (/ready) returns 503 if flag exists
  4. Kubernetes removes unhealthy pods from Service
  5. Admin pods always healthy (ADMIN_ACCESS=true env var)
"""

import os
from pathlib import Path

from flask import Flask, render_template_string, request

app = Flask(__name__)

# Configuration
MAINTENANCE_FILE = Path(os.getenv("MAINTENANCE_FILE", "/config/maintenance"))
IS_ADMIN_POD = os.getenv("ADMIN_ACCESS", "").lower() == "true"
POD_NAME = os.getenv("HOSTNAME", "local")


def is_maintenance_mode() -> bool:
    """Check if maintenance mode is enabled via ConfigMap file."""
    if not MAINTENANCE_FILE.exists():
        return False
    try:
        return MAINTENANCE_FILE.read_text().strip().lower() == "true"
    except Exception:
        return False


@app.before_request
def check_maintenance():
    """
    Flask Best Practice: @app.before_request decorator

    Intercepts ALL requests before routing.
    - Health/readiness checks: pass through
    - Admin routes: pass through
    - User routes: return 503 if maintenance mode
    """
    # Allow health checks and admin routes
    if request.path in ["/health", "/healthz", "/ready", "/readyz"]:
        return None
    if request.path.startswith("/admin"):
        return None

    # Block user routes during maintenance
    if is_maintenance_mode():
        return (
            render_template_string(MAINTENANCE_TEMPLATE, pod_name=POD_NAME),
            503,
            {
                "Retry-After": "300",  # Retry after 5 minutes
                "Cache-Control": "no-cache, no-store, must-revalidate",
            },
        )


# ============================================================================
# ROUTES
# ============================================================================


@app.route("/")
def index():
    """User landing page."""
    return render_template_string(INDEX_TEMPLATE, pod_name=POD_NAME)


@app.route("/admin")
def admin():
    """Admin control panel - always accessible."""
    maintenance = is_maintenance_mode()
    return render_template_string(
        ADMIN_TEMPLATE, pod_name=POD_NAME, maintenance=maintenance, is_admin=IS_ADMIN_POD
    )


@app.route("/admin/toggle", methods=["POST"])
def toggle_maintenance():
    """
    Toggle maintenance mode (local development only).

    WARNING: This doesn't work in Kubernetes!
    Each pod has its own filesystem. Use kubectl patch instead:

    kubectl patch configmap sample-app-config -n sample-app \
      -p '{"data":{"maintenance":"true"}}'
    """
    try:
        current = is_maintenance_mode()
        MAINTENANCE_FILE.parent.mkdir(parents=True, exist_ok=True)
        MAINTENANCE_FILE.write_text("false" if current else "true")
        return {"success": True, "maintenance": not current}
    except Exception as e:
        return {"success": False, "error": str(e)}, 500


# ============================================================================
# HEALTH CHECKS (Kubernetes)
# ============================================================================


@app.route("/health")
@app.route("/healthz")
def health():
    """
    Liveness Probe: Is the app running?
    Always returns 200 unless app is completely broken.
    """
    return {"status": "healthy", "pod": POD_NAME}


@app.route("/ready")
@app.route("/readyz")
def ready():
    """
    Readiness Probe: Should this pod receive traffic?

    - Admin pods: Always return 200 (ADMIN_ACCESS=true)
    - User pods: Return 503 if maintenance mode

    Kubernetes uses this to add/remove pods from Service endpoints.
    """
    if IS_ADMIN_POD:
        # Admin pods always ready
        return {"status": "ready", "pod": POD_NAME, "admin": True}

    if is_maintenance_mode():
        # User pods not ready during maintenance
        return (
            {"status": "not_ready", "reason": "maintenance_mode", "pod": POD_NAME},
            503,
        )

    return {"status": "ready", "pod": POD_NAME}


# ============================================================================
# HTML TEMPLATES
# ============================================================================

INDEX_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Maintenance Mode Demo</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            max-width: 800px;
            margin: 50px auto;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }
        .card {
            background: white;
            border-radius: 12px;
            padding: 40px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
        }
        h1 {
            color: #2d3748;
            margin-top: 0;
        }
        .pod-info {
            background: #f7fafc;
            padding: 15px;
            border-radius: 8px;
            margin: 20px 0;
            border-left: 4px solid #667eea;
        }
        .status {
            display: inline-block;
            background: #48bb78;
            color: white;
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 14px;
            font-weight: 600;
        }
        a {
            color: #667eea;
            text-decoration: none;
            font-weight: 600;
        }
        a:hover {
            text-decoration: underline;
        }
        code {
            background: #2d3748;
            color: #48bb78;
            padding: 2px 6px;
            border-radius: 4px;
            font-family: 'Monaco', monospace;
        }
    </style>
</head>
<body>
    <div class="card">
        <h1>🚀 Kubernetes Maintenance Mode Demo</h1>

        <div class="pod-info">
            <strong>Pod:</strong> {{ pod_name }}<br>
            <strong>Status:</strong> <span class="status">✓ Operational</span>
        </div>

        <h2>What This Demonstrates</h2>
        <ul>
            <li><strong>Flask Best Practice:</strong> <code>@app.before_request</code> decorator</li>
            <li><strong>Readiness Probes:</strong> Kubernetes traffic control</li>
            <li><strong>Graceful Degradation:</strong> 503 with Retry-After header</li>
            <li><strong>Admin Access:</strong> Separate deployment always available</li>
        </ul>

        <h2>Try It</h2>
        <p><a href="/admin">→ Open Admin Panel</a> (always accessible)</p>

        <h3>Enable Maintenance Mode</h3>
        <pre style="background: #2d3748; color: #48bb78; padding: 15px; border-radius: 8px; overflow-x: auto;">kubectl patch configmap sample-app-config -n sample-app \\
  -p '{"data":{"maintenance":"true"}}'</pre>

        <p>Then watch this page return 503 while admin stays accessible! ✨</p>
    </div>
</body>
</html>
"""

ADMIN_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Admin Panel - Maintenance Mode</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            max-width: 900px;
            margin: 50px auto;
            padding: 20px;
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            min-height: 100vh;
        }
        .card {
            background: white;
            border-radius: 12px;
            padding: 40px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
        }
        h1 {
            color: #2d3748;
            margin-top: 0;
        }
        .pod-info {
            background: #fff5f5;
            padding: 15px;
            border-radius: 8px;
            margin: 20px 0;
            border-left: 4px solid #f5576c;
        }
        .admin-badge {
            display: inline-block;
            background: #f5576c;
            color: white;
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 14px;
            font-weight: 600;
        }
        .status-box {
            background: #f7fafc;
            border: 2px solid #e2e8f0;
            border-radius: 8px;
            padding: 20px;
            margin: 20px 0;
        }
        .status-on {
            color: #e53e3e;
            font-weight: 700;
        }
        .status-off {
            color: #38a169;
            font-weight: 700;
        }
        button {
            background: #667eea;
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: background 0.2s;
        }
        button:hover {
            background: #5568d3;
        }
        button:disabled {
            background: #cbd5e0;
            cursor: not-allowed;
        }
        .warning {
            background: #fffaf0;
            border-left: 4px solid #ed8936;
            padding: 15px;
            margin: 20px 0;
            border-radius: 4px;
        }
        code {
            background: #2d3748;
            color: #48bb78;
            padding: 2px 6px;
            border-radius: 4px;
            font-family: 'Monaco', monospace;
        }
        pre {
            background: #2d3748;
            color: #48bb78;
            padding: 15px;
            border-radius: 8px;
            overflow-x: auto;
        }
    </style>
</head>
<body>
    <div class="card">
        <h1>🔧 Admin Control Panel</h1>

        <div class="pod-info">
            <strong>Pod:</strong> {{ pod_name }}<br>
            <strong>Type:</strong> <span class="admin-badge">ADMIN POD</span><br>
            <strong>Always Accessible:</strong> ✓ Yes
        </div>

        <div class="status-box">
            <h2>Maintenance Mode Status</h2>
            {% if maintenance %}
                <p class="status-on">🔴 ENABLED - User pods returning 503</p>
            {% else %}
                <p class="status-off">🟢 DISABLED - All pods operational</p>
            {% endif %}
        </div>

        <div class="warning">
            <strong>⚠️ Local Toggle Limitation</strong><br>
            The button below only works in local development.
            In Kubernetes, each pod has its own filesystem!
        </div>

        <button onclick="toggleMaintenance()" id="toggleBtn">
            {% if maintenance %}Disable{% else %}Enable{% endif %} Maintenance (Local Only)
        </button>

        <h2>Production Usage (Kubernetes)</h2>
        <p>Use kubectl to patch the ConfigMap:</p>

        <h3>Enable Maintenance</h3>
        <pre>kubectl patch configmap sample-app-config -n sample-app \\
  -p '{"data":{"maintenance":"true"}}'</pre>

        <h3>Disable Maintenance</h3>
        <pre>kubectl patch configmap sample-app-config -n sample-app \\
  -p '{"data":{"maintenance":"false"}}'</pre>

        <h3>Verify Pod Endpoints</h3>
        <pre>kubectl get endpoints -n sample-app sample-app-user
kubectl get endpoints -n sample-app sample-app-admin</pre>

        <p style="margin-top: 30px;">
            <a href="/">← Back to User View</a>
        </p>
    </div>

    <script>
        async function toggleMaintenance() {
            const btn = document.getElementById('toggleBtn');
            btn.disabled = true;
            btn.textContent = 'Toggling...';

            try {
                const response = await fetch('/admin/toggle', {
                    method: 'POST'
                });
                const data = await response.json();

                if (data.success) {
                    location.reload();
                } else {
                    alert('Error: ' + data.error);
                    btn.disabled = false;
                }
            } catch (error) {
                alert('Request failed: ' + error);
                btn.disabled = false;
            }
        }
    </script>
</body>
</html>
"""

MAINTENANCE_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Maintenance Mode</title>
    <meta http-equiv="refresh" content="300">
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            max-width: 700px;
            margin: 50px auto;
            padding: 20px;
            background: linear-gradient(135deg, #ffd89b 0%, #19547b 100%);
            min-height: 100vh;
            text-align: center;
        }
        .card {
            background: white;
            border-radius: 12px;
            padding: 60px 40px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.3);
        }
        .icon {
            font-size: 80px;
            margin-bottom: 20px;
        }
        h1 {
            color: #2d3748;
            margin: 20px 0;
        }
        p {
            color: #4a5568;
            font-size: 18px;
            line-height: 1.6;
        }
        .retry {
            background: #f7fafc;
            padding: 15px;
            border-radius: 8px;
            margin: 30px 0;
            color: #2d3748;
        }
        code {
            background: #2d3748;
            color: #48bb78;
            padding: 2px 6px;
            border-radius: 4px;
            font-family: 'Monaco', monospace;
        }
    </style>
</head>
<body>
    <div class="card">
        <div class="icon">🔧</div>
        <h1>Service Temporarily Unavailable</h1>
        <p>We're performing scheduled maintenance to improve your experience.</p>
        <p>This page will automatically refresh in 5 minutes.</p>

        <div class="retry">
            <strong>HTTP 503</strong> with <code>Retry-After: 300</code> header<br>
            <small>Pod: {{ pod_name }}</small>
        </div>

        <p style="font-size: 14px; color: #718096;">
            Admin access remains available during maintenance.
        </p>
    </div>
</body>
</html>
"""

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
