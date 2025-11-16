# GitHub Copilot Instructions - Kubernetes Maintenance Mode Demo

## Project Overview

Flask application demonstrating Kubernetes maintenance mode using `@app.before_request` decorator
with guaranteed admin access during maintenance windows.

## Key Architecture Decisions

1. **Flask Pattern**: Uses `@app.before_request` decorator (industry standard)
2. **Dual Deployments**: Separate user/admin pods with different readiness logic
3. **Graceful Degradation**: Readiness probes remove pods from load balancer (no restarts)

## Development Guidelines

- **Code Style**: Follow Flask best practices, use Ruff for linting
- **Testing**: Test with Minikube, verify both user and admin pod behaviors
- **Documentation**: Keep README concise, update MAINTENANCE_DEMO.md for details

## Current State

✅ Complete production-ready implementation
✅ Refactored to Flask best practice pattern
✅ All documentation updated
✅ Docker and Kubernetes manifests ready
