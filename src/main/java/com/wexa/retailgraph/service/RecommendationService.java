package com.wexa.retailgraph.service;

import com.wexa.retailgraph.dto.*;
import com.wexa.retailgraph.exception.NotFoundException;
import org.neo4j.driver.Record;
import org.neo4j.driver.Result;
import org.neo4j.driver.types.Node;
import org.neo4j.driver.types.Path;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Multi-hop recommendation traversals over the precomputed CO_PURCHASED_WITH graph (see
 * DataSeeder - it's derived from real order data at seed time). These are the queries that make
 * the "why a graph database" case: second-degree collaborative filtering ("people who bought
 * what people who bought X bought") and shortest-path product discovery would need a stack of
 * self-joins or a recursive CTE with manual de-duplication in SQL; here they're one Cypher
 * variable-length pattern.
 */
@Service
public class RecommendationService {

    /** Cypher does not allow a parameter inside a variable-length relationship bound
     *  (`*1..$n` is not legal openCypher) - a language limitation, not a free-text field - so we
     *  clamp to a server-controlled constant and splice the literal integer into the query text.
     *  Every real value (ids, limits) stays parameterized. */
    private static final int MAX_HOPS = 4;

    private final GraphQueryExecutor executor;

    public RecommendationService(GraphQueryExecutor executor) {
        this.executor = executor;
    }

    private static final String SEED_INFO_QUERY = """
            MATCH (p:Product {id: $productId})
            OPTIONAL MATCH (p)-[:IN_CATEGORY]->(c:Category)
            RETURN p.name AS name, c.name AS category
            """;

    /**
     * Extended ("second-degree and beyond") recommendations: every product reachable through a
     * chain of co-purchase relationships, with the shortest number of hops from the seed product.
     * hops=1 is exactly "frequently bought together"; hops=2+ is "people who bought what people
     * who bought X bought" - recommendations a direct co-purchase count alone would never surface.
     */
    public RecommendationResult getExtendedRecommendations(String productId, int hops, int limit) {
        int clampedHops = Math.max(1, Math.min(hops, MAX_HOPS));

        Record seed = executor.read(tx -> {
            Result r = tx.run(SEED_INFO_QUERY, Map.of("productId", productId));
            return r.hasNext() ? r.next() : null;
        });
        if (seed == null) {
            throw new NotFoundException("No product found with id '" + productId + "'");
        }

        String cypher = """
                MATCH (seed:Product {id: $productId})
                MATCH recPath = (seed)-[:CO_PURCHASED_WITH*1..%d]-(rec:Product)
                WHERE rec <> seed
                WITH rec, min(length(recPath)) AS hops
                OPTIONAL MATCH (rec)-[:IN_CATEGORY]->(c:Category)
                OPTIONAL MATCH (rec)-[:BY_BRAND]->(b:Brand)
                RETURN rec.id AS productId, rec.name AS productName, c.name AS category,
                       b.name AS brand, rec.price AS price, hops
                ORDER BY hops ASC, productName ASC
                LIMIT $limit
                """.formatted(clampedHops);

        return executor.read(tx -> {
            Result result = tx.run(cypher, Map.of("productId", productId, "limit", limit));
            List<RecommendedProductDto> recs = new ArrayList<>();
            while (result.hasNext()) {
                Record r = result.next();
                recs.add(new RecommendedProductDto(
                        r.get("productId").asString(),
                        r.get("productName").asString(),
                        r.get("category").isNull() ? null : r.get("category").asString(),
                        r.get("brand").isNull() ? null : r.get("brand").asString(),
                        r.get("price").asDouble(),
                        r.get("hops").asLong()
                ));
            }
            return new RecommendationResult(
                    productId, seed.get("name").asString(),
                    seed.get("category").isNull() ? null : seed.get("category").asString(),
                    recs
            );
        });
    }

    private static final String NODE_HOPS_QUERY = """
            MATCH (seed:Product {id: $productId})
            MATCH hopPath = (seed)-[:CO_PURCHASED_WITH*0..%d]-(n:Product)
            WITH n, min(length(hopPath)) AS hops
            RETURN n.id AS id, hops
            """;

    /** Same traversal as {@link #getExtendedRecommendations}, shaped as a node/edge graph for
     *  the interactive visualization on the product page instead of a flat ranked list.
     *  Edges are re-oriented to point away from the seed (lower hop-count -> higher hop-count)
     *  rather than kept in their stored CO_PURCHASED_WITH direction, which is arbitrary (fixed
     *  by product id ordering at seed time, unrelated to distance from whatever product you're
     *  viewing) and made the rendered tree look like it wasn't rooted at the seed at all. */
    public RecommendationGraphDto getRecommendationGraph(String productId, int hops) {
        int clampedHops = Math.max(1, Math.min(hops, MAX_HOPS));

        Record seed = executor.read(tx -> {
            Result r = tx.run(SEED_INFO_QUERY, Map.of("productId", productId));
            return r.hasNext() ? r.next() : null;
        });
        if (seed == null) {
            throw new NotFoundException("No product found with id '" + productId + "'");
        }

        Map<String, Long> hopsById = executor.read(tx -> {
            Result r = tx.run(NODE_HOPS_QUERY.formatted(clampedHops), Map.of("productId", productId));
            Map<String, Long> map = new HashMap<>();
            while (r.hasNext()) {
                Record rec = r.next();
                map.put(rec.get("id").asString(), rec.get("hops").asLong());
            }
            return map;
        });

        String cypher = """
                MATCH treePath = (v:Product {id: $productId})-[:CO_PURCHASED_WITH*1..%d]-(d:Product)
                WITH DISTINCT relationships(treePath) AS rels
                UNWIND rels AS rel
                WITH DISTINCT startNode(rel) AS from, endNode(rel) AS to
                OPTIONAL MATCH (from)-[:IN_CATEGORY]->(fc:Category)
                OPTIONAL MATCH (to)-[:IN_CATEGORY]->(tc:Category)
                RETURN from.id AS fromId, from.name AS fromName, fc.name AS fromCategory,
                       to.id AS toId, to.name AS toName, tc.name AS toCategory
                """.formatted(clampedHops);

        return executor.read(tx -> {
            Result result = tx.run(cypher, Map.of("productId", productId));
            Map<String, GraphNodeDto> nodes = new LinkedHashMap<>();
            List<GraphEdgeDto> edges = new ArrayList<>();

            nodes.put(productId, new GraphNodeDto(productId, seed.get("name").asString(),
                    seed.get("category").isNull() ? "" : seed.get("category").asString(), "SEED_PRODUCT"));

            while (result.hasNext()) {
                Record r = result.next();
                String fromId = r.get("fromId").asString();
                String toId = r.get("toId").asString();
                nodes.putIfAbsent(fromId, new GraphNodeDto(fromId, r.get("fromName").asString(),
                        r.get("fromCategory").isNull() ? "" : r.get("fromCategory").asString(), "PRODUCT"));
                nodes.putIfAbsent(toId, new GraphNodeDto(toId, r.get("toName").asString(),
                        r.get("toCategory").isNull() ? "" : r.get("toCategory").asString(), "PRODUCT"));

                long fromHops = hopsById.getOrDefault(fromId, 0L);
                long toHops = hopsById.getOrDefault(toId, 0L);
                if (fromHops <= toHops) {
                    edges.add(new GraphEdgeDto(fromId, toId, "CO_PURCHASED_WITH"));
                } else {
                    edges.add(new GraphEdgeDto(toId, fromId, "CO_PURCHASED_WITH"));
                }
            }

            return new RecommendationGraphDto(productId, new ArrayList<>(nodes.values()), edges);
        });
    }

    /** "How does interest in product A lead to product B?" - shortest chain of co-purchases. */
    public PathResult shortestDiscoveryPath(String fromProductId, String toProductId) {
        String cypher = """
                MATCH (a:Product {id: $fromId}), (b:Product {id: $toId})
                OPTIONAL MATCH path = shortestPath((a)-[:CO_PURCHASED_WITH*..%d]-(b))
                RETURN path
                """.formatted(MAX_HOPS * 2);

        return executor.read(tx -> {
            Result result = tx.run(cypher, Map.of("fromId", fromProductId, "toId", toProductId));
            if (!result.hasNext()) {
                throw new NotFoundException("One or both products were not found");
            }
            Record r = result.next();
            if (r.get("path").isNull()) {
                return new PathResult(false, 0, List.of(), List.of());
            }
            Path path = r.get("path").asPath();

            Map<String, GraphNodeDto> nodes = new LinkedHashMap<>();
            List<Node> ordered = new ArrayList<>();
            for (Node n : path.nodes()) {
                ordered.add(n);
                nodeFromProductNode(tx, n).ifPresent(dto -> nodes.put(dto.id(), dto));
            }
            List<GraphEdgeDto> edges = new ArrayList<>();
            for (int i = 0; i < ordered.size() - 1; i++) {
                edges.add(new GraphEdgeDto(ordered.get(i).get("id").asString(),
                        ordered.get(i + 1).get("id").asString(), "CO_PURCHASED_WITH"));
            }

            return new PathResult(true, path.length(), new ArrayList<>(nodes.values()), edges);
        });
    }

    private java.util.Optional<GraphNodeDto> nodeFromProductNode(org.neo4j.driver.TransactionContext tx, Node productNode) {
        Result r = tx.run("""
                MATCH (p:Product {id: $id})
                OPTIONAL MATCH (p)-[:IN_CATEGORY]->(c:Category)
                RETURN p.name AS name, c.name AS category
                """, Map.of("id", productNode.get("id").asString()));
        if (!r.hasNext()) {
            return java.util.Optional.empty();
        }
        Record rec = r.next();
        String id = productNode.get("id").asString();
        return java.util.Optional.of(new GraphNodeDto(
                id, rec.get("name").asString(),
                rec.get("category").isNull() ? "" : rec.get("category").asString(),
                "PRODUCT"
        ));
    }

    /** Bestsellers: products with the most orders - the "in-degree" of the purchase graph. */
    private static final String BESTSELLERS_QUERY = """
            MATCH (p:Product)<-[:CONTAINS]-(:Order)
            WITH p, count(*) AS orderCount
            OPTIONAL MATCH (p)-[:IN_CATEGORY]->(c:Category)
            OPTIONAL MATCH (p)-[:BY_BRAND]->(b:Brand)
            OPTIONAL MATCH (:Customer)-[rev:REVIEWED]->(p)
            WITH p, c, b, orderCount, avg(rev.rating) AS avgRating
            RETURN p.id AS productId, p.name AS productName, c.name AS category, b.name AS brand,
                   p.price AS price, avgRating, orderCount
            ORDER BY orderCount DESC
            LIMIT $limit
            """;

    public List<BestsellerDto> getBestsellers(int limit) {
        return executor.read(tx -> {
            Result result = tx.run(BESTSELLERS_QUERY, Map.of("limit", limit));
            List<BestsellerDto> out = new ArrayList<>();
            while (result.hasNext()) {
                Record r = result.next();
                out.add(new BestsellerDto(
                        r.get("productId").asString(),
                        r.get("productName").asString(),
                        r.get("category").isNull() ? null : r.get("category").asString(),
                        r.get("brand").isNull() ? null : r.get("brand").asString(),
                        r.get("price").asDouble(),
                        r.get("avgRating").isNull() ? null : r.get("avgRating").asDouble(),
                        r.get("orderCount").asLong()
                ));
            }
            return out;
        });
    }

    /**
     * "Deals": products that have an exact same-name alternative from a different brand for
     * less - the same tier-1 comparison from ProductService.getSimilarProducts, surfaced as a
     * homepage feed instead of something you only see after opening a specific product. Reuses
     * the same underlying signal (name match across BY_BRAND), just aggregated and ranked by
     * savings amount.
     */
    private static final String DEALS_QUERY = """
            MATCH (p:Product)
            MATCH (cheaper:Product)
            WHERE toLower(cheaper.name) = toLower(p.name) AND cheaper.price < p.price
            WITH p, cheaper
            ORDER BY cheaper.price ASC
            WITH p, collect(cheaper)[0] AS bestAlternative
            OPTIONAL MATCH (p)-[:IN_CATEGORY]->(c:Category)
            OPTIONAL MATCH (p)-[:BY_BRAND]->(b:Brand)
            OPTIONAL MATCH (bestAlternative)-[:BY_BRAND]->(cb:Brand)
            RETURN p.id AS productId, p.name AS productName, c.name AS category, b.name AS brand, p.price AS price,
                   bestAlternative.id AS cheaperProductId, cb.name AS cheaperBrand, bestAlternative.price AS cheaperPrice,
                   p.price - bestAlternative.price AS savings
            ORDER BY savings DESC
            LIMIT $limit
            """;

    public List<DealDto> getDeals(int limit) {
        return executor.read(tx -> {
            Result result = tx.run(DEALS_QUERY, Map.of("limit", limit));
            List<DealDto> out = new ArrayList<>();
            while (result.hasNext()) {
                Record r = result.next();
                out.add(new DealDto(
                        r.get("productId").asString(),
                        r.get("productName").asString(),
                        r.get("category").isNull() ? null : r.get("category").asString(),
                        r.get("brand").isNull() ? null : r.get("brand").asString(),
                        r.get("price").asDouble(),
                        r.get("cheaperProductId").asString(),
                        r.get("cheaperBrand").isNull() ? null : r.get("cheaperBrand").asString(),
                        r.get("cheaperPrice").asDouble(),
                        r.get("savings").asDouble()
                ));
            }
            return out;
        });
    }
}
