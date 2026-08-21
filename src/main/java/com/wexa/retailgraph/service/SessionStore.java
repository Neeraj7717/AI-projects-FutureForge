package com.wexa.retailgraph.service;

import org.springframework.stereotype.Component;

import java.security.SecureRandom;
import java.time.Instant;
import java.util.Base64;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * In-memory session store for the single demo login. There's exactly one fixed account (see
 * AuthProperties), so a real user/session database would be pure overhead here - a token ->
 * expiry map is the whole job. Sessions are lost on restart, which is fine for a demo: the
 * cookie just prompts a fresh login next time, nothing is silently broken.
 */
@Component
public class SessionStore {

    private static final long SESSION_TTL_SECONDS = 8 * 60 * 60; // 8 hours

    private final Map<String, Instant> sessions = new ConcurrentHashMap<>();
    private final SecureRandom random = new SecureRandom();

    public String createSession() {
        byte[] bytes = new byte[32];
        random.nextBytes(bytes);
        String token = Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
        sessions.put(token, Instant.now().plusSeconds(SESSION_TTL_SECONDS));
        return token;
    }

    public boolean isValid(String token) {
        if (token == null) {
            return false;
        }
        Instant expiry = sessions.get(token);
        if (expiry == null) {
            return false;
        }
        if (Instant.now().isAfter(expiry)) {
            sessions.remove(token);
            return false;
        }
        return true;
    }

    public void invalidate(String token) {
        if (token != null) {
            sessions.remove(token);
        }
    }
}
