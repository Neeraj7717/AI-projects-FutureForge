package com.wexa.retailgraph.controller;

import com.wexa.retailgraph.dto.CustomerSummary;
import com.wexa.retailgraph.dto.SimilarShopperDto;
import com.wexa.retailgraph.service.CustomerService;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/customers")
public class CustomerController {

    private final CustomerService customerService;

    public CustomerController(CustomerService customerService) {
        this.customerService = customerService;
    }

    @GetMapping("/search")
    public List<CustomerSummary> search(@RequestParam("q") String query,
                                         @RequestParam(value = "limit", defaultValue = "20") int limit) {
        if (query == null || query.isBlank()) {
            return List.of();
        }
        return customerService.search(query.trim(), Math.min(Math.max(limit, 1), 50));
    }

    @GetMapping("/{customerId}")
    public CustomerSummary getCustomer(@PathVariable String customerId) {
        return customerService.getCustomer(customerId);
    }

    /** Shared-purchase-history similarity: "who shops like this customer". */
    @GetMapping("/{customerId}/similar-shoppers")
    public List<SimilarShopperDto> similarShoppers(@PathVariable String customerId,
                                                     @RequestParam(defaultValue = "5") int limit) {
        return customerService.getSimilarShoppers(customerId, Math.min(Math.max(limit, 1), 20));
    }
}
