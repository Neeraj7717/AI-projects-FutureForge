package org.aialabs.dg.web.rest;

import java.util.Map;
import org.aialabs.dg.CatalogCreation.UnityCatalogAssetCounter;
import org.aialabs.dg.CatalogCreation.UnityCatalogAssetCounter.AssetCount;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/assets")
public class AssetCountController {

    private static final Logger log = LoggerFactory.getLogger(AssetCountController.class);
    private final UnityCatalogAssetCounter assetCounter;

    @Autowired
    public AssetCountController(UnityCatalogAssetCounter assetCounter) {
        this.assetCounter = assetCounter;
    }

    @GetMapping("/assets")
    public ResponseEntity<Map<String, Object>> getDiscoveredAssets(
        @RequestParam(defaultValue = "0") int page,
        @RequestParam(defaultValue = "20") int pageSize,
        @RequestParam(defaultValue = "lastDiscoveredAt,desc") String sort,
        @RequestParam(required = false) String search,
        @RequestParam(required = false) String dataSource,
        @RequestParam(required = false) String assetType,
        @RequestParam(required = false) String status,
        @RequestParam(required = false) String dateRange
    ) {
        try {
            Map<String, Object> result = assetCounter.getPaginatedAssets(
                "your_catalog_name",
                page,
                pageSize,
                sort,
                search,
                dataSource,
                assetType,
                status,
                dateRange
            );
            return ResponseEntity.ok(result);
        } catch (Exception e) {
            log.error("Error fetching discovered assets", e);
            return ResponseEntity
                .status(HttpStatus.INTERNAL_SERVER_ERROR)
                .body(Map.of("error", "Failed to fetch discovered assets: " + e.getMessage()));
        }
    }
}
