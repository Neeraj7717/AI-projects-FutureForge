package com.wexa.retailgraph.config;

import org.neo4j.driver.AuthTokens;
import org.neo4j.driver.Config;
import org.neo4j.driver.Driver;
import org.neo4j.driver.GraphDatabase;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * Wires the official Neo4j Bolt driver against CognoDB. Credentials are read purely from
 * environment-backed properties (see application.yml) - never hardcoded, never committed.
 *
 * The driver is created eagerly but connectivity is NOT verified here on purpose: CognoDB
 * being briefly unreachable must not prevent the app from starting and serving the UI with a
 * friendly "database unavailable" state (see GlobalExceptionHandler / HealthController).
 */
@Configuration
@EnableConfigurationProperties(CognoDbProperties.class)
public class Neo4jConfig {

    @Bean(destroyMethod = "close")
    public Driver neo4jDriver(CognoDbProperties props,
                               @Value("${cognodb.uri}") String uri) {
        Config driverConfig = Config.builder()
                .withConnectionTimeout(props.getConnectionTimeoutSeconds(), java.util.concurrent.TimeUnit.SECONDS)
                // Default is 30s: too slow for "graceful error handling" - fail fast so the
                // frontend's DB-unreachable banner shows up in seconds, not half a minute.
                .withMaxTransactionRetryTime(props.getMaxRetryTimeSeconds(), java.util.concurrent.TimeUnit.SECONDS)
                .withMaxConnectionPoolSize(20)
                .build();

        return GraphDatabase.driver(
                uri,
                AuthTokens.basic(props.getUsername(), props.getPassword()),
                driverConfig
        );
    }
}
