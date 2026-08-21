package com.wexa.retailgraph.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * Binds the {@code cognodb.*} properties (backed by env vars, see application.yml)
 * so the Bolt URI and credentials never appear as literals in code.
 */
@ConfigurationProperties(prefix = "cognodb")
public class CognoDbProperties {

    private String uri;
    private String username;
    private String password;
    private String database = "neo4j";
    private int connectionTimeoutSeconds = 10;
    private int maxRetryTimeSeconds = 5;

    public String getUri() {
        return uri;
    }

    public void setUri(String uri) {
        this.uri = uri;
    }

    public String getUsername() {
        return username;
    }

    public void setUsername(String username) {
        this.username = username;
    }

    public String getPassword() {
        return password;
    }

    public void setPassword(String password) {
        this.password = password;
    }

    public String getDatabase() {
        return database;
    }

    public void setDatabase(String database) {
        this.database = database;
    }

    public int getConnectionTimeoutSeconds() {
        return connectionTimeoutSeconds;
    }

    public void setConnectionTimeoutSeconds(int connectionTimeoutSeconds) {
        this.connectionTimeoutSeconds = connectionTimeoutSeconds;
    }

    public int getMaxRetryTimeSeconds() {
        return maxRetryTimeSeconds;
    }

    public void setMaxRetryTimeSeconds(int maxRetryTimeSeconds) {
        this.maxRetryTimeSeconds = maxRetryTimeSeconds;
    }
}
