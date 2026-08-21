package com.wexa.retailgraph.controller;

import com.wexa.retailgraph.dto.BestsellerDto;
import com.wexa.retailgraph.dto.DealDto;
import com.wexa.retailgraph.dto.PathResult;
import com.wexa.retailgraph.dto.RecommendationGraphDto;
import com.wexa.retailgraph.dto.RecommendationResult;
import com.wexa.retailgraph.service.RecommendationService;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/recommendations")
public class RecommendationController {

    private final RecommendationService recommendationService;

    public RecommendationController(RecommendationService recommendationService) {
        this.recommendationService = recommendationService;
    }

    /** Multi-hop: extended ("second-degree and beyond") recommendations, ranked list. */
    @GetMapping("/{productId}/extended")
    public RecommendationResult extendedRecommendations(@PathVariable String productId,
                                                          @RequestParam(defaultValue = "3") int hops,
                                                          @RequestParam(defaultValue = "20") int limit) {
        return recommendationService.getExtendedRecommendations(productId, hops, Math.min(Math.max(limit, 1), 100));
    }

    /** Same traversal as above, shaped as a graph for the visualization. */
    @GetMapping("/{productId}/graph")
    public RecommendationGraphDto recommendationGraph(@PathVariable String productId,
                                                        @RequestParam(defaultValue = "3") int hops) {
        return recommendationService.getRecommendationGraph(productId, hops);
    }

    /** Multi-hop: shortest discovery path between two products. */
    @GetMapping("/path")
    public PathResult shortestPath(@RequestParam String from, @RequestParam String to) {
        return recommendationService.shortestDiscoveryPath(from, to);
    }

    @GetMapping("/bestsellers")
    public List<BestsellerDto> bestsellers(@RequestParam(defaultValue = "10") int limit) {
        return recommendationService.getBestsellers(Math.min(Math.max(limit, 1), 50));
    }

    @GetMapping("/deals")
    public List<DealDto> deals(@RequestParam(defaultValue = "10") int limit) {
        return recommendationService.getDeals(Math.min(Math.max(limit, 1), 50));
    }
}
