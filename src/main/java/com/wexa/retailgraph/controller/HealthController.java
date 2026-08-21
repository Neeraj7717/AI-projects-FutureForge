package com.wexa.retailgraph.controller;

import com.wexa.retailgraph.dto.HealthStatus;
import com.wexa.retailgraph.service.GraphQueryExecutor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/**
 * A trivial round-trip query to CognoDB. If the driver can't reach the instance,
 * GraphQueryExecutor throws DatabaseUnavailableException and GlobalExceptionHandler turns it
 * into a 503 - the frontend polls this to decide whether to show its "database unreachable" banner.
 */
@RestController
public class HealthController {

    private final GraphQueryExecutor executor;

    public HealthController(GraphQueryExecutor executor) {
        this.executor = executor;
    }

    @GetMapping("/api/health")
    public HealthStatus health() {
        executor.read(tx -> tx.run("RETURN 1 AS ok", Map.of()).single());
        return new HealthStatus("UP", "Connected to CognoDB");
    }
}
