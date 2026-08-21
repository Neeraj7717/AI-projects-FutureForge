package com.wexa.retailgraph.service;

import com.wexa.retailgraph.config.CognoDbProperties;
import com.wexa.retailgraph.exception.DatabaseUnavailableException;
import org.neo4j.driver.Driver;
import org.neo4j.driver.Session;
import org.neo4j.driver.SessionConfig;
import org.neo4j.driver.TransactionContext;
import org.neo4j.driver.exceptions.Neo4jException;
import org.springframework.stereotype.Component;

import java.util.function.Function;

/**
 * Single choke point for every Cypher statement in the app. All domain services go through
 * {@link #read} / {@link #write} instead of touching the driver directly, so:
 *  - every query runs inside a proper managed transaction (executeRead/executeWrite, with the
 *    driver's built-in retry on transient failures),
 *  - a CognoDB outage surfaces uniformly as {@link DatabaseUnavailableException} everywhere,
 *    which GlobalExceptionHandler turns into a 503 the frontend can show a friendly state for.
 */
@Component
public class GraphQueryExecutor {

    private final Driver driver;
    private final String database;

    public GraphQueryExecutor(Driver driver, CognoDbProperties props) {
        this.driver = driver;
        this.database = props.getDatabase();
    }

    public <T> T read(Function<TransactionContext, T> work) {
        try (Session session = driver.session(SessionConfig.forDatabase(database))) {
            return session.executeRead(work::apply);
        } catch (Neo4jException e) {
            throw new DatabaseUnavailableException("CognoDB read failed: " + e.getMessage(), e);
        }
    }

    public <T> T write(Function<TransactionContext, T> work) {
        try (Session session = driver.session(SessionConfig.forDatabase(database))) {
            return session.executeWrite(work::apply);
        } catch (Neo4jException e) {
            throw new DatabaseUnavailableException("CognoDB write failed: " + e.getMessage(), e);
        }
    }
}
