package com.wexa.retailgraph.dto;

public record ProductDetail(
        String id,
        String name,
        String description,
        double price,
        String sku,
        String category,
        String brand,
        Double avgRating,
        long reviewCount,
        long orderCount
) {}
