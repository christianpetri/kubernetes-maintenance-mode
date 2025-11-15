# Standalone Tomcat Demo

This Maven WAR showcases a simple maintenance-mode filter that serves 503 for user paths but allows `/admin/*`.

## Build and Run

```bash
mvn -q -f java-tomcat-demo/pom.xml clean package
# Deploy the generated WAR to Tomcat (copy to webapps/ or use your IDE)
```

## Enable Maintenance

```bash
# On the Tomcat host/container
touch /tmp/maint.on
```

## Test

```bash
curl -i http://localhost:8080/api/status    # → 200 normally, 503 when maintenance flag exists
curl -i http://localhost:8080/admin/status  # → 200 always (filter bypasses /admin)
```

## Files

- `src/main/java/com/example/filter/MaintenanceFilter.java`
- `src/main/java/com/example/servlet/StatusServlet.java`
- `src/main/java/com/example/servlet/AdminStatusServlet.java`
- `src/main/webapp/WEB-INF/web.xml`
- `src/main/webapp/maintenance.html` (neutral wording)
