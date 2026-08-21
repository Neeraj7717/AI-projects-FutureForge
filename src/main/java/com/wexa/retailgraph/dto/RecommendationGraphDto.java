package com.wexa.retailgraph.dto;

import java.util.List;

public record RecommendationGraphDto(String rootId, List<GraphNodeDto> nodes, List<GraphEdgeDto> edges) {}
