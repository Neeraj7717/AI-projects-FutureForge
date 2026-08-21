package com.wexa.retailgraph.dto;

import java.util.List;

public record RecommendationResult(
        String seedProductId,
        String seedProductName,
        String category,
        List<RecommendedProductDto> recommendations
) {}
