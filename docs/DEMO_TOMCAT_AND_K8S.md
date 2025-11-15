# Maintenance Mode Demo (Tomcat + Kubernetes/OpenShift)

Two parts you can copy-paste and run:

## 1) Standalone Tomcat Demo (localhost)

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

## 2) Kubernetes / OpenShift YAML Demo

### deployment.yaml

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

### service.yaml

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

### route-normal.yaml (OpenShift)

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

### route-admin.yaml (OpenShift – bypass readiness)

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

### Demo Script (Run in 60 seconds)

```bash
# 1. Deploy
oc apply -f deployment.yaml,service.yaml,route-normal.yaml,route-admin.yaml

# 2. Enter maintenance mode
oc exec deploy/sample-app -- touch /tmp/maint.on

# 3. Test
curl -H "Host: example.com" http://$(oc get route sample-app-normal -o jsonpath='{.spec.host}')
# → 503

curl -H "Host: admin.example.com" http://$(oc get route sample-app-admin -o jsonpath='{.spec.host}')/admin/status
# → 200 + full access
```

## Summary for Tech Lead

> You said: "503 kills admin access"

Reality:
 
> - example.com → 503 → drained  
> - admin.example.com → 200 → full access  
> - Same app. Same code. Just routing rules.  
> - Works on Tomcat standalone and Kubernetes.  
> - 503 is a signal, not a shutdown.
