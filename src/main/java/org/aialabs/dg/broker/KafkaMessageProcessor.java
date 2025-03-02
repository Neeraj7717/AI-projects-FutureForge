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
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.kafka.annotation.KafkaListener;
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
    private String storageBucket;  // Add this to application.properties as "unity.storage.bucket=s3://your-bucket"

    @KafkaListener(topics = "${kafka.topic.name}", groupId = "${kafka.consumer.group-id}")
    public void consumeMessage(String jsonMessage) {
        log.info("Received Kafka message at {}: {}", System.currentTimeMillis(), jsonMessage);

        try {
            Map<String, Object> properties = deserializeMessage(jsonMessage);
            if (properties == null || properties.isEmpty()) {
                log.warn("Invalid or empty Kafka message, skipping processing.");
                return;
            }
            createTablesFromMessage(properties);
        } catch (Exception e) {
            log.error("Error processing Kafka message: {}", e.getMessage(), e);
        }
    }

    private Map<String, Object> deserializeMessage(String jsonMessage) {
        try {
            return objectMapper.readValue(jsonMessage, Map.class);
        } catch (Exception e) {
            log.error("Failed to deserialize Kafka message: {}", e.getMessage(), e);
            return null;
        }
    }

    void createTablesFromMessage(Map<String, Object> properties) throws Exception {
        for (Map.Entry<String, Object> entry : properties.entrySet()) {
            String tableName = entry.getKey();
            String fullTableName = String.format("%s.%s.%s", catalogName, schemaName, tableName);
            String endpoint = BASE_URL + "/tables";
            log.info("Sending POST request to create table: {}", fullTableName);

            // Create properties map with single key-value pair
            Map<String, String> propertiesMap = new HashMap<>();
            propertiesMap.put(entry.getKey(), String.valueOf(entry.getValue()));

            // Construct payload matching the specified format
            Map<String, Object> payloadMap = new HashMap<>();
            payloadMap.put("name", tableName);
            payloadMap.put("catalog_name", catalogName);
            payloadMap.put("schema_name", schemaName);
            payloadMap.put("table_type", "EXTERNAL");
            payloadMap.put("data_source_format", "DELTA");
            payloadMap.put("storage_location", storageBucket + "/tables/" + tableName);
            payloadMap.put("comment", "Table for " + tableName + " data");
            payloadMap.put("properties", propertiesMap);

            // Define columns
            List<Map<String, Object>> columns = new ArrayList<>();
            
            // ID column
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

            // Value column
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

            try {
                ApiResponse response = sendPostRequest(endpoint, payload);
                handleResponse(response, "Table creation for " + tableName);
            } catch (Exception e) {
                log.error("Failed to create table {}: {}", fullTableName, e.getMessage());
            }
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