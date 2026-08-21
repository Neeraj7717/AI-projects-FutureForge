package com.wexa.retailgraph.controller;

import com.wexa.retailgraph.dto.DashboardStats;
import com.wexa.retailgraph.service.StatsService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/stats")
public class StatsController {

    private final StatsService statsService;

    public StatsController(StatsService statsService) {
        this.statsService = statsService;
    }

    @GetMapping
    public DashboardStats stats() {
        return statsService.getDashboardStats();
    }
}
