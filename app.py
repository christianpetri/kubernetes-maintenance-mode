"""
Kubernetes Maintenance Mode Demo - Clean & Simple

DEV Responsibility: Return 503 when maintenance flag exists
OPS Responsibility: Use Kubernetes readiness probes to control traffic routing

Core Pattern:
  1. ConfigMap holds maintenance flag
  2. App reads flag from /config/maintenance (mounted as volume)
  3. Readiness probe (/ready) returns 503 if maintenance enabled
  4. Kubernetes removes unready pods from Service endpoints
  5. Admin pods always return 200 (ADMIN_ACCESS=true env var)

Demo Enhancement:
  - Optional Redis for shared state (demo mode only)
  - Shows real-time sync across pods during presentations
  - Production still uses ConfigMap (proper Kubernetes pattern)
"""

import os
import sys
from pathlib import Path

from flask import Flask, render_template_string, request

app = Flask(__name__)

# Configuration
MAINTENANCE_FILE = Path(os.getenv("MAINTENANCE_FILE", "/config/maintenance"))
# KEY DIFFERENCE: Admin and user pods run identical code - only this env var differs
# Admin pods: ADMIN_ACCESS=true  (always accessible via /admin routes)
# User pods:  ADMIN_ACCESS=false (blocked during maintenance mode)
IS_ADMIN_POD = os.getenv("ADMIN_ACCESS", "").lower() == "true"
POD_NAME = os.getenv("HOSTNAME", "local")

# Redis for demo mode (optional - shows real-time sync)
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
# Handle Kubernetes service discovery env vars (REDIS_SERVICE_PORT) or explicit REDIS_PORT
redis_port_str = os.getenv("REDIS_PORT", "6379")
# If it contains "tcp://", extract just the port number
if "tcp://" in redis_port_str:
    redis_port_str = "6379"  # Use default port when K8s injects service URL
REDIS_PORT = int(redis_port_str)
redis_client = None

try:
    import redis

    redis_client = redis.Redis(
        host=REDIS_HOST, port=REDIS_PORT, decode_responses=True, socket_connect_timeout=2
    )
    redis_client.ping()
    sys.stderr.write(f"[REDIS] Connected for demo state sync at {REDIS_HOST}:{REDIS_PORT}\n")
    sys.stderr.flush()
except Exception as e:
    sys.stderr.write(f"[REDIS] Not available (demo mode will be per-pod): {e}\n")
    sys.stderr.flush()
    redis_client = None


def is_maintenance_mode() -> bool:
    """Check if maintenance mode is enabled.

    Checks multiple sources in priority order for maintenance state.
    This supports both demo and production deployment patterns.

    Priority order:
    1. Redis shared state (demo mode - cross-pod synchronization)
    2. Local file flag (single pod testing)
    3. ConfigMap file (production Kubernetes pattern)

    Returns:
        Boolean indicating whether maintenance mode is currently enabled.
        Returns False if no maintenance indicator is found.
    """
    # Demo mode: Check Redis for shared state (instant cross-pod sync)
    if redis_client:
        try:
            redis_value = redis_client.get("maintenance_mode")
            if redis_value is not None:
                # Redis client returns bytes or str depending on decode_responses setting
                if isinstance(redis_value, bytes):
                    redis_state = redis_value.decode("utf-8")
                else:
                    redis_state = str(redis_value)
                return redis_state.lower() == "true"
        except Exception:
            pass

    # Production: Check ConfigMap file mount (or local file for testing)
    if not MAINTENANCE_FILE.exists():
        return False
    try:
        return MAINTENANCE_FILE.read_text().strip().lower() == "true"
    except Exception:
        return False


@app.before_request
def check_maintenance():
    """Intercept all requests before routing to check maintenance status.

    This implements the Flask best practice pattern using the
    @app.before_request decorator for centralized request filtering.

    Request handling rules:
    - Health and readiness checks pass through unconditionally
    - Admin routes require admin pod authentication
    - User routes return 503 during maintenance mode

    Returns:
        None to allow request processing, or Flask response tuple
        with (content, status_code, headers) to block the request.
    """
    # Allow health checks
    if request.path in ["/health", "/healthz", "/ready", "/readyz"]:
        return None

    # Admin routes only accessible from admin pods
    if request.path.startswith("/admin"):
        if not IS_ADMIN_POD:
            return (
                render_template_string(
                    """
                    <!DOCTYPE html>
                    <html><head><title>403 Forbidden</title></head>
                    <body style="font-family: sans-serif; text-align: center; padding: 50px;">
                        <h1>403 Forbidden</h1>
                        <p>Admin routes are only accessible from admin pods.</p>
                        <p>Access via the admin service endpoint.</p>
                    </body></html>
                    """
                ),
                403,
            )
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
    """Render the user-facing landing page.

    Returns:
        Rendered HTML template showing application status and
        demonstration instructions.
    """
    return render_template_string(INDEX_TEMPLATE, pod_name=POD_NAME, is_admin_pod=IS_ADMIN_POD)


@app.route("/admin")
def admin():
    """Render the administrative control panel.

    This endpoint is always accessible from admin pods, even during
    maintenance mode. Provides interface for toggling maintenance state
    and viewing Kubernetes integration commands.

    Returns:
        Rendered HTML template showing maintenance controls and
        production deployment instructions.
    """
    maintenance = is_maintenance_mode()
    return render_template_string(
        ADMIN_TEMPLATE, pod_name=POD_NAME, maintenance=maintenance, is_admin=IS_ADMIN_POD
    )


@app.route("/admin/toggle", methods=["POST"])
def toggle_maintenance():
    """Toggle maintenance mode state via Redis.

    This endpoint is designed for demonstration purposes to show
    the maintenance mode workflow. Production deployments should use
    Kubernetes ConfigMaps with kubectl commands.

    Demo Mode Behavior:
        With Redis: Toggles shared state visible to all pods instantly.
                   Demonstrates real-time pod draining behavior.
        Without Redis: Returns error - Redis required for toggle.

    Production Integration:
        Instead of this endpoint, production systems should:
        1. Update ConfigMap via kubectl or CI/CD pipeline
        2. Restart deployments to apply configuration changes
        3. Use approval workflows and audit logging

    Example production commands:
        kubectl patch configmap sample-app-config -n sample-app
          -p '{"data":{"maintenance":"true"}}'
        kubectl rollout restart deployment/sample-app-user -n sample-app

    Returns:
        JSON response with success status and mode information.
        HTTP 200 on success, HTTP 500 if Redis unavailable.

    Raises:
        Returns error response if Redis connection fails or is unavailable.
    """
    try:
        current = is_maintenance_mode()
        new_state = "false" if current else "true"

        # Use Redis for shared state (syncs across pods)
        if redis_client:
            try:
                redis_client.set("maintenance_mode", new_state)
                return {
                    "success": True,
                    "maintenance": not current,
                    "mode": "redis",
                    "note": "Redis state updated - all pods will sync instantly!",
                }
            except Exception as redis_error:
                return {
                    "success": False,
                    "error": f"Redis connection failed: {redis_error}",
                    "note": "Redis is required for maintenance mode toggle in Kubernetes",
                }, 500

        # No Redis available
        return {
            "success": False,
            "error": "Redis not available",
            "note": "Redis is required for maintenance mode toggle in Kubernetes",
        }, 500
    except Exception as e:
        return {"success": False, "error": str(e)}, 500


# ============================================================================
# HEALTH CHECKS (Kubernetes)
# ============================================================================


@app.route("/health")
@app.route("/healthz")
def health():
    """Kubernetes liveness probe endpoint.

    Indicates whether the application process is running correctly.
    Always returns 200 unless the application is completely non-functional.
    Kubernetes will restart the pod if this check fails repeatedly.

    Returns:
        Dictionary with status and pod identification, HTTP 200.
    """
    return {"status": "healthy", "pod": POD_NAME}


@app.route("/ready")
@app.route("/readyz")
def ready():
    """Kubernetes readiness probe endpoint.

    Indicates whether the pod should receive traffic from the Service.
    Kubernetes uses this to dynamically add or remove pods from the
    Service endpoint list without restarting pods.

    Behavior:
    - Admin pods: Always return 200 (guaranteed access)
    - User pods: Return 503 during maintenance mode

    Returns:
        Dictionary with readiness status and pod identification.
        HTTP 200 when ready, HTTP 503 when not ready.
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
        .pod-type {
            color: #667eea;
            font-weight: 600;
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
        .user-badge {
            display: inline-block;
            background: #667eea;
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
        .admin-link {
            display: inline-block;
            background: #f5576c;
            color: white;
            padding: 12px 24px;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            text-decoration: none;
            transition: background 0.2s;
            margin: 10px 0;
        }
        .admin-link:hover {
            background: #e04556;
            text-decoration: none;
        }
        .help-text {
            font-size: 13px;
            color: #718096;
            text-align: center;
            margin-top: 8px;
            line-height: 1.5;
        }
        code {
            background: #2d3748;
            color: #48bb78;
            padding: 2px 6px;
            border-radius: 4px;
            font-family: 'Monaco', monospace;
        }
        .maintenance-banner {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            background: #f59e0b;
            color: white;
            padding: 20px;
            text-align: center;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            z-index: 1000;
            display: none;
            animation: slideDown 0.5s ease-out;
        }
        .maintenance-banner.show {
            display: block;
        }
        .maintenance-banner h2 {
            margin: 0 0 10px 0;
            color: white;
        }
        .maintenance-banner p {
            margin: 5px 0;
        }
        .maintenance-banner .countdown {
            font-size: 24px;
            font-weight: bold;
            margin: 10px 0;
        }
        @keyframes slideDown {
            from {
                transform: translateY(-100%);
            }
            to {
                transform: translateY(0);
            }
        }
    </style>
</head>
<body>
    <div class="maintenance-banner" id="maintenanceBanner">
        <h2>Maintenance Mode Starting</h2>
        <p>Please save your work. You will be logged out in:</p>
        <div class="countdown" id="countdown">30</div>
        <p><small>Redirecting to maintenance page...</small></p>
    </div>
    <div class="card">
        <h1>Kubernetes Maintenance Mode Demo</h1>

        <div class="pod-info">
            <strong>Pod:</strong> {{ pod_name }}<br>
            <strong>Type:</strong>
            {% if is_admin_pod %}
                <span class="admin-badge">ADMIN POD</span>
            {% else %}
                <span class="user-badge">USER POD</span>
            {% endif %}
            <br>
            <strong>Status:</strong> <span class="status">Operational</span>
        </div>

        {% if is_admin_pod %}
        <div style="background: #fff5f5; padding: 15px; border-radius: 8px; border-left: 4px solid #f5576c; margin: 20px 0;">
            <strong style="color: #2d3748; font-size: 16px;">🎛️ Admin Service Detected</strong>
            <p style="margin: 10px 0 15px 0; color: #4a5568;">You are viewing the admin service. Click below to access the control panel and manage maintenance mode.</p>
            <a href="/admin" style="display: inline-block; background: #f5576c; color: white; padding: 10px 20px; border-radius: 6px; text-decoration: none; font-weight: 600;">→ Open Admin Control Panel</a>
        </div>

        <h2>What This Demo Shows</h2>
        <ul style="line-height: 1.8;">
            <li>Graceful maintenance mode with zero downtime for administrators</li>
            <li>Admin access preserved during maintenance windows</li>
            <li>Automatic traffic routing via Kubernetes readiness probes</li>
            <li>Industry-standard HTTP 503 error handling with retry instructions</li>
        </ul>

        <h2>How to Test</h2>
        <ol style="line-height: 1.8; background: #f7fafc; padding: 20px 20px 20px 40px; border-radius: 8px; margin: 20px 0;">
            <li><strong>Click "Open Admin Control Panel"</strong> above to access maintenance controls</li>
            <li><strong>Enable maintenance mode</strong> using the toggle button</li>
            <li><strong>Observe the behavior:</strong>
                <ul style="margin-top: 8px; color: #4a5568;">
                    <li>Active user sessions see a warning banner with countdown</li>
                    <li>New requests fail with connection refused (pods removed from service)</li>
                    <li>Kubernetes Service stops routing to user pods (readiness probe failure)</li>
                </ul>
            </li>
            <li><strong>Return to admin panel</strong> to disable maintenance and restore service</li>
        </ol>
        <p style="background: #e6fffa; padding: 12px; border-radius: 6px; border-left: 4px solid #38b2ac; margin-top: 15px; font-size: 14px;">
            <strong>📝 Production Difference:</strong> External load balancer would serve a static "We'll be back soon" page instead of connection refused.
        </p>
        {% else %}
        <h2>What This Demo Shows</h2>
        <ul style="line-height: 1.8;">
            <li>Graceful maintenance mode with zero downtime for administrators</li>
            <li>Admin access preserved during maintenance windows</li>
            <li>Automatic traffic routing via Kubernetes readiness probes</li>
            <li>Industry-standard HTTP 503 error handling with retry instructions</li>
        </ul>

        <h2>How to Access Admin Controls</h2>
        <p style="background: #fff5f5; padding: 15px; border-radius: 8px; border-left: 4px solid #f5576c; margin: 20px 0;">
            <strong style="color: #2d3748;">To toggle maintenance mode, you need admin access:</strong><br><br>
            Open the <strong>admin service URL</strong> in a separate browser tab to access the control panel.<br>
            <small style="color: #718096; display: block; margin-top: 8px;">(The admin service runs on a separate endpoint from this user service)</small>
        </p>

        <h2>Demo Flow</h2>
        <ol style="line-height: 1.8; background: #fffaf0; padding: 20px 20px 20px 40px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #ed8936;">
            <li><strong>Access admin service</strong> using the admin service URL (separate endpoint)</li>
            <li><strong>Enable maintenance mode</strong> via the admin control panel button</li>
            <li><strong>Watch this page</strong> - a warning banner appears with a 30-second countdown, then shows 503 maintenance message</li>
            <li><strong>Open user service in a new tab</strong> - connection fails (ERR_CONNECTION_RESET) because Kubernetes removes unhealthy pods from service</li>
            <li><strong>Return to admin service</strong> to disable maintenance and restore normal operation</li>
        </ol>
        <p style="background: #e6fffa; padding: 12px; border-radius: 6px; border-left: 4px solid #38b2ac; margin-top: 15px; font-size: 14px;">
            <strong>Production Difference:</strong> External load balancer would serve a static "We'll be back soon" page instead of connection refused.
        </p>
        {% endif %}

        <details style="margin: 20px 0;">
            <summary style="cursor: pointer; font-weight: 600; color: #2d3748; padding: 10px; background: #f7fafc; border-radius: 6px;">📋 Technical Implementation Details</summary>
            <div style="padding: 15px; background: #f7fafc; border-radius: 6px; margin-top: 10px;">
                <h4 style="margin-top: 0;">Architecture Pattern</h4>
                <ul style="line-height: 1.8;">
                    <li><strong>Flask Best Practice:</strong> <code>@app.before_request</code> decorator for centralized request filtering</li>
                    <li><strong>Kubernetes Readiness Probes:</strong> Automatic traffic control via health checks</li>
                    <li><strong>Dual Deployment:</strong> Separate admin and user pod deployments</li>
                    <li><strong>HTTP 503 Response:</strong> Standard Service Unavailable with Retry-After header</li>
                </ul>
                <h4>State Synchronization</h4>
                <ul style="line-height: 1.8;">
                    <li><strong>Demo (with Redis):</strong> Maintenance state syncs instantly across all pods (ideal for demonstrations)</li>
                    <li><strong>Demo (without Redis):</strong> Changes affect only the current pod (local testing)</li>
                    <li><strong>Production:</strong> ConfigMap updates with deployment restarts (Kubernetes native pattern)</li>
                </ul>
                <h4>Maintenance Page Delivery</h4>
                <ul style="line-height: 1.8;">
                    <li><strong>This Demo:</strong> Application pods serve the 503 maintenance page via <code>@app.before_request</code> (simplifies demo - no external infrastructure needed)</li>
                    <li><strong>Production:</strong> External load balancer (nginx, HAProxy, cloud ALB) serves static maintenance HTML independently, bypassing application entirely and ensuring availability during complete outages</li>
                </ul>
                <h4>Traffic Routing</h4>
                <ul style="line-height: 1.8;">
                    <li><strong>This Demo:</strong> Kubernetes Service removes unhealthy pods from endpoints based on readiness probes</li>
                    <li><strong>Production:</strong> External load balancer health checks determine routing, typically with static maintenance page served at load balancer level before reaching Kubernetes</li>
                </ul>
            </div>
        </details>

        <details style="margin: 20px 0;">
            <summary style="cursor: pointer; font-weight: 600; color: #2d3748; padding: 10px; background: #e6fffa; border-radius: 6px;">⚙️ Production Deployment with Kubernetes</summary>
            <div style="padding: 15px; background: #e6fffa; border-radius: 6px; margin-top: 10px;">
                <p style="color: #2d3748; margin-top: 0;">In production environments, use kubectl to manage maintenance mode:</p>

                <h4 style="margin-top: 15px;">Enable Maintenance</h4>
                <pre style="background: #2d3748; color: #48bb78; padding: 15px; border-radius: 8px; overflow-x: auto;"># Update ConfigMap
kubectl patch configmap sample-app-config -n sample-app \\
  -p '{"data":{"maintenance":"true"}}'

# Restart user deployment
kubectl rollout restart deployment/sample-app-user -n sample-app</pre>

                <h4>Disable Maintenance</h4>
                <pre style="background: #2d3748; color: #48bb78; padding: 15px; border-radius: 8px; overflow-x: auto;"># Update ConfigMap
kubectl patch configmap sample-app-config -n sample-app \\
  -p '{"data":{"maintenance":"false"}}'

# Restart user deployment
kubectl rollout restart deployment/sample-app-user -n sample-app</pre>

                <h4>Verify Status</h4>
                <pre style="background: #2d3748; color: #48bb78; padding: 15px; border-radius: 8px; overflow-x: auto;"># Check service endpoints
kubectl get endpoints -n sample-app

# Check pod readiness
kubectl get pods -n sample-app -o wide</pre>
            </div>
        </details>
    </div>

    <script>
        let countdownTimer;
        let secondsLeft = 30;

        // Check maintenance status every 3 seconds
        setInterval(async () => {
            try {
                const response = await fetch('/ready');
                const data = await response.json();

                // If maintenance mode detected, show banner and start countdown
                if (data.status === 'not_ready' && data.reason === 'maintenance_mode') {
                    showMaintenanceBanner();
                }
            } catch (error) {
                console.log('Status check failed:', error);
            }
        }, 3000);

        function showMaintenanceBanner() {
            const banner = document.getElementById('maintenanceBanner');
            if (banner.classList.contains('show')) return; // Already showing

            banner.classList.add('show');

            // Start countdown
            countdownTimer = setInterval(() => {
                secondsLeft--;
                document.getElementById('countdown').textContent = secondsLeft;

                if (secondsLeft <= 0) {
                    clearInterval(countdownTimer);
                    // Redirect to trigger maintenance page
                    window.location.reload();
                }
            }, 1000);
        }
    </script>
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
        <h1>Admin Control Panel</h1>

        <div class="pod-info">
            <strong>Pod:</strong> {{ pod_name }}<br>
            <strong>Type:</strong> <span class="admin-badge">ADMIN POD</span>
        </div>

        <div class="status-box">
            <h2>Maintenance Mode Status</h2>
            {% if maintenance %}
                <p class="status-on">ENABLED - User service returning 503 errors</p>
                <p style="margin-top: 15px;">
                    <a href="/" target="_blank" style="color: #667eea; text-decoration: none; font-weight: 600; font-size: 14px;">
                        → View maintenance page (opens in new tab)
                    </a>
                </p>
                <p style="margin-top: 10px; font-size: 13px; color: #666; font-style: italic;">
                    <strong>Demo Setup:</strong> This maintenance page is served from application pods. Admin service remains accessible independently.<br>
                    <strong>Production Setup:</strong> External load balancer (nginx, HAProxy, cloud ALB) would serve a static maintenance page. Admin access via separate internal endpoint.
                </p>
            {% else %}
                <p class="status-off">DISABLED - All services operational</p>
            {% endif %}
        </div>

        <div class="warning">
            <strong>Demo vs Production Modes</strong><br>
            <strong>DEMO (with Redis):</strong> Button syncs maintenance state across all pods instantly (ideal for live demonstrations)<br>
            <strong>DEMO (without Redis):</strong> Button affects only this pod (local testing)<br>
            <strong>PRODUCTION:</strong> Use kubectl commands to update ConfigMap (proper Kubernetes pattern)
        </div>

        <button onclick="toggleMaintenance()" id="toggleBtn">
            {% if maintenance %}Disable{% else %}Enable{% endif %} Maintenance (Demo)
        </button>
        <p style="font-size: 14px; color: #718096; margin-top: 10px;">
            Click the button above to toggle maintenance mode and observe the user interface behavior.
        </p>

        <h2>Production Usage (Kubernetes)</h2>
        <p><strong>Step 1:</strong> Update ConfigMap (single source of truth)</p>

        <h3>Enable Maintenance</h3>
        <pre>kubectl patch configmap sample-app-config -n sample-app \\
  -p '{"data":{"maintenance":"true"}}'</pre>

        <p><strong>Step 2:</strong> Restart deployments to pick up new config</p>
        <pre>kubectl rollout restart deployment/sample-app-user -n sample-app</pre>

        <h3>Disable Maintenance</h3>
        <pre>kubectl patch configmap sample-app-config -n sample-app \\
  -p '{"data":{"maintenance":"false"}}'
kubectl rollout restart deployment/sample-app-user -n sample-app</pre>

        <h3>Verify Status</h3>
        <pre># Check which pods are ready (in service)
kubectl get endpoints -n sample-app sample-app-user
kubectl get endpoints -n sample-app sample-app-admin

# Check readiness probe status
kubectl get pods -n sample-app -o wide</pre>

        <h3>Production Integration</h3>
        <p style="background: #f0f9ff; padding: 15px; border-radius: 8px; border-left: 4px solid #3b82f6;">
            <strong>Production Implementation Recommendations:</strong><br>
            • Integrate kubectl commands into your CI/CD pipeline (Jenkins, GitLab CI, GitHub Actions, etc.)<br>
            • Use Kubernetes operators or custom controllers for automated management<br>
            • Build an admin dashboard that interfaces with the kubectl API<br>
            • Implement approval workflows and comprehensive audit logging<br>
            • Monitor active user sessions before enabling maintenance mode
        </p>

        <p style="margin-top: 30px;">
            <a href="/" style="color: #667eea; text-decoration: none; font-weight: 600;">← Back to Landing Page</a>
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
        <p>We are performing scheduled maintenance to improve your experience.</p>
        <p>This page will automatically refresh in 5 minutes.</p>

        <div class="retry">
            <strong>HTTP 503 Service Unavailable</strong><br>
            <code>Retry-After: 300</code> header included<br>
            <small style="color: #718096;">Pod: {{ pod_name }}</small>
        </div>

        <p style="font-size: 14px; color: #718096; margin-top: 20px;">
            <strong>Note:</strong> Administrative access remains available during maintenance.
        </p>

        <p style="margin-top: 20px; text-align: center;">
            <a href="/" target="_blank" style="display: inline-block; color: #667eea; text-decoration: none; font-weight: 600; padding: 10px 20px; border: 2px solid #667eea; border-radius: 6px;">
                ↻ Try accessing the service again
            </a>
            <br>
            <small style="display: block; margin-top: 8px; color: #a0aec0;">(Will show this maintenance page while service is down)</small>
        </p>
    </div>
</body>
</html>
"""

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
