# Troubleshooting Guide

Common issues and solutions for the Kubernetes Maintenance Mode demo.

## Table of Contents

- [Pod Issues](#pod-issues)
- [Service Tunnel Issues](#service-tunnel-issues)
- [Minikube Issues](#minikube-issues)
- [Ingress Issues](#ingress-issues)
- [Redis Issues](#redis-issues)

## Pod Issues

### Pods Not Becoming NotReady During Maintenance

**Check:**

```powershell
# 1. Is maintenance mode enabled?
kubectl exec -n sample-app deployment/redis -- redis-cli GET maintenance_mode

# 2. Is Redis working?
kubectl logs -n sample-app deployment/sample-app-user | Select-String "redis"

# 3. Test readiness probe manually (use tunnel window URL)
# Example: http://127.0.0.1:52876/ready
# Should return: {"status": "not_ready", "reason": "maintenance_mode"}
```

**Solution:**

- Wait 10-15 seconds for readiness probe interval
- Check Redis is deployed and accessible
- Verify environment variable: `REDIS_ENABLED=true`

### Pods Not Ready After Maintenance Toggle

```powershell
# Check pod status
kubectl get pods -n sample-app

# Check pod logs
kubectl logs -n sample-app deployment/sample-app-user
kubectl logs -n sample-app deployment/sample-app-admin

# Verify ConfigMap
kubectl get configmap sample-app-config -n sample-app -o yaml
```

**Solution:**

```powershell
# Restart deployments
kubectl rollout restart deployment/sample-app-user -n sample-app
kubectl rollout restart deployment/sample-app-admin -n sample-app
```

## Service Tunnel Issues

### Cannot Access Application Through Tunnel

**Check:**

```powershell
# Verify service tunnels are running
# Should see two PowerShell windows from runme.ps1 setup
```

**Solution:**

```powershell
# Close tunnel windows and restart
.\scripts\teardown.ps1 -KeepMinikube -Force
.\scripts\runme.ps1 setup
```

### Why Does kubectl port-forward Bypass the Drain?

**Answer:** kubectl port-forward is a debugging tool.

Manual kubectl port-forward commands bypass Service routing and readiness checks.
They connect directly to pods.

**To see the drain working:**

- Use service tunnels: `runme.ps1 setup` (respects Service endpoints)
- Use Ingress: `http://sample-app.local` (requires tunnel)
- Check endpoints: `kubectl get endpoints -n sample-app sample-app-user`
  - Should be EMPTY during maintenance
- Check pod status: `kubectl get pods -n sample-app`
  - User pods should be 0/1 NotReady

The drain IS working - service tunnels respect readiness checks.

## Minikube Issues

### Minikube Not Starting

```powershell
# Check Minikube status
minikube status

# Delete and recreate cluster
minikube delete
minikube start --cpus=4 --memory=8192 --driver=docker
```

### Image Not Found in Minikube

```powershell
# Rebuild image in Minikube Docker environment
minikube docker-env | Invoke-Expression
docker build -t sample-app:latest .

# Verify image exists
docker images | Select-String sample-app
```

### General Minikube Reset

```powershell
# Complete reset
.\scripts\teardown.ps1 -DeepClean
.\scripts\runme.ps1 setup
```

## Ingress Issues

### Cannot Access via sample-app.local

**Check:**

```powershell
# 1. Is Ingress enabled?
minikube addons list | Select-String ingress

# 2. Is Ingress deployed?
kubectl get ingress -n sample-app

# 3. Is tunnel running?
# Must run: minikube tunnel (in Admin PowerShell)

# 4. Is hosts file updated?
Get-Content C:\Windows\System32\drivers\etc\hosts | Select-String sample-app
```

**Solution:**

```powershell
# Enable Ingress
minikube addons enable ingress

# Deploy Ingress
kubectl apply -f kubernetes/ingress.yaml

# Update hosts file (as Administrator)
$ip = minikube ip
Add-Content C:\Windows\System32\drivers\etc\hosts "$ip sample-app.local"
Add-Content C:\Windows\System32\drivers\etc\hosts "$ip admin.sample-app.local"

# Start tunnel
minikube tunnel  # Keep running
```

### Custom 503 Page Not Showing

**Check:**

```powershell
# 1. Is maintenance page pod running?
kubectl get pods -n sample-app -l app=maintenance-page

# 2. Is Ingress configured correctly?
kubectl get ingress -n sample-app sample-app-ingress -o yaml | Select-String custom-http-errors

# 3. Test maintenance page directly
kubectl port-forward -n sample-app svc/maintenance-page 8889:80
curl http://localhost:8889
```

**Solution:**

```powershell
# Deploy/update maintenance page
kubectl apply -f kubernetes/maintenance-page-deployment.yaml

# Update Ingress
kubectl apply -f kubernetes/ingress.yaml

# Restart maintenance page pod
kubectl rollout restart deployment/maintenance-page -n sample-app
```

## Redis Issues

### Redis Connection Failed

**Check:**

```powershell
# Verify Redis is running
kubectl get pods -n sample-app -l app=redis

# Check Redis logs
kubectl logs -n sample-app deployment/redis

# Test Redis connection
kubectl exec -n sample-app deployment/redis -- redis-cli ping
```

**Solution:**

```powershell
# Restart Redis
kubectl rollout restart deployment/redis -n sample-app

# Wait for Redis to be ready, then restart app pods
Start-Sleep -Seconds 10
kubectl rollout restart deployment/sample-app-user -n sample-app
kubectl rollout restart deployment/sample-app-admin -n sample-app
```

### Admin Panel Button Not Working

**Problem:** Button returns `{"error":"Redis not available"}`

**Solution:**

```powershell
# Restart Redis and app deployments
kubectl rollout restart deployment/redis -n sample-app
Start-Sleep -Seconds 10
kubectl rollout restart deployment/sample-app-user -n sample-app
kubectl rollout restart deployment/sample-app-admin -n sample-app
```

## Quick Diagnostics

### Check All Components

```powershell
# Pod status
kubectl get pods -n sample-app

# Service endpoints
kubectl get endpoints -n sample-app

# ConfigMap
kubectl get configmap sample-app-config -n sample-app -o yaml

# Redis state
kubectl exec -n sample-app deployment/redis -- redis-cli GET maintenance_mode

# Full status
.\scripts\runme.ps1 status
```

### Clean Slate

```powershell
# Nuclear option - delete everything and start fresh
.\scripts\teardown.ps1 -DeepClean -Force
.\scripts\runme.ps1 setup
```

## Getting Help

If you encounter issues not covered here:

1. Check pod logs: `kubectl logs -n sample-app <pod-name>`
2. Check events: `kubectl get events -n sample-app`
3. Verify configuration: `kubectl get all -n sample-app`
4. Review [DESIGN.md](../DESIGN.md) for architecture details
5. Check [GitHub Issues](https://github.com/christianpetri/openshift-maintenance-demo/issues)
