# Maintenance Mode Demo (Tomcat + OpenShift)

A concise, copy-paste-ready guide to demonstrate application maintenance mode
with proper 503 behavior for users while keeping admin access available for
operations.

## Contents

- Overview
- Tomcat Standalone Demo
- OpenShift Manifests
- One-Minute Demo Script
- Lessons Learned

---

## Overview

- User requests receive HTTP 503 during maintenance (with `Retry-After`).
- Liveness stays 200 (don’t restart pods just because we’re in maintenance).
- Admin path remains available, bypassing readiness draining.
- Maintenance state is shared across workers/pods via a simple flag.

---

## Tomcat Standalone Demo (localhost)

### MaintenanceFilter.java

```java
// src/main/java/com/example/filter/MaintenanceFilter.java
package com.example.filter;

import jakarta.servlet.*;
import jakarta.servlet.http.HttpServletResponse;
import java.io.File;
import java.io.IOException;

public class MaintenanceFilter implements Filter {
    private static final String MAINTENANCE_FLAG = "/tmp/maint.on";
    private static final String ADMIN_PATH = "/admin";

    @Override
    public void doFilter(ServletRequest req, ServletResponse res, FilterChain chain)
            throws IOException, ServletException {
        HttpServletResponse response = (HttpServletResponse) res;
        String uri = ((jakarta.servlet.http.HttpServletRequest) req).getRequestURI();

        if (new File(MAINTENANCE_FLAG).exists() && !uri.startsWith(ADMIN_PATH)) {
            response.setStatus(503);
            response.setHeader("Retry-After", "120");
            response.setContentType("application/json");
            response.getWriter().write("{\"error\": \"Service in maintenance mode\"}");
            return;
        }
        chain.doFilter(req, res);
    }
}
```

### web.xml (add to WEB-INF)

```xml
<filter>
    <filter-name>MaintenanceFilter</filter-name>
    <filter-class>com.example.filter.MaintenanceFilter</filter-class>
</filter>
<filter-mapping>
    <filter-name>MaintenanceFilter</filter-name>
    <url-pattern>/*</url-pattern>
</filter-mapping>
```

### maintenance.html (static fallback)

```html
<!-- src/main/webapp/maintenance.html -->
<!DOCTYPE html>
<html>
<head><title>Maintenance</title></head>
<body style="font-family: sans-serif; text-align: center; margin-top: 100px;">
  <h1>The application is in maintenance mode</h1>
  <p>Please come back later.</p>
</body>
</html>
```

### How to Run (Terminal)

```bash
mvn clean package
# Start Tomcat, then:
touch /tmp/maint.on
curl http://localhost:8080/api/status          # → 503 + JSON
curl http://localhost:8080/admin/status        # → 200 + normal response
```

---

## OpenShift Manifests

### openshift/deployment.yaml

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: sample-app
spec:
  replicas: 2
  selector:
    matchLabels:
      app: sample-app
  template:
    metadata:
      labels:
        app: sample-app
    spec:
      containers:
      - name: app
        image: your-registry/sample-app:latest
        ports:
        - containerPort: 8080
        readinessProbe:
          httpGet:
            path: /system/status
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
        livenessProbe:
          httpGet:
            path: /ping
            port: 8080
          initialDelaySeconds: 120
```

### openshift/service.yaml

```yaml
apiVersion: v1
kind: Service
metadata:
  name: sample-app-service
spec:
  selector:
    app: sample-app
  ports:
    - port: 80
      targetPort: 8080
```

### openshift/route-normal.yaml

```yaml
apiVersion: route.openshift.io/v1
kind: Route
metadata:
  name: sample-app-normal
spec:
  host: example.com
  to:
    kind: Service
    name: sample-app-service
  port:
    targetPort: 8080
  # Honors readiness → 503 = drained
```

### openshift/route-admin.yaml (bypass readiness)

```yaml
apiVersion: route.openshift.io/v1
kind: Route
metadata:
  name: sample-app-admin
spec:
  host: admin.example.com
  to:
    kind: Service
    name: sample-app-service
  port:
    targetPort: 8080
  # Ignores readiness → always reachable
  tls:
    termination: edge
```

---

## One-Minute Demo Script

```bash
# 1. Deploy (from repo root)
oc apply -f openshift/deployment.yaml,openshift/service.yaml,openshift/route-normal.yaml,openshift/route-admin.yaml

# 2. Enter maintenance mode
oc exec deploy/sample-app -- touch /tmp/maint.on

# 3. Test
curl -H "Host: example.com" http://$(oc get route sample-app-normal -o jsonpath='{.spec.host}')
# → 503

curl -H "Host: admin.example.com" http://$(oc get route sample-app-admin -o jsonpath='{.spec.host}')/admin/status
# → 200 + full access
```

---

## Lessons Learned

- Readiness vs user 503: Keep liveness 200, return 503 on user paths during maintenance.
- Admin access: Provide a separate route that bypasses readiness, so ops stays reachable.
- Shared maintenance flag: Use a file or ConfigMap so all pods agree on state.
- Split vs single Service: Split routes keep admin accessible without impacting user draining.
- Headers matter: Include `Retry-After` to communicate expected back-in-service window.

---

## Quick Start (Windows PowerShell)

- Build and run in Docker (default port 8080):

```powershell
.\scripts
unme.ps1 -Mode docker -Build -Start -Port 8080
```

- Enable/disable maintenance in the running container:

```powershell
.\scripts
unme.ps1 -Mode docker -EnableMaintenance
.\scripts
unme.ps1 -Mode docker -DisableMaintenance
```

- Deploy natively to an existing Tomcat (set `TOMCAT_HOME` first):

```powershell
$env:TOMCAT_HOME="C:\\apache-tomcat-10.1.x"
.\scripts
unme.ps1 -Mode native -Build -Start -Port 8080
```

Notes:

- Native maintenance flag lives at `C:\tmp\maint.on`.
- Docker maintenance flag lives at `/tmp/maint.on` inside the container.
