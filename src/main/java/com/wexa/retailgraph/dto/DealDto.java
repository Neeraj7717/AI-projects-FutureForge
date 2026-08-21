package com.wexa.retailgraph.dto;

/** A product that has a cheaper same-name alternative from another brand - the "similar
 *  products, other brands" query, aggregated into a homepage deals feed. */
public record DealDto(
        String productId,
        String productName,
        String category,
        String brand,
        double price,
        String cheaperProductId,
        String cheaperBrand,
        double cheaperPrice,
        double savings
) {}
