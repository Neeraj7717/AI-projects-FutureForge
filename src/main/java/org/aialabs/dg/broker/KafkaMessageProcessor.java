package org.aialabs.dg.broker;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import org.aialabs.dg.CatalogCreation.KafkaMessage;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Service;

@Service
public class KafkaMessageProcessor {

    private final Logger log = LoggerFactory.getLogger(KafkaMessageProcessor.class);
    private final ObjectMapper objectMapper = new ObjectMapper();
    private static final String BASE_URL = "http://localhost:8080/api/2.1/unity-catalog";
    private final HttpClient httpClient = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(10)).build();

    @Value("${unity.catalog.name}")
    private String catalogName;

    @Value("${unity.catalog.schema.name}")
    private String schemaName;

    @Value("${unity.storage.bucket}")
    private String storageBucket;

    @Value("${kafka.output.topic.name}")
    private String outputTopicName;

    private final KafkaTemplate<String, String> kafkaTemplate;

    public KafkaMessageProcessor(KafkaTemplate<String, String> kafkaTemplate) {
        this.kafkaTemplate = kafkaTemplate;
    }

    @KafkaListener(topics = "${kafka.topic.name}", groupId = "${kafka.consumer.group-id}")
    public void consumeMessage(String jsonMessage) {
        log.info("Received Kafka message at {}: {}", System.currentTimeMillis(), jsonMessage);

        try {
            KafkaMessage message = deserializeMessage(jsonMessage);
            if (message == null || !message.isValid()) {
                log.warn("Invalid or empty Kafka message or missing labels, skipping processing: {}", jsonMessage);
                return;
            }

            if (message.isTableCreationMessage()) {
                createOrUpdateTableFromMessage(message);
            } else {
                searchTablesByLabels(message);
            }
        } catch (Exception e) {
            log.error("Error processing Kafka message: {}", e.getMessage(), e);
        }
    }

    KafkaMessage deserializeMessage(String jsonMessage) {
        try {
            return objectMapper.readValue(jsonMessage, KafkaMessage.class);
        } catch (Exception e) {
            log.error("Failed to deserialize Kafka message: {}", e.getMessage(), e);
            return null;
        }
    }

    void createOrUpdateTableFromMessage(KafkaMessage message) throws Exception {
        String dataAssetUri = message.getDataAssetUri();
        String tableName = extractTableNameFromUri(dataAssetUri);
        String fullTableName = String.format("%s.%s.%s", catalogName, schemaName, tableName);

        // Check if table exists
        boolean tableExists = checkTableExists(tableName);

        if (tableExists) {
            // Update existing table with labels
            updateTableLabels(tableName, message.getLabels());
        } else {
            // Create new table
            createTable(tableName, dataAssetUri, message.getLabels());
        }

        // Fetch and send updated labels to Kafka
        Map<String, String> fetchedLabels = fetchLabelsFromEndpoint(tableName);
        sendLabelsToKafka(fetchedLabels, tableName);
    }

    private boolean checkTableExists(String tableName) {
        String endpoint = String.format("%s/tables/%s.%s.%s", BASE_URL, catalogName, schemaName, tableName);

        try {
            HttpRequest request = HttpRequest
                .newBuilder()
                .uri(URI.create(endpoint))
                .header("Accept", "application/json")
                .GET()
                .timeout(Duration.ofSeconds(10))
                .build();

            HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
            return response.statusCode() == 200;
        } catch (Exception e) {
            log.info("Table {} does not exist or error checking existence: {}", tableName, e.getMessage());
            return false;
        }
    }

    private void createTable(String tableName, String dataAssetUri, Map<String, String> labels) throws Exception {
        String fullTableName = String.format("%s.%s.%s", catalogName, schemaName, tableName);
        String endpoint = BASE_URL + "/tables";
        log.info("Sending POST request to create table: {}", fullTableName);

        Map<String, Object> payloadMap = new HashMap<>();
        payloadMap.put("name", tableName);
        payloadMap.put("catalog_name", catalogName);
        payloadMap.put("schema_name", schemaName);
        payloadMap.put("table_type", "EXTERNAL");
        payloadMap.put("data_source_format", "DELTA");
        payloadMap.put("storage_location", dataAssetUri);
        payloadMap.put("comment", "Table for " + tableName + " data");
        payloadMap.put("properties", labels);

        List<Map<String, Object>> columns = new ArrayList<>();
        Map<String, Object> idColumn = new HashMap<>();
        idColumn.put("name", "id");
        idColumn.put("type_text", "INT");
        idColumn.put("type_json", "INT");
        idColumn.put("type_name", "INT");
        idColumn.put("type_precision", 0);
        idColumn.put("type_scale", 0);
        idColumn.put("type_interval_type", "");
        idColumn.put("position", 0);
        idColumn.put("comment", "Primary key column");
        idColumn.put("nullable", false);
        idColumn.put("partition_index", 0);
        columns.add(idColumn);

        Map<String, Object> valueColumn = new HashMap<>();
        valueColumn.put("name", "value");
        valueColumn.put("type_text", "STRING");
        valueColumn.put("type_json", "STRING");
        valueColumn.put("type_name", "STRING");
        valueColumn.put("type_precision", 0);
        valueColumn.put("type_scale", 0);
        valueColumn.put("type_interval_type", "");
        valueColumn.put("position", 1);
        valueColumn.put("comment", "Value for " + tableName);
        valueColumn.put("nullable", true);
        valueColumn.put("partition_index", 0);
        columns.add(valueColumn);

        payloadMap.put("columns", columns);

        String payload = objectMapper.writeValueAsString(payloadMap);
        log.info("Creating table: {} with payload: {}", fullTableName, payload);

        ApiResponse response = sendPostRequest(endpoint, payload);
        handleResponse(response, "Table creation for " + tableName);
    }

    private void updateTableLabels(String tableName, Map<String, String> labels) throws Exception {
        String fullTableName = String.format("%s.%s.%s", catalogName, schemaName, tableName);
        String endpoint = String.format("%s/tables/%s.%s.%s", BASE_URL, catalogName, schemaName, tableName);
        log.info("Sending PATCH request to update labels for table: {}", fullTableName);

        Map<String, Object> payloadMap = new HashMap<>();
        payloadMap.put("properties", labels);

        String payload = objectMapper.writeValueAsString(payloadMap);
        log.info("Updating labels for table: {} with payload: {}", fullTableName, payload);

        HttpRequest request = HttpRequest
            .newBuilder()
            .uri(URI.create(endpoint))
            .header("Content-Type", "application/json")
            .header("Accept", "application/json")
            .method("PATCH", HttpRequest.BodyPublishers.ofString(payload))
            .timeout(Duration.ofSeconds(15))
            .build();

        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
        ApiResponse apiResponse = new ApiResponse(response.statusCode(), response.body());
        handleResponse(apiResponse, "Table label update for " + tableName);
    }

    void searchTablesByLabels(KafkaMessage message) {
        Map<String, String> labels = message.getLabels();

        // Use the first key or value as the search term
        String searchTerm = labels.isEmpty()
            ? ""
            : (labels.keySet().iterator().hasNext() ? labels.keySet().iterator().next() : labels.values().iterator().next());

        if (searchTerm.isEmpty()) {
            log.warn("No labels provided for search, skipping.");
            return;
        }

        String searchEndpoint = String.format(
            "%s/tables/search?search=%s&catalog_name=%s&schema_name=%s",
            BASE_URL,
            searchTerm,
            catalogName,
            schemaName
        );
        log.info("Searching tables with endpoint: {}", searchEndpoint);

        try {
            HttpRequest request = HttpRequest
                .newBuilder()
                .uri(URI.create(searchEndpoint))
                .header("Accept", "application/json")
                .GET()
                .timeout(Duration.ofSeconds(10))
                .build();

            HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
            log.info("Search response: status={}, body={}", response.statusCode(), response.body());

            if (response.statusCode() == 200) {
                String key = "search_result_" + searchTerm;
                kafkaTemplate.send(outputTopicName, key, response.body());
                log.info("Sent search result to Kafka topic {} with key {}: {}", outputTopicName, key, response.body());
            } else {
                log.warn("Failed to search tables. Status: {}", response.statusCode());
            }
        } catch (Exception e) {
            log.error("Error searching tables with labels {}: {}", labels, e.getMessage(), e);
        }
    }

    private Map<String, String> fetchLabelsFromEndpoint(String tableName) {
        String labelsEndpoint = String.format(
            "%s/tables/labels?table_name=%s&catalog_name=%s&schema_name=%s",
            BASE_URL,
            tableName,
            catalogName,
            schemaName
        );
        try {
            HttpRequest request = HttpRequest
                .newBuilder()
                .uri(URI.create(labelsEndpoint))
                .header("Accept", "application/json")
                .GET()
                .timeout(Duration.ofSeconds(10))
                .build();

            HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
            log.info("Fetched labels from endpoint: status={}, body={}", response.statusCode(), response.body());

            if (response.statusCode() == 200) {
                @SuppressWarnings("unchecked")
                Map<String, String> labels = objectMapper.readValue(response.body(), Map.class);
                return labels;
            } else {
                log.warn("Failed to fetch labels for table {}. Status: {}", tableName, response.statusCode());
                return new HashMap<>();
            }
        } catch (Exception e) {
            log.error("Error fetching labels for table {}: {}", tableName, e.getMessage(), e);
            return new HashMap<>();
        }
    }

    private void sendLabelsToKafka(Map<String, String> labels, String tableName) {
        try {
            String labelsJson = objectMapper.writeValueAsString(labels);
            kafkaTemplate.send(outputTopicName, tableName, labelsJson);
            log.info("Sent labels to Kafka topic {} for table {}: {}", outputTopicName, tableName, labelsJson);
        } catch (Exception e) {
            log.error("Failed to send labels to Kafka topic {} for table {}: {}", outputTopicName, tableName, e.getMessage(), e);
        }
    }

    String extractTableNameFromUri(String dataAssetUri) {
        try {
            String[] parts = dataAssetUri.split("/");
            String fileNameWithExt = parts[parts.length - 1];
            String tableName = fileNameWithExt.substring(0, fileNameWithExt.lastIndexOf("."));
            return tableName.isEmpty() ? "default_table" : tableName;
        } catch (Exception e) {
            log.error("Failed to extract table name from URI: {}. Using default name.", dataAssetUri, e);
            return "default_table";
        }
    }

    private ApiResponse sendPostRequest(String endpoint, String payload) throws Exception {
        HttpRequest request = HttpRequest
            .newBuilder()
            .uri(URI.create(endpoint))
            .header("Content-Type", "application/json")
            .header("Accept", "application/json")
            .POST(HttpRequest.BodyPublishers.ofString(payload))
            .timeout(Duration.ofSeconds(15))
            .build();

        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
        log.info("Response: status={}, body={}", response.statusCode(), response.body());
        return new ApiResponse(response.statusCode(), response.body());
    }

    private void handleResponse(ApiResponse response, String operation) {
        if (response.getStatusCode() == 200 || response.getStatusCode() == 201) {
            log.info("{} succeeded. Response: {}", operation, response.getResponseBody());
        } else {
            log.error("{} failed. Status Code: {}, Error: {}", operation, response.getStatusCode(), response.getResponseBody());
            throw new RuntimeException(
                operation + " failed: Status: " + response.getStatusCode() + ", Error: " + response.getResponseBody()
            );
        }
    }

    private static class ApiResponse {

        private final int statusCode;
        private final String responseBody;

        public ApiResponse(int statusCode, String responseBody) {
            this.statusCode = statusCode;
            this.responseBody = responseBody;
        }

        public int getStatusCode() {
            return statusCode;
        }

        public String getResponseBody() {
            return responseBody;
        }
    }
}
