package com.wexa.retailgraph.dto;

/** hops = degrees of separation from the seed product through the co-purchase graph
 *  (1 = people who bought the seed also bought this; 2+ = second-degree and beyond). */
public record RecommendedProductDto(
        String productId,
        String productName,
        String category,
        String brand,
        double price,
        long hops
) {}
