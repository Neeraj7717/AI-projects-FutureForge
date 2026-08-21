package com.wexa.retailgraph.config;

import com.wexa.retailgraph.exception.UnauthenticatedException;
import com.wexa.retailgraph.service.SessionStore;
import jakarta.servlet.http.Cookie;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.web.servlet.HandlerInterceptor;

/**
 * Guards the API (everything except /api/auth/** and /api/health, see WebConfig) behind the
 * SESSION cookie issued by AuthController on login. This is what actually protects the app -
 * the login page itself is just a form; without this, anyone could skip it and hit the API
 * endpoints directly since a client-side-only gate proves nothing.
 */
public class AuthInterceptor implements HandlerInterceptor {

    public static final String COOKIE_NAME = "SESSION";

    private final SessionStore sessionStore;

    public AuthInterceptor(SessionStore sessionStore) {
        this.sessionStore = sessionStore;
    }

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) {
        if (sessionStore.isValid(extractToken(request))) {
            return true;
        }
        throw new UnauthenticatedException("Please log in to continue.");
    }

    private String extractToken(HttpServletRequest request) {
        Cookie[] cookies = request.getCookies();
        if (cookies == null) {
            return null;
        }
        for (Cookie cookie : cookies) {
            if (COOKIE_NAME.equals(cookie.getName())) {
                return cookie.getValue();
            }
        }
        return null;
    }
}
