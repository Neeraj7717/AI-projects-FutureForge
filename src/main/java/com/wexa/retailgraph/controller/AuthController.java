package com.wexa.retailgraph.controller;

import com.wexa.retailgraph.config.AuthInterceptor;
import com.wexa.retailgraph.config.AuthProperties;
import com.wexa.retailgraph.dto.AuthStatus;
import com.wexa.retailgraph.dto.LoginRequest;
import com.wexa.retailgraph.service.SessionStore;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseCookie;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Single fixed demo account (see AuthProperties) - no signup, no password reset, no user table.
 * Credentials are compared with MessageDigest.isEqual (constant-time) rather than String.equals
 * purely as good practice; the real protection is that the session cookie is HttpOnly (so page
 * JS can never read or forge it) and validated server-side on every request by AuthInterceptor.
 */
@RestController
@RequestMapping("/api/auth")
public class AuthController {

    private final AuthProperties authProperties;
    private final SessionStore sessionStore;

    public AuthController(AuthProperties authProperties, SessionStore sessionStore) {
        this.authProperties = authProperties;
        this.sessionStore = sessionStore;
    }

    @PostMapping("/login")
    public ResponseEntity<Map<String, Object>> login(@RequestBody LoginRequest request) {
        if (!isValid(request)) {
            Map<String, Object> body = new LinkedHashMap<>();
            body.put("error", "INVALID_CREDENTIALS");
            body.put("message", "Incorrect username or password.");
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body(body);
        }

        String token = sessionStore.createSession();
        return ResponseEntity.ok()
                .header(HttpHeaders.SET_COOKIE, sessionCookie(token, 8 * 60 * 60).toString())
                .body(Map.of("authenticated", true));
    }

    @PostMapping("/logout")
    public ResponseEntity<Void> logout(@CookieValue(name = AuthInterceptor.COOKIE_NAME, required = false) String token) {
        sessionStore.invalidate(token);
        return ResponseEntity.ok()
                .header(HttpHeaders.SET_COOKIE, sessionCookie("", 0).toString())
                .build();
    }

    @GetMapping("/status")
    public AuthStatus status(@CookieValue(name = AuthInterceptor.COOKIE_NAME, required = false) String token) {
        return new AuthStatus(sessionStore.isValid(token));
    }

    private boolean isValid(LoginRequest request) {
        if (request == null || request.username() == null || request.password() == null) {
            return false;
        }
        return constantTimeEquals(request.username(), authProperties.getUsername())
                && constantTimeEquals(request.password(), authProperties.getPassword());
    }

    private boolean constantTimeEquals(String a, String b) {
        return MessageDigest.isEqual(a.getBytes(StandardCharsets.UTF_8), b.getBytes(StandardCharsets.UTF_8));
    }

    private ResponseCookie sessionCookie(String value, int maxAgeSeconds) {
        return ResponseCookie.from(AuthInterceptor.COOKIE_NAME, value)
                .httpOnly(true)
                .sameSite("Lax")
                .path("/")
                .maxAge(maxAgeSeconds)
                .build();
    }
}
