package org.aialabs.dg.service;

import java.util.HashMap;
import java.util.Map;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Service;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.HttpServerErrorException;
import org.springframework.web.client.RestTemplate;

@Service
public class UnityCatalogService {

    private final RestTemplate restTemplate;
    private final String unityCatalogBaseUrl = "http://localhost:8080"; // Updated to correct port

    public UnityCatalogService(RestTemplate restTemplate) {
        this.restTemplate = restTemplate;
    }

    // List all catalogs
    public String listCatalogs() {
        String url = unityCatalogBaseUrl + "/api/2.1/unity-catalog/catalogs";
        try {
            ResponseEntity<String> response = restTemplate.getForEntity(url, String.class);
            return response.getBody();
        } catch (HttpClientErrorException | HttpServerErrorException e) {
            throw new RuntimeException("Failed to list catalogs: " + e.getResponseBodyAsString(), e);
        }
    }

    // Create a new catalog
    public String createCatalog(String catalogName) {
        String url = unityCatalogBaseUrl + "/api/2.1/unity-catalog/catalogs";
        Map<String, String> request = new HashMap<>();
        request.put("catalog_name", catalogName);

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        HttpEntity<Map<String, String>> entity = new HttpEntity<>(request, headers);

        try {
            ResponseEntity<String> response = restTemplate.postForEntity(url, entity, String.class);
            return response.getBody();
        } catch (HttpClientErrorException | HttpServerErrorException e) {
            throw new RuntimeException("Failed to create catalog: " + e.getResponseBodyAsString(), e);
        }
    }

    // List schemas in a catalog
    public String listSchemas(String catalogName) {
        String url = unityCatalogBaseUrl + "/api/2.1/unity-catalog/schemas?catalog_name=" + catalogName;
        try {
            ResponseEntity<String> response = restTemplate.getForEntity(url, String.class);
            return response.getBody();
        } catch (HttpClientErrorException | HttpServerErrorException e) {
            throw new RuntimeException("Failed to list schemas: " + e.getResponseBodyAsString(), e);
        }
    }

    // Create a new schema in a catalog
    public String createSchema(String catalogName, String schemaName) {
        String url = unityCatalogBaseUrl + "/api/2.1/unity-catalog/schemas";
        Map<String, String> request = new HashMap<>();
        request.put("catalog_name", catalogName);
        request.put("name", schemaName);

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        HttpEntity<Map<String, String>> entity = new HttpEntity<>(request, headers);

        try {
            ResponseEntity<String> response = restTemplate.postForEntity(url, entity, String.class);
            return response.getBody();
        } catch (HttpClientErrorException | HttpServerErrorException e) {
            throw new RuntimeException("Failed to create schema: " + e.getResponseBodyAsString(), e);
        }
    }

    // List tables in a schema (Fixed Endpoint)
    public String listTables(String catalogName, String schemaName) {
        String url = unityCatalogBaseUrl + "/api/2.1/unity-catalog/tables?catalog_name=" + catalogName + "&schema_name=" + schemaName;
        try {
            ResponseEntity<String> response = restTemplate.getForEntity(url, String.class);
            return response.getBody();
        } catch (HttpClientErrorException | HttpServerErrorException e) {
            throw new RuntimeException("Failed to list tables: " + e.getResponseBodyAsString(), e);
        }
    }

    // Create a new table in a schema
    public String createTable(String catalogName, String schemaName, String tableName) {
        String url = unityCatalogBaseUrl + "/api/2.1/unity-catalog/tables";
        Map<String, Object> request = new HashMap<>();
        request.put("catalog_name", catalogName);
        request.put("schema_name", schemaName);
        request.put("name", tableName);
        request.put("columns", new Object[] { Map.of("name", "id", "type", "INT"), Map.of("name", "name", "type", "STRING") });

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        HttpEntity<Map<String, Object>> entity = new HttpEntity<>(request, headers);

        try {
            ResponseEntity<String> response = restTemplate.postForEntity(url, entity, String.class);
            return response.getBody();
        } catch (HttpClientErrorException | HttpServerErrorException e) {
            throw new RuntimeException("Failed to create table: " + e.getResponseBodyAsString(), e);
        }
    }
}
