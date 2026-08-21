package com.wexa.retailgraph.dto;

/** strength = how many distinct orders contained both products. */
public record CoPurchaseDto(String productId, String productName, String category, String brand, double price, long strength) {}
