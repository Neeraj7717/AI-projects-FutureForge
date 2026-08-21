package com.wexa.retailgraph.service;

import com.wexa.retailgraph.dto.CoPurchaseDto;
import com.wexa.retailgraph.dto.ProductDetail;
import com.wexa.retailgraph.dto.ProductSummary;
import com.wexa.retailgraph.exception.NotFoundException;
import org.neo4j.driver.Record;
import org.neo4j.driver.Result;
import org.neo4j.driver.types.Node;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

@Service
public class ProductService {

    private final GraphQueryExecutor executor;

    public ProductService(GraphQueryExecutor executor) {
        this.executor = executor;
    }

    private static final String SEARCH_QUERY = """
            MATCH (p:Product)
            WHERE toLower(p.name) CONTAINS toLower($query)
            OPTIONAL MATCH (p)-[:IN_CATEGORY]->(c:Category)
            OPTIONAL MATCH (p)-[:BY_BRAND]->(b:Brand)
            RETURN p.id AS id, p.name AS name, c.name AS category, b.name AS brand, p.price AS price
            ORDER BY p.name
            LIMIT $limit
            """;

    public List<ProductSummary> search(String query, int limit) {
        return executor.read(tx -> {
            Result result = tx.run(SEARCH_QUERY, Map.of("query", query, "limit", limit));
            List<ProductSummary> out = new ArrayList<>();
            while (result.hasNext()) {
                Record r = result.next();
                out.add(new ProductSummary(
                        r.get("id").asString(),
                        r.get("name").asString(),
                        r.get("category").isNull() ? null : r.get("category").asString(),
                        r.get("brand").isNull() ? null : r.get("brand").asString(),
                        r.get("price").asDouble()
                ));
            }
            return out;
        });
    }

    private static final String DETAIL_QUERY = """
            MATCH (p:Product {id: $productId})
            OPTIONAL MATCH (p)-[:IN_CATEGORY]->(c:Category)
            OPTIONAL MATCH (p)-[:BY_BRAND]->(b:Brand)
            OPTIONAL MATCH (:Customer)-[rev:REVIEWED]->(p)
            WITH p, c, b, avg(rev.rating) AS avgRating, count(rev) AS reviewCount
            OPTIONAL MATCH (:Order)-[:CONTAINS]->(p)
            WITH p, c, b, avgRating, reviewCount, count(*) AS orderCount
            RETURN p, c.name AS category, b.name AS brand, avgRating, reviewCount, orderCount
            """;

    public ProductDetail getProductDetail(String productId) {
        return executor.read(tx -> {
            Result result = tx.run(DETAIL_QUERY, Map.of("productId", productId));
            if (!result.hasNext()) {
                throw new NotFoundException("No product found with id '" + productId + "'");
            }
            Record r = result.next();
            Node p = r.get("p").asNode();
            return new ProductDetail(
                    p.get("id").asString(),
                    p.get("name").asString(),
                    p.get("description").isNull() ? null : p.get("description").asString(),
                    p.get("price").asDouble(),
                    p.get("sku").isNull() ? null : p.get("sku").asString(),
                    r.get("category").isNull() ? null : r.get("category").asString(),
                    r.get("brand").isNull() ? null : r.get("brand").asString(),
                    r.get("avgRating").isNull() ? null : r.get("avgRating").asDouble(),
                    r.get("reviewCount").asLong(),
                    r.get("orderCount").asLong()
            );
        });
    }

    /** Direct (1-hop) "frequently bought together": the precomputed co-purchase edge. */
    private static final String FREQUENTLY_BOUGHT_TOGETHER_QUERY = """
            MATCH (p:Product {id: $productId})-[r:CO_PURCHASED_WITH]-(other:Product)
            OPTIONAL MATCH (other)-[:IN_CATEGORY]->(c:Category)
            OPTIONAL MATCH (other)-[:BY_BRAND]->(b:Brand)
            RETURN other.id AS productId, other.name AS productName, c.name AS category,
                   b.name AS brand, other.price AS price, r.strength AS strength
            ORDER BY strength DESC, productName ASC
            LIMIT $limit
            """;

    public List<CoPurchaseDto> getFrequentlyBoughtTogether(String productId, int limit) {
        return executor.read(tx -> {
            Result result = tx.run(FREQUENTLY_BOUGHT_TOGETHER_QUERY, Map.of("productId", productId, "limit", limit));
            List<CoPurchaseDto> out = new ArrayList<>();
            while (result.hasNext()) {
                Record r = result.next();
                out.add(new CoPurchaseDto(
                        r.get("productId").asString(),
                        r.get("productName").asString(),
                        r.get("category").isNull() ? null : r.get("category").asString(),
                        r.get("brand").isNull() ? null : r.get("brand").asString(),
                        r.get("price").asDouble(),
                        r.get("strength").asLong()
                ));
            }
            return out;
        });
    }

    /**
     * "Same product, other company": an exact-name match across brands (e.g. "Whole Milk 1L" by
     * FreshFarm vs. by ValueMart) - the direct price comparison a shopper actually wants when they
     * open a branded item. Not every product has one (most produce is unbranded and one-of-a-kind
     * in the catalog), so {@link #getSimilarProducts} falls back to same-category browsing when
     * this comes back empty - every product still gets a useful "similar" list either way.
     */
    private static final String SAME_PRODUCT_OTHER_BRAND_QUERY = """
            MATCH (p:Product {id: $productId})
            MATCH (similar:Product)
            WHERE toLower(similar.name) = toLower(p.name) AND similar <> p
            OPTIONAL MATCH (similar)-[:IN_CATEGORY]->(c:Category)
            OPTIONAL MATCH (similar)-[:BY_BRAND]->(b:Brand)
            RETURN similar.id AS id, similar.name AS name, c.name AS category, b.name AS brand, similar.price AS price
            ORDER BY similar.price ASC
            LIMIT $limit
            """;

    /** Fallback: other products in the same category, cheapest first - a 2-hop traversal
     *  (Product -> Category <- Product) distinct from the co-purchase graph. */
    private static final String SAME_CATEGORY_QUERY = """
            MATCH (p:Product {id: $productId})-[:IN_CATEGORY]->(c:Category)<-[:IN_CATEGORY]-(similar:Product)
            WHERE similar <> p
            OPTIONAL MATCH (similar)-[:BY_BRAND]->(b:Brand)
            RETURN similar.id AS id, similar.name AS name, c.name AS category, b.name AS brand, similar.price AS price
            ORDER BY similar.price ASC
            LIMIT $limit
            """;

    public List<ProductSummary> getSimilarProducts(String productId, int limit) {
        List<ProductSummary> sameProduct = runSimilarQuery(SAME_PRODUCT_OTHER_BRAND_QUERY, productId, limit);
        if (!sameProduct.isEmpty()) {
            return sameProduct;
        }
        return runSimilarQuery(SAME_CATEGORY_QUERY, productId, limit);
    }

    private List<ProductSummary> runSimilarQuery(String cypher, String productId, int limit) {
        return executor.read(tx -> {
            Result result = tx.run(cypher, Map.of("productId", productId, "limit", limit));
            List<ProductSummary> out = new ArrayList<>();
            while (result.hasNext()) {
                Record r = result.next();
                out.add(new ProductSummary(
                        r.get("id").asString(),
                        r.get("name").asString(),
                        r.get("category").isNull() ? null : r.get("category").asString(),
                        r.get("brand").isNull() ? null : r.get("brand").asString(),
                        r.get("price").asDouble()
                ));
            }
            return out;
        });
    }
}
