FROM tomcat:10.1-jdk17-temurin

# Copy built WAR as ROOT to serve at '/'
COPY target/maintenance-demo.war /usr/local/tomcat/webapps/ROOT.war

# Expose port
EXPOSE 8080

# Default command (provided by base image)