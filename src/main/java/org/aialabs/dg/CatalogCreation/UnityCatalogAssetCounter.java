package org.aialabs.dg.CatalogCreation;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Instant;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.stream.Collectors;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

@Component
public class UnityCatalogAssetCounter {

    private static final Logger log = LoggerFactory.getLogger(UnityCatalogAssetCounter.class);
    private static final DateTimeFormatter ISO_FORMATTER = DateTimeFormatter.ISO_INSTANT.withZone(ZoneOffset.UTC);

    @Value("${unity.catalog.api.url}")
    private String baseUrl;

    @Value("${unity.catalog.api.token}")
    private String apiToken;

    @Value("${unity.catalog.schema.name}")
    private String schemaName;

    // Inner class to hold the count results
    public static class AssetCount {

        public final int volumeCount;
        public final int tableCount;
        public final int totalAssets;
        public final int recentVolumeCount;
        public final int recentTableCount;
        public final int totalRecentAssets;
        public final String catalogName;
        public final String schemaName;

        public AssetCount(
            int volumeCount,
            int tableCount,
            int totalAssets,
            int recentVolumeCount,
            int recentTableCount,
            int totalRecentAssets,
            String catalogName,
            String schemaName
        ) {
            this.volumeCount = volumeCount;
            this.tableCount = tableCount;
            this.totalAssets = totalAssets;
            this.recentVolumeCount = recentVolumeCount;
            this.recentTableCount = recentTableCount;
            this.totalRecentAssets = totalRecentAssets;
            this.catalogName = catalogName;
            this.schemaName = schemaName;
        }
    }

    // New class to match frontend's IDiscoveredAsset interface
    public static class DiscoveredAsset {

        public final String id;
        public final String name;
        public final String dataSource;
        public final String type;
        public final String size;
        public final String location;
        public final String discoveryDate;
        public final String lastModified;
        public final String status;
        public final String owner;
        public final List<SchemaField> schema;
        public final AssetMetadata metadata;
        public final List<String> tags;
        public final AssetQuality quality;

        public DiscoveredAsset(
            String id,
            String name,
            String dataSource,
            String type,
            String size,
            String location,
            String discoveryDate,
            String lastModified,
            String status,
            String owner,
            List<SchemaField> schema,
            AssetMetadata metadata,
            List<String> tags,
            AssetQuality quality
        ) {
            this.id = id;
            this.name = name;
            this.dataSource = dataSource;
            this.type = type;
            this.size = size;
            this.location = location;
            this.discoveryDate = discoveryDate;
            this.lastModified = lastModified;
            this.status = status;
            this.owner = owner;
            this.schema = schema;
            this.metadata = metadata;
            this.tags = tags;
            this.quality = quality;
        }
    }

    public static class SchemaField {

        public final String field;
        public final String type;

        public SchemaField(String field, String type) {
            this.field = field;
            this.type = type;
        }
    }

    public static class AssetMetadata {

        public final Long rows;
        public final Integer columns;
        public final String format;
        public final String encoding;
        public final String compression;

        public AssetMetadata(Long rows, Integer columns, String format, String encoding, String compression) {
            this.rows = rows;
            this.columns = columns;
            this.format = format;
            this.encoding = encoding;
            this.compression = compression;
        }
    }

    public static class AssetQuality {

        public final int score;
        public final List<String> issues;

        public AssetQuality(int score, List<String> issues) {
            this.score = score;
            this.issues = issues;
        }
    }

    // Inner class to represent Unity Catalog asset data
    public static class AssetData {

        public final String name;
        public final String type;
        public final long createdAt;
        public final ObjectNode metadata;

        public AssetData(String name, String type, long createdAt, ObjectNode metadata) {
            this.name = name;
            this.type = type;
            this.createdAt = createdAt;
            this.metadata = metadata;
        }
    }

    // Method to get all assets from a catalog with pagination and filtering
    public List<AssetData> getAllAssetsForCatalog(String catalogName) {
        try {
            HttpClient client = HttpClient.newHttpClient();
            String url = baseUrl + "/catalogs/" + catalogName + "/schemas/" + schemaName + "/assets";
            log.debug("Fetching assets from URL: {}", url);

            HttpRequest request = HttpRequest.newBuilder().uri(URI.create(url)).header("Authorization", "Bearer " + apiToken).GET().build();

            HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());

            if (response.statusCode() == 200) {
                ObjectMapper mapper = new ObjectMapper();
                ObjectNode root = (ObjectNode) mapper.readTree(response.body());
                ArrayNode assets = (ArrayNode) root.get("assets");

                List<AssetData> result = new ArrayList<>();
                for (int i = 0; i < assets.size(); i++) {
                    ObjectNode asset = (ObjectNode) assets.get(i);
                    result.add(
                        new AssetData(
                            asset.get("name").asText(),
                            asset.get("type").asText(),
                            asset.get("created_at").asLong(),
                            (ObjectNode) asset.get("metadata")
                        )
                    );
                }
                return result;
            } else {
                log.error(
                    "Failed to fetch assets from Unity Catalog. Status code: {}, Response: {}",
                    response.statusCode(),
                    response.body()
                );
                return new ArrayList<>();
            }
        } catch (Exception e) {
            log.error("Error fetching assets from Unity Catalog", e);
            return new ArrayList<>();
        }
    }

    // Method to get paginated and filtered assets
    public Map<String, Object> getPaginatedAssets(
        String catalogName,
        int page,
        int pageSize,
        String sort,
        String search,
        String dataSource,
        String assetType,
        String status,
        String dateRange
    ) {
        try {
            List<AssetData> allAssets = getAllAssetsForCatalog(catalogName);

            // Apply filters
            List<AssetData> filteredAssets = allAssets
                .stream()
                .filter(asset -> {
                    // Search filter
                    if (search != null && !search.isEmpty()) {
                        String searchLower = search.toLowerCase();
                        if (!asset.name.toLowerCase().contains(searchLower)) {
                            return false;
                        }
                    }

                    // Data source filter
                    if (dataSource != null && !dataSource.equals("all")) {
                        if (!catalogName.equalsIgnoreCase(dataSource)) {
                            return false;
                        }
                    }

                    // Asset type filter
                    if (assetType != null && !assetType.equals("all")) {
                        if (!asset.type.equalsIgnoreCase(assetType)) {
                            return false;
                        }
                    }

                    // Status filter
                    if (status != null && !status.equals("all")) {
                        String assetStatus = asset.metadata.has("status") ? asset.metadata.get("status").asText() : "Cataloged";
                        if (!assetStatus.equals(status)) {
                            return false;
                        }
                    }

                    // Date range filter
                    if (dateRange != null && !dateRange.equals("all")) {
                        Instant cutoffDate = getCutoffDate(dateRange);
                        if (asset.createdAt < cutoffDate.toEpochMilli()) {
                            return false;
                        }
                    }

                    return true;
                })
                .collect(Collectors.toList());

            // Apply sorting
            String[] sortParams = sort.split(",");
            String sortField = sortParams[0];
            String sortDirection = sortParams.length > 1 ? sortParams[1] : "asc";

            Comparator<AssetData> comparator = (a1, a2) -> {
                int result = 0;
                switch (sortField) {
                    case "name":
                        result = a1.name.compareTo(a2.name);
                        break;
                    case "type":
                        result = a1.type.compareTo(a2.type);
                        break;
                    case "createdAt":
                        result = Long.compare(a1.createdAt, a2.createdAt);
                        break;
                    default:
                        result = 0;
                }
                return sortDirection.equalsIgnoreCase("desc") ? -result : result;
            };

            filteredAssets.sort(comparator);

            // Apply pagination
            int start = page * pageSize;
            int end = Math.min(start + pageSize, filteredAssets.size());
            List<AssetData> paginatedAssets = start < filteredAssets.size() ? filteredAssets.subList(start, end) : new ArrayList<>();

            // Convert to frontend format
            List<DiscoveredAsset> frontendAssets = paginatedAssets
                .stream()
                .map(asset -> convertToFrontendAsset(asset, catalogName))
                .collect(Collectors.toList());

            // Calculate statistics
            Map<String, Long> fileTypeCounts = new HashMap<>();
            long totalSizeBytes = 0;

            for (AssetData asset : filteredAssets) {
                String fileType = asset.metadata.has("format") ? asset.metadata.get("format").asText() : "Unknown";
                fileTypeCounts.merge(fileType, 1L, Long::sum);

                if (asset.metadata.has("size")) {
                    totalSizeBytes += asset.metadata.get("size").asLong();
                }
            }

            // Prepare response
            Map<String, Object> response = new HashMap<>();
            response.put("content", frontendAssets);
            response.put("totalElements", filteredAssets.size());
            response.put("totalPages", (int) Math.ceil((double) filteredAssets.size() / pageSize));
            response.put("currentPage", page);
            response.put("pageSize", pageSize);

            Map<String, Object> statistics = new HashMap<>();
            statistics.put("fileTypes", fileTypeCounts);
            statistics.put("totalSize", formatSize(totalSizeBytes));
            response.put("statistics", statistics);

            return response;
        } catch (Exception e) {
            log.error("Error getting paginated assets", e);
            throw new RuntimeException("Failed to get paginated assets: " + e.getMessage());
        }
    }

    private Instant getCutoffDate(String dateRange) {
        Instant now = Instant.now();
        switch (dateRange.toLowerCase()) {
            case "today":
                return now.minus(1, ChronoUnit.DAYS);
            case "week":
                return now.minus(7, ChronoUnit.DAYS);
            case "month":
                return now.minus(30, ChronoUnit.DAYS);
            case "year":
                return now.minus(365, ChronoUnit.DAYS);
            default:
                return now.minus(1, ChronoUnit.DAYS);
        }
    }

    private DiscoveredAsset convertToFrontendAsset(AssetData asset, String catalogName) {
        ObjectNode metadata = asset.metadata;

        // Extract schema information if available
        List<SchemaField> schema = new ArrayList<>();
        if (metadata.has("schema")) {
            ArrayNode schemaArray = (ArrayNode) metadata.get("schema");
            for (int i = 0; i < schemaArray.size(); i++) {
                ObjectNode field = (ObjectNode) schemaArray.get(i);
                schema.add(new SchemaField(field.get("name").asText(), field.get("type").asText()));
            }
        }

        // Create asset metadata
        AssetMetadata assetMetadata = new AssetMetadata(
            metadata.has("num_rows") ? metadata.get("num_rows").asLong() : null,
            metadata.has("num_columns") ? metadata.get("num_columns").asInt() : null,
            metadata.has("format") ? metadata.get("format").asText() : "Unknown",
            metadata.has("encoding") ? metadata.get("encoding").asText() : "UTF-8",
            metadata.has("compression") ? metadata.get("compression").asText() : "None"
        );

        // Determine asset quality
        List<String> issues = new ArrayList<>();
        int qualityScore = 90; // Default high score
        if (metadata.has("quality_issues")) {
            ArrayNode qualityIssues = (ArrayNode) metadata.get("quality_issues");
            for (int i = 0; i < qualityIssues.size(); i++) {
                issues.add(qualityIssues.get(i).asText());
            }
            qualityScore = Math.max(50, 90 - (issues.size() * 10)); // Reduce score based on issues
        }

        return new DiscoveredAsset(
            UUID.randomUUID().toString(),
            asset.name,
            catalogName.toUpperCase(),
            asset.type,
            metadata.has("size") ? formatSize(metadata.get("size").asLong()) : "Unknown",
            metadata.has("location") ? metadata.get("location").asText() : "",
            ISO_FORMATTER.format(Instant.ofEpochMilli(asset.createdAt)),
            metadata.has("last_modified")
                ? ISO_FORMATTER.format(Instant.ofEpochMilli(metadata.get("last_modified").asLong()))
                : ISO_FORMATTER.format(Instant.ofEpochMilli(asset.createdAt)),
            "Cataloged",
            metadata.has("owner") ? metadata.get("owner").asText() : "Unknown",
            schema,
            assetMetadata,
            extractTags(metadata),
            new AssetQuality(qualityScore, issues)
        );
    }

    private String formatSize(long bytes) {
        if (bytes < 1024) return bytes + " B";
        int exp = (int) (Math.log(bytes) / Math.log(1024));
        String pre = "KMGTPE".charAt(exp - 1) + "";
        return String.format("%.1f %sB", bytes / Math.pow(1024, exp), pre);
    }

    private List<String> extractTags(ObjectNode metadata) {
        List<String> tags = new ArrayList<>();
        if (metadata.has("tags")) {
            ArrayNode tagsArray = (ArrayNode) metadata.get("tags");
            for (int i = 0; i < tagsArray.size(); i++) {
                tags.add(tagsArray.get(i).asText());
            }
        }
        return tags;
    }

    // Convenience methods for different catalogs
    public Map<String, Object> getAllGcpAssetsForFrontend(
        int page,
        int pageSize,
        String sort,
        String search,
        String dataSource,
        String assetType,
        String status,
        String dateRange
    ) {
        return getPaginatedAssets("GCP", page, pageSize, sort, search, dataSource, assetType, status, dateRange);
    }

    public Map<String, Object> getAllAwsAssetsForFrontend(
        int page,
        int pageSize,
        String sort,
        String search,
        String dataSource,
        String assetType,
        String status,
        String dateRange
    ) {
        return getPaginatedAssets("AWS", page, pageSize, sort, search, dataSource, assetType, status, dateRange);
    }

    public Map<String, Object> getAllAzureAssetsForFrontend(
        int page,
        int pageSize,
        String sort,
        String search,
        String dataSource,
        String assetType,
        String status,
        String dateRange
    ) {
        return getPaginatedAssets("Azure", page, pageSize, sort, search, dataSource, assetType, status, dateRange);
    }

    public Map<String, Object> getAllDatabricksAssetsForFrontend(
        int page,
        int pageSize,
        String sort,
        String search,
        String dataSource,
        String assetType,
        String status,
        String dateRange
    ) {
        return getPaginatedAssets("databricks", page, pageSize, sort, search, dataSource, assetType, status, dateRange);
    }

    public Map<String, Object> getAllSnowflakeAssetsForFrontend(
        int page,
        int pageSize,
        String sort,
        String search,
        String dataSource,
        String assetType,
        String status,
        String dateRange
    ) {
        return getPaginatedAssets("snowflake", page, pageSize, sort, search, dataSource, assetType, status, dateRange);
    }
}
