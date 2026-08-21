package com.wexa.retailgraph.controller;

import com.wexa.retailgraph.dto.CoPurchaseDto;
import com.wexa.retailgraph.dto.ProductDetail;
import com.wexa.retailgraph.dto.ProductSummary;
import com.wexa.retailgraph.service.ProductService;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/products")
public class ProductController {

    private final ProductService productService;

    public ProductController(ProductService productService) {
        this.productService = productService;
    }

    @GetMapping("/search")
    public List<ProductSummary> search(@RequestParam("q") String query,
                                        @RequestParam(value = "limit", defaultValue = "20") int limit) {
        if (query == null || query.isBlank()) {
            return List.of();
        }
        return productService.search(query.trim(), Math.min(Math.max(limit, 1), 50));
    }

    @GetMapping("/{productId}")
    public ProductDetail getProduct(@PathVariable String productId) {
        return productService.getProductDetail(productId);
    }

    /** Direct (1-hop): "frequently bought together". */
    @GetMapping("/{productId}/frequently-bought-together")
    public List<CoPurchaseDto> frequentlyBoughtTogether(@PathVariable String productId,
                                                          @RequestParam(defaultValue = "8") int limit) {
        return productService.getFrequentlyBoughtTogether(productId, Math.min(Math.max(limit, 1), 30));
    }

    /** 2-hop: other products in the same category, cheapest first - "similar, better offer". */
    @GetMapping("/{productId}/similar")
    public List<ProductSummary> similarProducts(@PathVariable String productId,
                                                  @RequestParam(defaultValue = "8") int limit) {
        return productService.getSimilarProducts(productId, Math.min(Math.max(limit, 1), 30));
    }
}
