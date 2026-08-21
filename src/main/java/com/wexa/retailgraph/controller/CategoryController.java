package com.wexa.retailgraph.controller;

import com.wexa.retailgraph.dto.CategoryDto;
import com.wexa.retailgraph.dto.ProductSummary;
import com.wexa.retailgraph.service.CategoryService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/categories")
public class CategoryController {

    private final CategoryService categoryService;

    public CategoryController(CategoryService categoryService) {
        this.categoryService = categoryService;
    }

    @GetMapping
    public List<CategoryDto> list() {
        return categoryService.listCategories();
    }

    @GetMapping("/{categoryId}")
    public CategoryDto get(@PathVariable String categoryId) {
        return categoryService.getCategory(categoryId);
    }

    @GetMapping("/{categoryId}/products")
    public List<ProductSummary> products(@PathVariable String categoryId) {
        return categoryService.getProductsInCategory(categoryId);
    }
}
