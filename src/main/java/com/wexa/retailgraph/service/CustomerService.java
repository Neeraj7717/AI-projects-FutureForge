package com.wexa.retailgraph.service;

import com.wexa.retailgraph.dto.CustomerSummary;
import com.wexa.retailgraph.dto.ProductSummary;
import com.wexa.retailgraph.dto.SimilarShopperDto;
import com.wexa.retailgraph.exception.NotFoundException;
import org.neo4j.driver.Record;
import org.neo4j.driver.Result;
import org.neo4j.driver.Value;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * Shared-purchase-history similarity: "who else shops like this customer, and what did they buy
 * that this customer hasn't" - the classic user-based collaborative filtering query. It's a join
 * through shared products between two people, not a foreign key - the kind of query that stays
 * a single readable traversal here regardless of how many customers or products are involved,
 * where a relational join across order_items against itself gets expensive and awkward fast.
 */
@Service
public class CustomerService {

    private static final int UNIQUE_RECS_PER_SHOPPER = 5;

    private final GraphQueryExecutor executor;

    public CustomerService(GraphQueryExecutor executor) {
        this.executor = executor;
    }

    private static final String CUSTOMER_QUERY = """
            MATCH (c:Customer {id: $customerId})
            RETURN c.id AS id, c.name AS name, c.email AS email
            """;

    public CustomerSummary getCustomer(String customerId) {
        return executor.read(tx -> {
            Result r = tx.run(CUSTOMER_QUERY, Map.of("customerId", customerId));
            if (!r.hasNext()) {
                throw new NotFoundException("No customer found with id '" + customerId + "'");
            }
            Record rec = r.next();
            return new CustomerSummary(rec.get("id").asString(), rec.get("name").asString(), rec.get("email").asString());
        });
    }

    private static final String SEARCH_QUERY = """
            MATCH (c:Customer)
            WHERE toLower(c.name) CONTAINS toLower($query)
            RETURN c.id AS id, c.name AS name, c.email AS email
            ORDER BY c.name
            LIMIT $limit
            """;

    public List<CustomerSummary> search(String query, int limit) {
        return executor.read(tx -> {
            Result result = tx.run(SEARCH_QUERY, Map.of("query", query, "limit", limit));
            List<CustomerSummary> out = new ArrayList<>();
            while (result.hasNext()) {
                Record r = result.next();
                out.add(new CustomerSummary(r.get("id").asString(), r.get("name").asString(), r.get("email").asString()));
            }
            return out;
        });
    }

    private static final String SIMILAR_SHOPPERS_QUERY = """
            MATCH (target:Customer {id: $customerId})-[:PLACED]->(:Order)-[:CONTAINS]->(p:Product)
            WITH target, collect(DISTINCT p.id) AS targetProductIds
            MATCH (other:Customer)-[:PLACED]->(:Order)-[:CONTAINS]->(shared:Product)
            WHERE other <> target AND shared.id IN targetProductIds
            WITH other, targetProductIds, count(DISTINCT shared) AS sharedCount
            ORDER BY sharedCount DESC
            LIMIT $limit
            RETURN other.id AS customerId, other.name AS customerName, sharedCount, targetProductIds
            """;

    private static final String UNIQUE_RECOMMENDATIONS_QUERY = """
            MATCH (other:Customer {id: $otherId})-[:PLACED]->(:Order)-[:CONTAINS]->(rec:Product)
            WHERE NOT rec.id IN $excludeIds
            OPTIONAL MATCH (rec)-[:IN_CATEGORY]->(c:Category)
            OPTIONAL MATCH (rec)-[:BY_BRAND]->(b:Brand)
            RETURN DISTINCT rec.id AS productId, rec.name AS productName, c.name AS category,
                   b.name AS brand, rec.price AS price
            LIMIT $limit
            """;

    public List<SimilarShopperDto> getSimilarShoppers(String customerId, int limit) {
        List<Record> similar = executor.read(tx -> {
            Result result = tx.run(SIMILAR_SHOPPERS_QUERY, Map.of("customerId", customerId, "limit", limit));
            List<Record> rows = new ArrayList<>();
            while (result.hasNext()) {
                rows.add(result.next());
            }
            return rows;
        });

        List<SimilarShopperDto> out = new ArrayList<>();
        for (Record row : similar) {
            String otherId = row.get("customerId").asString();
            List<String> targetProductIds = new ArrayList<>();
            for (Value v : row.get("targetProductIds").asList(v -> v)) {
                targetProductIds.add(v.asString());
            }

            List<ProductSummary> recs = executor.read(tx -> {
                Result r = tx.run(UNIQUE_RECOMMENDATIONS_QUERY,
                        Map.of("otherId", otherId, "excludeIds", targetProductIds, "limit", UNIQUE_RECS_PER_SHOPPER));
                List<ProductSummary> products = new ArrayList<>();
                while (r.hasNext()) {
                    Record pr = r.next();
                    products.add(new ProductSummary(
                            pr.get("productId").asString(),
                            pr.get("productName").asString(),
                            pr.get("category").isNull() ? null : pr.get("category").asString(),
                            pr.get("brand").isNull() ? null : pr.get("brand").asString(),
                            pr.get("price").asDouble()
                    ));
                }
                return products;
            });

            out.add(new SimilarShopperDto(otherId, row.get("customerName").asString(), row.get("sharedCount").asLong(), recs));
        }
        return out;
    }
}
