package com.wexa.retailgraph.dto;

import java.util.List;

/** sharedProductCount = how many products this shopper and the target customer both bought.
 *  uniqueRecommendations = products this shopper bought that the target customer has not
 *  (the actual "customers like you also bought" recommendation). */
public record SimilarShopperDto(
        String customerId,
        String customerName,
        long sharedProductCount,
        List<ProductSummary> uniqueRecommendations
) {}
