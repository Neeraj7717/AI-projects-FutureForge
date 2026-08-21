package com.wexa.retailgraph.dto;

import java.util.List;

public record PathResult(boolean found, int length, List<GraphNodeDto> nodes, List<GraphEdgeDto> edges) {}
