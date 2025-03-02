package org.aialabs.dg.web.rest;

import org.aialabs.dg.service.UnityCatalogService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/unity-catalog") // Updated base path to match API structure
public class UnityCatalogController {

    private final UnityCatalogService unityCatalogService;

    public UnityCatalogController(UnityCatalogService unityCatalogService) {
        this.unityCatalogService = unityCatalogService;
    }

    // List all catalogs
    @GetMapping("/catalogs")
    public ResponseEntity<String> listCatalogs() {
        String catalogs = unityCatalogService.listCatalogs();
        return ResponseEntity.ok(catalogs);
    }

    // Create a new catalog
    @PostMapping("/catalogs")
    public ResponseEntity<String> createCatalog(@RequestParam("catalog_name") String catalogName) {
        String response = unityCatalogService.createCatalog(catalogName);
        return ResponseEntity.ok(response);
    }

    // List schemas within a catalog
    @GetMapping("/schemas")
    public ResponseEntity<String> listSchemas(@RequestParam("catalog_name") String catalogName) {
        String schemas = unityCatalogService.listSchemas(catalogName);
        return ResponseEntity.ok(schemas);
    }

    // Create a new schema within a catalog
    @PostMapping("/schemas")
    public ResponseEntity<String> createSchema(@RequestParam("catalog_name") String catalogName, @RequestParam("name") String schemaName) {
        String response = unityCatalogService.createSchema(catalogName, schemaName);
        return ResponseEntity.ok(response);
    }

    // List tables within a schema
    @GetMapping("/tables")
    public ResponseEntity<String> listTables(
        @RequestParam("catalog_name") String catalogName,
        @RequestParam("schema_name") String schemaName
    ) {
        String tables = unityCatalogService.listTables(catalogName, schemaName);
        return ResponseEntity.ok(tables);
    }

    // Create a new table within a schema
    @PostMapping("/tables")
    public ResponseEntity<String> createTable(
        @RequestParam("catalog_name") String catalogName,
        @RequestParam("schema_name") String schemaName,
        @RequestParam("name") String tableName
    ) {
        String response = unityCatalogService.createTable(catalogName, schemaName, tableName);
        return ResponseEntity.ok(response);
    }
}
