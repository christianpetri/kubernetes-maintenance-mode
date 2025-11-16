"""
Kubernetes Maintenance Mode Demo - Best Practice Pattern

Uses Flask's @app.before_request decorator (industry standard):
- Intercepts ALL requests before routing
- Clean separation: maintenance logic in one place
- Readiness probe removes pods from load balancer during maintenance
- Liveness probe keeps pods alive (no restarts needed)
"""

import os
from pathlib import Path

from flask import Flask, redirect, render_template_string, request

app = Flask(__name__)

# Maintenance flag file (shared across all workers)
MAINTENANCE_FLAG = Path("/tmp/maintenance.flag")


def is_maintenance_mode():
    """Check if maintenance mode is active."""
    return MAINTENANCE_FLAG.exists() or os.getenv("MAINTENANCE_MODE", "").lower() == "true"


def is_admin_access():
    """Check if this is an admin pod (always accessible during maintenance)."""
    return os.getenv("ADMIN_ACCESS", "").lower() == "true"


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
    <title>We'll Be Right Back - Maintenance in Progress</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', sans-serif; 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
            min-height: 100vh; 
            display: flex; 
            align-items: center; 
            justify-content: center;
            padding: 20px;
        }
        .container { 
            max-width: 600px; 
            background: white; 
            padding: 60px 40px; 
            border-radius: 24px; 
            box-shadow: 0 20px 60px rgba(0,0,0,0.3); 
            text-align: center; 
        }
        .icon { font-size: 72px; margin-bottom: 20px; animation: pulse 2s ease-in-out infinite; }
        @keyframes pulse { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.05); } }
        h1 { 
            color: #2c3e50; 
            font-size: 32px; 
            margin-bottom: 16px; 
            font-weight: 700; 
        }
        .subtitle { 
            color: #6c757d; 
            font-size: 18px; 
            margin-bottom: 30px; 
            line-height: 1.6;
        }
        .eta-box { 
            background: #f8f9fa; 
            padding: 24px; 
            border-radius: 12px; 
            margin: 30px 0; 
            border-left: 4px solid #667eea; 
        }
        .eta-label { 
            font-size: 12px; 
            color: #6c757d; 
            text-transform: uppercase; 
            letter-spacing: 1.5px; 
            margin-bottom: 8px; 
            font-weight: 600;
        }
        .eta-value { 
            font-size: 24px; 
            color: #667eea; 
            font-weight: 700; 
        }
        .status-info { 
            background: #fff3cd; 
            border: 2px solid #ffc107; 
            padding: 20px; 
            border-radius: 12px; 
            margin: 24px 0; 
        }
        .status-info h3 { 
            color: #856404; 
            font-size: 14px; 
            margin-bottom: 12px; 
            display: flex; 
            align-items: center; 
            justify-content: center; 
            gap: 8px; 
        }
        .status-info h3::before { content: '⚠️'; }
        .status-code { 
            font-family: 'Courier New', monospace; 
            background: rgba(0,0,0,0.05); 
            padding: 8px 16px; 
            border-radius: 6px; 
            display: inline-block; 
            color: #856404; 
            font-size: 14px; 
            font-weight: 600;
        }
        .info-grid { 
            background: #f8f9fa; 
            padding: 20px; 
            border-radius: 12px; 
            margin: 24px 0; 
            text-align: left; 
        }
        .info-grid h3 { 
            font-size: 12px; 
            color: #6c757d; 
            text-transform: uppercase; 
            letter-spacing: 1px; 
            margin-bottom: 12px; 
            text-align: center; 
        }
        .info-item { 
            display: flex; 
            justify-content: space-between; 
            padding: 8px 0; 
            border-bottom: 1px solid #dee2e6; 
            font-size: 14px; 
        }
        .info-item:last-child { border-bottom: none; }
        .info-label { color: #6c757d; }
        .info-value { font-weight: 600; color: #dc3545; }
        .info-value.ok { color: #28a745; }
        .contact { 
            margin-top: 30px; 
            color: #6c757d; 
            font-size: 14px; 
        }
        .contact a { 
            color: #667eea; 
            text-decoration: none; 
            font-weight: 600; 
        }
        .contact a:hover { text-decoration: underline; }
        @media (max-width: 600px) {
            .container { padding: 40px 24px; }
            h1 { font-size: 24px; }
            .icon { font-size: 56px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="icon">🔧</div>
        <h1>We'll Be Right Back</h1>
        <p class="subtitle">
            Our site is currently undergoing scheduled maintenance to improve your experience. 
            We appreciate your patience!
        </p>
        
        <div class="eta-box">
            <div class="eta-label">Estimated Return Time</div>
            <div class="eta-value">~30 minutes</div>
        </div>
        
        <div class="status-info">
            <h3>HTTP 503 - Service Temporarily Unavailable</h3>
            <span class="status-code">Retry-After: 1800 seconds</span>
        </div>
        
        <div class="info-grid">
            <h3>Kubernetes Status</h3>
            <div class="info-item">
                <span class="info-label">Readiness Probe</span>
                <span class="info-value">✗ NOT READY</span>
            </div>
            <div class="info-item">
                <span class="info-label">Liveness Probe</span>
                <span class="info-value ok">✓ HEALTHY</span>
            </div>
            <div class="info-item">
                <span class="info-label">Service Status</span>
                <span class="info-value">REMOVED FROM LB</span>
            </div>
        </div>
        
        <div class="contact">
            <p>Need immediate assistance?</p>
            <p>Contact: <a href="/admin">Admin Panel</a></p>
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
    Intercept all requests before routing.
    This is the Flask standard pattern for maintenance mode.
    """
    # Skip maintenance check for health probes and admin routes
    if request.path in ['/health', '/healthz', '/ready', '/readyz'] or request.path.startswith('/admin'):
        return None
    
    # Show maintenance page for all other routes
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
    """Liveness Probe - Always returns 200 (app is running)."""
    return {"status": "healthy"}, 200


@app.route("/ready")
@app.route("/readyz")
def ready():
    """
    Readiness Probe - Can the application serve traffic?

    Returns 503 during maintenance to remove pod from load balancer.
    Admin pods bypass this via ADMIN_ACCESS check.
    """
    # Admin pods always ready (for maintenance control access)
    if is_admin_access():
        return {"status": "ready", "pod_type": "admin"}, 200
    
    # User pods: not ready during maintenance (removes from LB)
    if is_maintenance_mode():
        return {"status": "not_ready", "maintenance_mode": True}, 503

    return {"status": "ready"}, 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
