package com.wexa.retailgraph.seed;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.wexa.retailgraph.service.GraphQueryExecutor;
import org.neo4j.driver.exceptions.Neo4jException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.boot.SpringApplication;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.core.io.ClassPathResource;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;

import java.io.InputStream;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * Loads src/main/resources/seed/seed-data.json into CognoDB. This is the "script included in
 * the repo" required by the assignment - it does NOT run on every app boot; it only runs when
 * the app is launched with the --seed argument, e.g.:
 *
 *   mvn spring-boot:run -Dspring-boot.run.arguments=--seed
 *   java -jar target/retailgraph.jar --seed
 *
 * Every write uses MERGE keyed on a stable id, so re-running the seed is safe and idempotent.
 * Add --reset to wipe the entire database first (e.g. when switching domains on an instance
 * that already has different data in it): --seed --reset.
 *
 * The last step derives the CO_PURCHASED_WITH graph from the actual order data - it is not
 * hand-authored - which is what all the multi-hop recommendation queries traverse.
 */
@Component
@Order(1)
public class DataSeeder implements ApplicationRunner {

    private static final Logger log = LoggerFactory.getLogger(DataSeeder.class);

    private final GraphQueryExecutor executor;
    private final ObjectMapper objectMapper;
    private final ConfigurableApplicationContext context;

    public DataSeeder(GraphQueryExecutor executor, ObjectMapper objectMapper, ConfigurableApplicationContext context) {
        this.executor = executor;
        this.objectMapper = objectMapper;
        this.context = context;
    }

    @Override
    public void run(ApplicationArguments args) throws Exception {
        if (!args.containsOption("seed")) {
            return;
        }

        java.util.concurrent.atomic.AtomicInteger exitCode = new java.util.concurrent.atomic.AtomicInteger(0);
        try {
            if (args.containsOption("reset")) {
                log.info("Resetting CognoDB - deleting all existing nodes and relationships ...");
                executor.write(tx -> tx.run("MATCH (n) DETACH DELETE n").consume());
            }
            seed();
        } catch (Exception e) {
            log.error("Seeding failed", e);
            exitCode.set(1);
        }
        // This runner is used as a one-shot CLI script (scripts/seed.sh), not as part of normal
        // app boot - it must exit rather than leaving the embedded web server running forever.
        System.exit(SpringApplication.exit(context, exitCode::get));
    }

    private void seed() throws Exception {
        log.info("Seeding CognoDB from seed/seed-data.json ...");
        JsonNode root;
        try (InputStream in = new ClassPathResource("seed/seed-data.json").getInputStream()) {
            root = objectMapper.readTree(in);
        }

        ensureConstraints();

        List<Map<String, Object>> categories = toList(root.get("categories"));
        List<Map<String, Object>> brands = toList(root.get("brands"));
        List<Map<String, Object>> products = toList(root.get("products"));
        List<Map<String, Object>> customers = toList(root.get("customers"));
        List<Map<String, Object>> orders = toList(root.get("orders"));
        List<Map<String, Object>> reviews = toList(root.get("reviews"));

        executor.write(tx -> tx.run("""
                UNWIND $rows AS row
                MERGE (c:Category {id: row.id})
                SET c.name = row.name
                """, Map.of("rows", categories)).consume());
        log.info("  {} categories merged", categories.size());

        executor.write(tx -> tx.run("""
                UNWIND $rows AS row
                MERGE (b:Brand {id: row.id})
                SET b.name = row.name
                """, Map.of("rows", brands)).consume());
        log.info("  {} brands merged", brands.size());

        executor.write(tx -> tx.run("""
                UNWIND $rows AS row
                MERGE (p:Product {id: row.id})
                SET p.name = row.name, p.description = row.description, p.price = row.price, p.sku = row.sku
                WITH p, row
                MATCH (c:Category {id: row.categoryId})
                MERGE (p)-[:IN_CATEGORY]->(c)
                WITH p, row
                MATCH (b:Brand {id: row.brandId})
                MERGE (p)-[:BY_BRAND]->(b)
                """, Map.of("rows", products)).consume());
        log.info("  {} products merged", products.size());

        executor.write(tx -> tx.run("""
                UNWIND $rows AS row
                MERGE (c:Customer {id: row.id})
                SET c.name = row.name, c.email = row.email, c.joinDate = row.joinDate
                """, Map.of("rows", customers)).consume());
        log.info("  {} customers merged", customers.size());

        executor.write(tx -> tx.run("""
                UNWIND $rows AS row
                MATCH (cust:Customer {id: row.customerId})
                MERGE (o:Order {id: row.id})
                SET o.orderDate = row.orderDate
                MERGE (cust)-[:PLACED]->(o)
                WITH o, row
                UNWIND row.productIds AS productId
                MATCH (p:Product {id: productId})
                MERGE (o)-[:CONTAINS]->(p)
                """, Map.of("rows", orders)).consume());
        log.info("  {} orders merged", orders.size());

        executor.write(tx -> tx.run("""
                UNWIND $rows AS row
                MATCH (c:Customer {id: row.customerId}), (p:Product {id: row.productId})
                MERGE (c)-[r:REVIEWED]->(p)
                SET r.rating = row.rating, r.comment = row.comment, r.date = row.date
                """, Map.of("rows", reviews)).consume());
        log.info("  {} reviews merged", reviews.size());

        // Derive the co-purchase graph from the actual order data (not hand-authored) - every
        // multi-hop recommendation query in RecommendationService traverses this edge.
        long coPurchaseEdges = executor.write(tx -> tx.run("""
                MATCH (o:Order)-[:CONTAINS]->(p1:Product), (o)-[:CONTAINS]->(p2:Product)
                WHERE p1.id < p2.id
                WITH p1, p2, count(DISTINCT o) AS strength
                MERGE (p1)-[r:CO_PURCHASED_WITH]->(p2)
                SET r.strength = strength
                RETURN count(*) AS edges
                """).single().get("edges").asLong());
        log.info("  {} co-purchase edges derived from order data", coPurchaseEdges);

        log.info("Seeding complete.");
    }

    /** Constraints are a performance nicety, not a correctness requirement - if CognoDB rejects
     *  the syntax we log and move on rather than failing the whole seed run. */
    private void ensureConstraints() {
        String[] constraints = {
                "CREATE CONSTRAINT category_id IF NOT EXISTS FOR (c:Category) REQUIRE c.id IS UNIQUE",
                "CREATE CONSTRAINT brand_id IF NOT EXISTS FOR (b:Brand) REQUIRE b.id IS UNIQUE",
                "CREATE CONSTRAINT product_id IF NOT EXISTS FOR (p:Product) REQUIRE p.id IS UNIQUE",
                "CREATE CONSTRAINT customer_id IF NOT EXISTS FOR (c:Customer) REQUIRE c.id IS UNIQUE",
                "CREATE CONSTRAINT order_id IF NOT EXISTS FOR (o:Order) REQUIRE o.id IS UNIQUE"
        };
        for (String stmt : constraints) {
            try {
                executor.write(tx -> tx.run(stmt).consume());
            } catch (Neo4jException e) {
                log.warn("Skipping constraint (not supported or already present): {}", e.getMessage());
            }
        }
    }

    private List<Map<String, Object>> toList(JsonNode arrayNode) {
        List<Map<String, Object>> out = new ArrayList<>();
        if (arrayNode == null) {
            return out;
        }
        for (JsonNode node : arrayNode) {
            out.add(objectMapper.convertValue(node, new com.fasterxml.jackson.core.type.TypeReference<Map<String, Object>>() {}));
        }
        return out;
    }
}
