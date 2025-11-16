# GitHub Repository Configuration

Recommendations for enhancing repository visibility.

## GitHub Topics (Settings → Topics)

**Core**: `kubernetes` `minikube` `docker` `python` `flask`  
**Patterns**: `maintenance-mode` `readiness-probe` `503-service-unavailable`
`high-availability` `flask-best-practices`  
**Use Cases**: `demo` `tutorial` `devops` `site-reliability-engineering`

## Repository Settings

### Description

**Current:**

```text
A demonstration of implementing maintenance mode in Kubernetes with 503 Service Unavailable responses
for regular users while guaranteeing admin access remains available during maintenance windows.
```

**Recommended (shorter for GitHub display):**

```text
Kubernetes maintenance mode demo with admin-always-accessible pattern using readiness probes
```

### Website

Add your demo URL if deployed (e.g., GitHub Pages for documentation)

### Social Preview Image

Create a social preview image (1280x640 pixels) showing:

- Repository name
- Key visual (architecture diagram)
- Tagline: "Admin Always Accessible During Maintenance"

Upload at: Settings → Social Preview

## README Enhancements

### Badges to Consider Adding

```markdown
[![Stars](https://img.shields.io/github/stars/christianpetri/kubernetes-maintenance-mode?style=social)](https://github.com/christianpetri/kubernetes-maintenance-mode)
[![Forks](https://img.shields.io/github/forks/christianpetri/kubernetes-maintenance-mode?style=social)](https://github.com/christianpetri/kubernetes-maintenance-mode/fork)
[![Contributors](https://img.shields.io/github/contributors/christianpetri/kubernetes-maintenance-mode)](https://github.com/christianpetri/kubernetes-maintenance-mode/graphs/contributors)
```

### Quick Links Section

Add to top of README (after badges):

```markdown
[Architecture](#architecture) • [Quick Start](#quick-start) • [Demo Script](#demo-script) • [Troubleshooting](#troubleshooting)
```

## GitHub Actions (Optional)

Consider adding CI/CD workflows:

### .github/workflows/lint.yml

```yaml
name: Lint

on: [push, pull_request]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install ruff mypy
      - run: ruff check .
      - run: mypy app.py
```

### .github/workflows/docker-build.yml

```yaml
name: Docker Build

on: [push, pull_request]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - run: docker build -t sample-app:test .
```

## GitHub Pages (Optional)

Host documentation at `https://christianpetri.github.io/kubernetes-maintenance-mode/`:

1. Create `docs/index.html` or use Jekyll
2. Settings → Pages → Source: `main` branch, `/docs` folder
3. Add enhanced documentation with interactive examples

## License File

Add `LICENSE` file if not present. Recommended: Apache 2.0 (matches badge in README)

## GitHub Releases

When you reach milestones, create releases:

```text
v1.0.0 - Initial Kubernetes/Minikube implementation
v1.1.0 - Added runme.ps1 automation script
v1.2.0 - Migrated to EndpointSlice API
```

## Community Files

Consider adding:

- `.github/ISSUE_TEMPLATE/` - Issue templates
- `.github/PULL_REQUEST_TEMPLATE.md` - PR template
- `CODE_OF_CONDUCT.md` - Community guidelines
- `SECURITY.md` - Security policy

## Star History

After gaining traction, add star history badge:

```markdown
[![Star History](https://api.star-history.com/svg?repos=christianpetri/kubernetes-maintenance-mode&type=Date)](https://star-history.com/#christianpetri/kubernetes-maintenance-mode)
```

Delete this file once you've applied the recommendations.
