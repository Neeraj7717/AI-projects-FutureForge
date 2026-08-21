package com.wexa.retailgraph.service;

import com.wexa.retailgraph.dto.DashboardStats;
import org.neo4j.driver.Record;
import org.neo4j.driver.Result;
import org.springframework.stereotype.Service;

import java.util.Map;

@Service
public class StatsService {

    private final GraphQueryExecutor executor;

    public StatsService(GraphQueryExecutor executor) {
        this.executor = executor;
    }

    private static final String STATS_QUERY = """
            MATCH (c:Customer) WITH count(c) AS customers
            MATCH (p:Product) WITH customers, count(p) AS products
            MATCH (o:Order) WITH customers, products, count(o) AS orders
            MATCH (:Customer)-[rev:REVIEWED]->(:Product) WITH customers, products, orders, count(rev) AS reviews
            MATCH ()-[cp:CO_PURCHASED_WITH]->()
            RETURN customers, products, orders, reviews, count(cp) AS coPurchaseEdges
            """;

    public DashboardStats getDashboardStats() {
        return executor.read(tx -> {
            Result result = tx.run(STATS_QUERY, Map.of());
            if (!result.hasNext()) {
                return new DashboardStats(0, 0, 0, 0, 0);
            }
            Record r = result.next();
            return new DashboardStats(
                    r.get("customers").asLong(),
                    r.get("products").asLong(),
                    r.get("orders").asLong(),
                    r.get("reviews").asLong(),
                    r.get("coPurchaseEdges").asLong()
            );
        });
    }
}
