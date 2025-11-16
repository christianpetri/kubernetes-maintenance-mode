# Project File Structure

Complete directory tree of the Demo_503 Kubernetes Maintenance Mode Demo project.

Generated: 2025-11-16 16:20:09

```text
Demo_503/
├── app.py                                    # Main Flask application (676 lines)
├── app_complex_backup.py                     # Previous complex version (backup)
├── Dockerfile                                # Container image definition
├── requirements.txt                          # Python dependencies
├── pyproject.toml                            # Python project configuration (Ruff linting)
├── README.md                                 # Project overview and quick start
├── DESIGN.md                                 # System design and architecture
├── CONTRIBUTING.md                           # Contribution guidelines
│
├── docs/                                     # Documentation directory
│   ├── ACTIVE_USER_TRACKING.md              # User session tracking (future feature)
│   ├── CUSTOM_503_PAGES.md                  # Custom maintenance page implementation
│   ├── GITHUB_SETUP.md                      # GitHub repository setup guide
│   ├── TROUBLESHOOTING.md                   # Troubleshooting guide
│   ├── MAINTENANCE_PAGE_QUICK_REF.md        # Quick reference for 503 pages
│   ├── PRODUCTION_ROUTING.md                # Production routing patterns explained
│   └── PROJECT_STRUCTURE.md                 # This file!
│
├── kubernetes/                               # Kubernetes manifests
│   ├── namespace.yaml                        # sample-app namespace
│   ├── configmap.yaml                        # Configuration for maintenance mode
│   ├── redis-deployment.yaml                 # Redis for demo mode sync
│   ├── deployment.yaml                       # User & admin pod deployments
│   ├── service.yaml                          # User & admin services
│   ├── ingress.yaml                          # Ingress with custom 503 handling
│   ├── maintenance-page-deployment.yaml      # Custom 503 page (nginx + ConfigMap)
│   └── maintenance-page/
│       └── index.html                        # Standalone maintenance page HTML
│
└── scripts/                                  # PowerShell automation scripts
    ├── runme.ps1                             # Main demo runner (all-in-one)
    ├── deploy-update.ps1                     # Build and deploy updates
    ├── demo-real-user-access.ps1             # Set up Ingress for real user testing
    ├── test-endpoints.ps1                    # Test readiness and maintenance endpoints
    └── test-all-buttons.ps1                  # Test all admin UI buttons
```

## Key Files Explained

### Application Code

- **app.py** (676 lines)
  - Flask application with maintenance mode
  - Three-tier check: Redis → File → ConfigMap
  - Admin access control (user pods → 403)
  - Warning banner with 30-second countdown
  - Production-ready patterns

### Kubernetes Infrastructure

#### Core Application

- **deployment.yaml** - User (2 replicas) & admin (1 replica) deployments
- **service.yaml** - Separate services for user and admin traffic
- **redis-deployment.yaml** - Redis for instant cross-pod sync (demo mode)

#### Networking

- **ingress.yaml** - Routes traffic, serves custom 503 on maintenance
- **maintenance-page-deployment.yaml** - Nginx pod serving beautiful 503 page

#### Configuration

- **namespace.yaml** - Isolated namespace for demo
- **configmap.yaml** - Maintenance mode configuration (production pattern)

### Documentation

- **TROUBLESHOOTING.md** - Comprehensive troubleshooting guide
- **PRODUCTION_ROUTING.md** - Port-forward vs Ingress explained
- **CUSTOM_503_PAGES.md** - How to serve custom maintenance pages
- **DESIGN.md** - System design and architecture patterns
- **MAINTENANCE_PAGE_QUICK_REF.md** - Quick reference for 503 pages

### Scripts

All scripts are PowerShell for Windows:

- **runme.ps1** - One-command demo setup (builds, deploys, tests)
- **deploy-update.ps1** - Rebuild image and update pods
- **demo-real-user-access.ps1** - Configure Ingress for real user testing
- **test-endpoints.ps1** - Health check and maintenance toggle testing
- **test-all-buttons.ps1** - Automated UI testing

## File Statistics

```text
Total Files: ~25 files
Total Lines of Code: ~2,000 lines
  - Python: 676 lines (app.py)
  - YAML: ~400 lines (Kubernetes manifests)
  - PowerShell: ~300 lines (automation scripts)
  - Markdown: ~600 lines (documentation)
  - HTML: ~100 lines (maintenance page)

Documentation: 7 detailed markdown files
Kubernetes Manifests: 8 YAML files
Scripts: 5 PowerShell automation scripts
```

## Technology Stack

- **Language:** Python 3.11+
- **Framework:** Flask 3.0.0
- **Cache:** Redis 5.0.1 (demo mode)
- **Container:** Docker with multi-stage build
- **Orchestration:** Kubernetes (tested on Minikube v1.34.0)
- **Ingress:** nginx-ingress-controller v1.13.2
- **Web Server:** Nginx (for maintenance page)
- **Linting:** Ruff (configured in pyproject.toml)

## Production Readiness

### Production-Ready Features

- Flask @app.before_request pattern (industry standard)
- Kubernetes readiness probes for graceful drain
- Separate admin pods (guaranteed access during maintenance)
- Redis-based instant sync across pods
- Custom 503 maintenance page via Ingress
- Retry-After headers for API clients
- Warning banner for active users
- Security: User pods cannot access /admin routes

### 🔄 Future Enhancements

- Authentication (OAuth2/OIDC)
- Observability (Prometheus metrics, structured logging)
- Active user tracking (WebSocket session management)
- Multi-region support
- Helm chart for easier deployment

## Getting Started

```bash
# Quick start (one command)
.\scripts\runme.ps1

# Manual setup
minikube start
eval $(minikube docker-env)  # Use Minikube's Docker
docker build -t sample-app:latest .
kubectl apply -f kubernetes/

# Test real user access
.\scripts\demo-real-user-access.ps1
```

## Related Documentation

- **README.md** - Project overview, quick start
- **DESIGN.md** - System design principles
- **TROUBLESHOOTING.md** - Problem resolution guide
- **PRODUCTION_ROUTING.md** - How Ingress routing works
- **CUSTOM_503_PAGES.md** - Maintenance page patterns
