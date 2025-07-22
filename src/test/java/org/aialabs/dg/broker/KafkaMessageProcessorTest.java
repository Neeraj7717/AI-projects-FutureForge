package org.aialabs.dg.broker;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.util.HashMap;
import java.util.Map;
import org.aialabs.dg.CatalogCreation.KafkaMessage;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.test.util.ReflectionTestUtils;

@ExtendWith(MockitoExtension.class)
public class KafkaMessageProcessorTest {

    @Mock
    private KafkaTemplate<String, String> kafkaTemplate;

    @Mock
    private HttpClient httpClient;

    @Mock
    private HttpResponse<Object> httpResponse;

    @InjectMocks
    private KafkaMessageProcessor processor;

    private ObjectMapper objectMapper;

    @BeforeEach
    void setUp() {
        objectMapper = new ObjectMapper();

        // Set private fields using reflection
        ReflectionTestUtils.setField(processor, "catalogName", "test_catalog");
        ReflectionTestUtils.setField(processor, "schemaName", "test_schema");
        ReflectionTestUtils.setField(processor, "storageBucket", "test_bucket");
        ReflectionTestUtils.setField(processor, "outputTopicName", "test_output_topic");
        ReflectionTestUtils.setField(processor, "httpClient", httpClient);

        // Reset mocks
        reset(httpClient, httpResponse, kafkaTemplate);
    }

    @Test
    void testValidMessageDeserialization_TableCreation() throws Exception {
        // Load test data from test-messages.json
        String jsonMessage;
        try (var inputStream = getClass().getClassLoader().getResourceAsStream("test-messages.json")) {
            if (inputStream == null) {
                throw new IllegalStateException("test-messages.json not found in classpath");
            }
            Map<String, Object> jsonMap = objectMapper.readValue(inputStream, Map.class);
            Map<String, Object> validMessage = (Map<String, Object>) jsonMap.get("valid_message");
            jsonMessage = objectMapper.writeValueAsString(validMessage);
        }

        // Mock HTTP responses for table check (exists) and label update
        when(httpResponse.statusCode()).thenReturn(200, 200); // Table exists, update succeeds
        when(httpResponse.body()).thenReturn("{}", "{\"properties\":{\"key1\":\"value1\",\"key2\":\"value2\"}}");
        when(httpClient.send(any(HttpRequest.class), any())).thenReturn(httpResponse);

        // Execute
        processor.consumeMessage(jsonMessage);

        // Verify
        verify(httpClient, times(2)).send(any(HttpRequest.class), any());
        verify(kafkaTemplate, times(1)).send(eq("test_output_topic"), eq("test-table"), anyString());
    }

    @Test
    void testValidMessageDeserialization_Search() throws Exception {
        // Prepare test data for search (no dataAssetUri, triggers search)
        KafkaMessage message = new KafkaMessage();
        Map<String, String> labels = new HashMap<>();
        labels.put("search_key", "search_value");
        message.setLabels(labels);
        // No setDataAssetUri, so isTableCreationMessage() returns false
        String jsonMessage = objectMapper.writeValueAsString(message);

        // Mock HTTP response for search
        when(httpResponse.statusCode()).thenReturn(200);
        when(httpResponse.body()).thenReturn("{\"tables\":[{\"name\":\"test_table\"}]}");
        when(httpClient.send(any(HttpRequest.class), any())).thenReturn(httpResponse);

        // Execute
        processor.consumeMessage(jsonMessage);

        // Verify
        verify(httpClient, times(1)).send(any(HttpRequest.class), any());
        verify(kafkaTemplate, times(1))
            .send(eq("test_output_topic"), eq("search_result_search_key"), eq("{\"tables\":[{\"name\":\"test_table\"}]}"));
    }

    @Test
    void testInvalidMessageDeserialization() {
        // Test with invalid JSON
        String invalidJson = "{invalid_json}";

        // Execute
        processor.consumeMessage(invalidJson);

        // Verify no interactions with mocks
        verifyNoInteractions(httpClient, kafkaTemplate);
    }

    @Test
    void testTableCreation() throws Exception {
        // Prepare test data
        KafkaMessage message = new KafkaMessage();
        Map<String, String> labels = new HashMap<>();
        labels.put("key1", "value1");
        message.setDataAssetUri("s3://test-bucket/new-table.delta");
        message.setLabels(labels);

        // Mock HTTP responses: table doesn't exist, creation succeeds, labels fetched
        when(httpResponse.statusCode()).thenReturn(404, 201, 200);
        when(httpResponse.body()).thenReturn("{}", "{\"success\":true}", "{\"key1\":\"value1\"}");
        when(httpClient.send(any(HttpRequest.class), any())).thenReturn(httpResponse);

        // Execute
        processor.createOrUpdateTableFromMessage(message);

        // Verify
        verify(httpClient, times(3)).send(any(HttpRequest.class), any());
        verify(kafkaTemplate, times(1)).send(eq("test_output_topic"), eq("new-table"), anyString());
    }

    @Test
    void testTableUpdate() throws Exception {
        // Prepare test data
        KafkaMessage message = new KafkaMessage();
        Map<String, String> labels = new HashMap<>();
        labels.put("key1", "value1");
        message.setDataAssetUri("s3://test-bucket/existing-table.delta");
        message.setLabels(labels);

        // Mock HTTP responses: table exists, update succeeds, labels fetched
        when(httpResponse.statusCode()).thenReturn(200, 200, 200);
        when(httpResponse.body()).thenReturn("{}", "{\"success\":true}", "{\"key1\":\"value1\"}");
        when(httpClient.send(any(HttpRequest.class), any())).thenReturn(httpResponse);

        // Execute
        processor.createOrUpdateTableFromMessage(message);

        // Verify
        verify(httpClient, times(3)).send(any(HttpRequest.class), any());
        verify(kafkaTemplate, times(1)).send(eq("test_output_topic"), eq("existing-table"), anyString());
    }

    @Test
    void testSearchTablesByLabels() throws Exception {
        // Prepare test data
        KafkaMessage message = new KafkaMessage();
        Map<String, String> labels = new HashMap<>();
        labels.put("search_key", "search_value");
        message.setLabels(labels);

        // Mock HTTP response
        when(httpResponse.statusCode()).thenReturn(200);
        when(httpResponse.body()).thenReturn("{\"tables\":[{\"name\":\"test_table\"}]}");
        when(httpClient.send(any(HttpRequest.class), any())).thenReturn(httpResponse);

        // Execute
        processor.searchTablesByLabels(message);

        // Verify
        verify(httpClient, times(1)).send(any(HttpRequest.class), any());
        verify(kafkaTemplate, times(1))
            .send(eq("test_output_topic"), eq("search_result_search_key"), eq("{\"tables\":[{\"name\":\"test_table\"}]}"));
    }

    @Test
    void testTableCreationFailure() throws IOException, InterruptedException {
        // Prepare test data
        KafkaMessage message = new KafkaMessage();
        Map<String, String> labels = new HashMap<>();
        labels.put("key1", "value1");
        message.setDataAssetUri("s3://test-bucket/error-table.delta");
        message.setLabels(labels);

        // Mock HTTP responses: table doesn't exist, creation fails
        when(httpResponse.statusCode()).thenReturn(404, 500);
        when(httpResponse.body()).thenReturn("{}", "{\"error\":\"Internal Server Error\"}");
        when(httpClient.send(any(HttpRequest.class), any())).thenReturn(httpResponse);

        // Execute and verify exception
        assertThrows(RuntimeException.class, () -> processor.createOrUpdateTableFromMessage(message));
        verifyNoInteractions(kafkaTemplate); // No message sent on failure
    }

    @Test
    void testEmptyLabelsSearch() {
        // Prepare test data with empty labels
        KafkaMessage message = new KafkaMessage();
        message.setLabels(new HashMap<>());

        // Execute
        processor.searchTablesByLabels(message);

        // Verify no interactions with mocks
        verifyNoInteractions(httpClient, kafkaTemplate);
    }

    @Test
    void testHttpClientTimeout() throws Exception {
        // Prepare test data
        KafkaMessage message = new KafkaMessage();
        Map<String, String> labels = new HashMap<>();
        labels.put("key1", "value1");
        message.setDataAssetUri("s3://test-bucket/timeout-table.delta");
        message.setLabels(labels);

        // Mock HTTP client to throw timeout exception
        when(httpClient.send(any(HttpRequest.class), any())).thenThrow(new java.io.IOException("Connection timeout"));

        // Execute and verify exception
        assertThrows(IOException.class, () -> processor.createOrUpdateTableFromMessage(message));
        verifyNoInteractions(kafkaTemplate);
    }

    @Test
    void testExtractTableNameFromUri() {
        // Test valid URI
        String validUri = "s3://bucket/path/table_name.delta";
        String tableName = processor.extractTableNameFromUri(validUri);
        assertEquals("table_name", tableName);

        // Test invalid URI
        String invalidUri = "invalid_uri";
        String defaultTableName = processor.extractTableNameFromUri(invalidUri);
        assertEquals("default_table", defaultTableName);
    }

    @Test
    void testDeserializeMessage_InvalidJson() {
        // Test invalid JSON
        String invalidJson = "{invalid_json}";
        KafkaMessage result = processor.deserializeMessage(invalidJson);

        // Verify null result
        assertNull(result);
    }
}
