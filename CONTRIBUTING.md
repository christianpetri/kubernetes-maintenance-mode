# Contributing to Kubernetes Maintenance Demo

Thank you for your interest in contributing! This guide will help you maintain code quality standards.

## Development Setup

### Prerequisites

- Python 3.11+
- Minikube v1.30+
- kubectl
- Docker Desktop
- Git

### Initial Setup

```powershell
# Clone the repository
git clone https://github.com/christianpetri/openshift-maintenance-demo.git
cd openshift-maintenance-demo

# Create virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1  # On Linux/Mac: source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install development tools
pip install ruff mypy pre-commit

# Set up pre-commit hooks
pre-commit install
```

### Local Development with Minikube

```powershell
# Start Minikube
minikube start --cpus=4 --memory=8192 --driver=docker

# Build image in Minikube's Docker environment
minikube docker-env | Invoke-Expression
docker build -t sample-app:latest .

# Deploy to Minikube
.\scripts\runme.ps1 setup
# Service tunnels open automatically with access URLs
```

## Code Quality Tools

### Python Linting and Formatting

We use **Ruff** - a fast, modern Python linter and formatter that replaces multiple tools:

```bash
# Run linter (checks for issues)
ruff check .

# Fix auto-fixable issues
ruff check . --fix

# Run formatter
ruff format .

# Check formatting without changes
ruff format --check .
```

**Ruff replaces:**

- flake8 (linting)
- black (formatting)
- isort (import sorting)
- pyupgrade (syntax modernization)
- And 10+ other tools!

### Type Checking

We use **mypy** for static type checking:

```bash
# Run type checker
mypy app.py
```

### Markdown Linting

Install markdownlint CLI:

```bash
# Via npm
npm install -g markdownlint-cli

# Or use Docker
docker run -v "$PWD:/workdir" ghcr.io/igorshubovych/markdownlint-cli:latest "**/*.md"
```

Run markdown linter:

```bash
# Check all markdown files
markdownlint '**/*.md'

# Auto-fix issues
markdownlint '**/*.md' --fix
```

### Pre-commit Hooks

Pre-commit hooks run automatically before each commit:

```bash
# Run manually on all files
pre-commit run --all-files

# Update hooks to latest versions
pre-commit autoupdate
```

## Project Structure

```text
openshift-maintenance-demo/
├── app.py                          # Flask application with dual readiness logic
├── requirements.txt                # Python dependencies
├── Dockerfile                      # Container image
├── pyproject.toml                  # Python project config + Ruff/mypy settings
├── .markdownlint.json              # Markdown linting rules
├── .pre-commit-config.yaml         # Pre-commit hook configuration
├── .gitignore                      # Git ignore patterns
├── README.md                       # Main documentation
├── CONTRIBUTING.md                 # This file
├── docs/
│   └── TROUBLESHOOTING.md          # Troubleshooting guide
├── kubernetes/                     # Kubernetes manifests (Minikube)
│   ├── namespace.yaml
│   ├── configmap.yaml
│   ├── deployment.yaml             # User + Admin deployments
│   ├── service.yaml
│   └── ingress.yaml
├── scripts/
│   └── runme.ps1                   # Quick start script
└── .github/
    ├── workflows/
    │   └── lint.yml                # CI/CD linting
    └── copilot-instructions.md     # Copilot customization
```

## Testing

### Local Testing with Minikube

```powershell
# Deploy to Minikube
.\scripts\runme.ps1 setup

# Wait for service tunnels to open
# URLs displayed in tunnel windows
```

### Test Maintenance Mode

```powershell
# Enable maintenance
.\scripts\runme.ps1 enable

# Check pod status
kubectl get pods -n sample-app
# Admin should be 1/1 Ready, User should be 0/1 Not Ready

# Test endpoints (use tunnel window URLs)
# User service: Connection refused
# Admin service: Still accessible

# Disable maintenance
.\scripts\runme.ps1 disable
```

### Test Probes Directly

```powershell
# Test from inside a pod
kubectl exec -n sample-app deploy/sample-app-user -- curl localhost:8080/health
kubectl exec -n sample-app deploy/sample-app-user -- curl localhost:8080/ready
kubectl exec -n sample-app deploy/sample-app-admin -- curl localhost:8080/ready
```

## Making Changes

### Workflow

1. **Create a branch:**

   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make changes** and ensure code quality:

   ```bash
   # Run linting
   ruff check . --fix
   ruff format .

   # Run type checking
   mypy app.py

   # Lint markdown
   markdownlint '**/*.md' --fix
   ```

3. **Test locally:**

   ```bash
   docker-compose up
   ```

4. **Commit changes** (pre-commit hooks run automatically):

   ```bash
   git add .
   git commit -m "feat: add new feature"
   ```

5. **Push and create PR:**

   ```bash
   git push origin feature/your-feature-name
   ```

### Commit Message Format

Use conventional commits:

- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `style:` - Code style changes (formatting)
- `refactor:` - Code refactoring
- `test:` - Test changes
- `chore:` - Build/tooling changes

Examples:

```text
feat: add startup probe support
fix: correct readiness probe response code
docs: update deployment guide
chore: update ruff configuration
```

## Code Style Guidelines

### Python

- Follow PEP 8 (enforced by Ruff)
- Use type hints where appropriate
- Maximum line length: 100 characters
- Use double quotes for strings
- Sort imports automatically (handled by Ruff)

### Markdown

- Maximum line length: 120 characters (except code blocks and tables)
- Use fenced code blocks (```)
- One sentence per line (semantic line breaks)

### YAML

- 2-space indentation
- Use lowercase keys
- Add comments for complex configurations

## Pull Request Process

1. Ensure all tests pass locally
2. Update documentation if needed
3. Add/update tests if applicable
4. Ensure CI/CD checks pass
5. Request review from maintainers

## Questions?

Open an issue or discussion on GitHub!

## License

This project is for educational purposes.
