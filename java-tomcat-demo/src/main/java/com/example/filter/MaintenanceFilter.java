package com.example.filter;

import jakarta.servlet.*;
import jakarta.servlet.http.HttpServletRequest;
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
        HttpServletRequest request = (HttpServletRequest) req;
        String uri = request.getRequestURI();

        if (new File(MAINTENANCE_FLAG).exists() && !uri.startsWith(ADMIN_PATH)) {
            response.setStatus(503);
            response.setContentType("application/json");
            response.setHeader("Retry-After", "120");
            response.getWriter().write("{\"error\": \"Service in maintenance mode\"}");
            return;
        }
        chain.doFilter(req, res);
    }
}
