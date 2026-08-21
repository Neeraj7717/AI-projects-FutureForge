package com.wexa.retailgraph.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

/** Binds the {@code app.auth.*} properties (env-var backed, see application.yml) - the demo
 *  login credentials, same "never hardcoded" pattern as CognoDbProperties. */
@ConfigurationProperties(prefix = "app.auth")
public class AuthProperties {

    private String username = "admin";
    private String password = "admin@123";

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
}
