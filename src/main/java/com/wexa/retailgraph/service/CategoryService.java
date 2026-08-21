package com.wexa.retailgraph.service;

import com.wexa.retailgraph.dto.CategoryDto;
import com.wexa.retailgraph.dto.ProductSummary;
import com.wexa.retailgraph.exception.NotFoundException;
import org.neo4j.driver.Record;
import org.neo4j.driver.Result;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/** Powers the category sidebar and the "browse a category" page - straightforward reads over
 *  the IN_CATEGORY relationship, included for a non-technical shopper to explore the catalog
 *  without needing to already know what they're searching for. */
@Service
public class CategoryService {

    private final GraphQueryExecutor executor;

    public CategoryService(GraphQueryExecutor executor) {
        this.executor = executor;
    }

    private static final String LIST_QUERY = """
            MATCH (c:Category)
            OPTIONAL MATCH (c)<-[:IN_CATEGORY]-(p:Product)
            WITH c, count(p) AS productCount
            RETURN c.id AS id, c.name AS name, productCount
            ORDER BY c.name
            """;

    public List<CategoryDto> listCategories() {
        return executor.read(tx -> {
            Result result = tx.run(LIST_QUERY, Map.of());
            List<CategoryDto> out = new ArrayList<>();
            while (result.hasNext()) {
                Record r = result.next();
                out.add(new CategoryDto(
                        r.get("id").asString(),
                        r.get("name").asString(),
                        r.get("productCount").asLong()
                ));
            }
            return out;
        });
    }

    private static final String GET_QUERY = """
            MATCH (c:Category {id: $categoryId})
            OPTIONAL MATCH (c)<-[:IN_CATEGORY]-(p:Product)
            RETURN c.id AS id, c.name AS name, count(p) AS productCount
            """;

    public CategoryDto getCategory(String categoryId) {
        return executor.read(tx -> {
            Result result = tx.run(GET_QUERY, Map.of("categoryId", categoryId));
            if (!result.hasNext()) {
                throw new NotFoundException("No category found with id '" + categoryId + "'");
            }
            Record r = result.next();
            return new CategoryDto(r.get("id").asString(), r.get("name").asString(), r.get("productCount").asLong());
        });
    }

    private static final String PRODUCTS_QUERY = """
            MATCH (c:Category {id: $categoryId})<-[:IN_CATEGORY]-(p:Product)
            OPTIONAL MATCH (p)-[:BY_BRAND]->(b:Brand)
            RETURN p.id AS id, p.name AS name, c.name AS category, b.name AS brand, p.price AS price
            ORDER BY p.name
            """;

    public List<ProductSummary> getProductsInCategory(String categoryId) {
        return executor.read(tx -> {
            Result result = tx.run(PRODUCTS_QUERY, Map.of("categoryId", categoryId));
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
