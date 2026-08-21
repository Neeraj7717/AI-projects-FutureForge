package com.wexa.retailgraph.dto;

public record BestsellerDto(String productId, String productName, String category, String brand,
                             double price, Double avgRating, long orderCount) {}
