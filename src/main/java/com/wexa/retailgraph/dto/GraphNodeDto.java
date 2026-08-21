package com.wexa.retailgraph.dto;

/** type is one of: PRODUCT, SEED_PRODUCT - lets the frontend highlight the anchor product differently. */
public record GraphNodeDto(String id, String label, String sublabel, String type) {}
