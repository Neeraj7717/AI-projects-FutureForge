package org.aialabs.dg.CatalogCreation;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class UnityCatalogManager {

    private static final Logger log = LoggerFactory.getLogger(UnityCatalogManager.class);

    public void createCatalog(String catalogName) throws Exception {
        String payload = "{\"" + CatalogLiterals.NAME + "\": \"" + catalogName + "\"}";
        log.info("Creating catalog: " + catalogName);
        ApiResponse response = sendPostRequest(CatalogLiterals.CATALOGS_ENDPOINT, payload);
        handleResponse(response, "Catalog");
    }

    public void createSchema(String catalogName, String schemaName) throws Exception {
        String payload =
            "{\"" + CatalogLiterals.NAME + "\": \"" + schemaName + "\", \"" + CatalogLiterals.CATALOG_NAME + "\": \"" + catalogName + "\"}";
        log.info("Creating schema: " + schemaName + " in catalog: " + catalogName);
        ApiResponse response = sendPostRequest(CatalogLiterals.SCHEMAS_ENDPOINT, payload);
        handleResponse(response, "Schema");
    }

    public void createTable(String catalogName, String schemaName, String tableName) throws Exception {
        String payload =
            "{" +
            "\"" +
            CatalogLiterals.NAME +
            "\": \"" +
            tableName +
            "\", " +
            "\"" +
            CatalogLiterals.CATALOG_NAME +
            "\": \"" +
            catalogName +
            "\", " +
            "\"" +
            CatalogLiterals.SCHEMA_NAME +
            "\": \"" +
            schemaName +
            "\", " +
            "\"" +
            CatalogLiterals.TABLE_TYPE +
            "\": \"" +
            CatalogLiterals.EXTERNAL +
            "\", " +
            "\"" +
            CatalogLiterals.DATA_SOURCE_FORMAT +
            "\": \"" +
            CatalogLiterals.DELTA +
            "\", " +
            "\"" +
            CatalogLiterals.COLUMNS +
            "\": [" +
            "    {" +
            "        \"" +
            CatalogLiterals.NAME +
            "\": \"" +
            CatalogLiterals.ID +
            "\", " +
            "        \"" +
            CatalogLiterals.TYPE_TEXT +
            "\": \"" +
            CatalogLiterals.INT +
            "\", " +
            "        \"" +
            CatalogLiterals.TYPE_JSON +
            "\": \"" +
            CatalogLiterals.INT +
            "\", " +
            "        \"" +
            CatalogLiterals.TYPE_NAME +
            "\": \"" +
            CatalogLiterals.INT +
            "\", " +
            "        \"" +
            CatalogLiterals.TYPE_PRECISION +
            "\": 0, " +
            "        \"" +
            CatalogLiterals.TYPE_SCALE +
            "\": 0, " +
            "        \"" +
            CatalogLiterals.TYPE_INTERVAL_TYPE +
            "\": \"\", " +
            "        \"" +
            CatalogLiterals.POSITION +
            "\": 0, " +
            "        \"" +
            CatalogLiterals.COMMENT +
            "\": \"" +
            CatalogLiterals.PRIMARY_KEY_COLUMN +
            "\", " +
            "        \"" +
            CatalogLiterals.NULLABLE +
            "\": false, " +
            "        \"" +
            CatalogLiterals.PARTITION_INDEX +
            "\": 0" +
            "    }," +
            "    {" +
            "        \"" +
            CatalogLiterals.NAME +
            "\": \"" +
            CatalogLiterals.NAME +
            "\", " +
            "        \"" +
            CatalogLiterals.TYPE_TEXT +
            "\": \"" +
            CatalogLiterals.STRING +
            "\", " +
            "        \"" +
            CatalogLiterals.TYPE_JSON +
            "\": \"" +
            CatalogLiterals.STRING +
            "\", " +
            "        \"" +
            CatalogLiterals.TYPE_NAME +
            "\": \"" +
            CatalogLiterals.STRING +
            "\", " +
            "        \"" +
            CatalogLiterals.TYPE_PRECISION +
            "\": 0, " +
            "        \"" +
            CatalogLiterals.TYPE_SCALE +
            "\": 0, " +
            "        \"" +
            CatalogLiterals.TYPE_INTERVAL_TYPE +
            "\": \"\", " +
            "        \"" +
            CatalogLiterals.POSITION +
            "\": 1, " +
            "        \"" +
            CatalogLiterals.COMMENT +
            "\": \"" +
            CatalogLiterals.NAME_OF_ENTITY +
            "\", " +
            "        \"" +
            CatalogLiterals.NULLABLE +
            "\": true, " +
            "        \"" +
            CatalogLiterals.PARTITION_INDEX +
            "\": 0" +
            "    }" +
            "]," +
            "\"" +
            CatalogLiterals.STORAGE_LOCATION +
            "\": \"s3://your-bucket/path/to/table\", " +
            "\"" +
            CatalogLiterals.COMMENT +
            "\": \"Sample external table\", " +
            "\"" +
            CatalogLiterals.PROPERTIES +
            "\": {" +
            "    \"" +
            CatalogLiterals.ADDITIONAL_PROP1 +
            "\": \"" +
            CatalogLiterals.VALUE1 +
            "\", " +
            "    \"" +
            CatalogLiterals.ADDITIONAL_PROP2 +
            "\": \"" +
            CatalogLiterals.VALUE2 +
            "\", " +
            "    \"" +
            CatalogLiterals.ADDITIONAL_PROP3 +
            "\": \"" +
            CatalogLiterals.VALUE3 +
            "\"" +
            "}" +
            "}";

        log.info("Creating table: " + tableName + " in schema: " + schemaName + " and catalog: " + catalogName);
        ApiResponse response = sendPostRequest(CatalogLiterals.TABLES_ENDPOINT, payload);
        handleResponse(response, "Table");
    }

    static ApiResponse sendPostRequest(String endpoint, String payload) throws Exception {
        HttpURLConnection conn = null;
        try {
            URL url = new URL(endpoint);
            conn = (HttpURLConnection) url.openConnection();
            conn.setRequestMethod("POST");
            conn.setRequestProperty("Content-Type", "application/json");
            conn.setRequestProperty("Accept", "application/json");
            conn.setDoOutput(true);

            // Write request payload
            try (OutputStream os = conn.getOutputStream()) {
                byte[] input = payload.getBytes(StandardCharsets.UTF_8);
                os.write(input, 0, input.length);
            }

            // Read response
            int responseCode = conn.getResponseCode();
            String responseBody;
            try (
                BufferedReader br = new BufferedReader(
                    new InputStreamReader(responseCode < 400 ? conn.getInputStream() : conn.getErrorStream(), StandardCharsets.UTF_8)
                )
            ) {
                StringBuilder response = new StringBuilder();
                String responseLine;
                while ((responseLine = br.readLine()) != null) {
                    response.append(responseLine.trim());
                }
                responseBody = response.toString();
            }

            return new ApiResponse(responseCode, responseBody);
        } finally {
            if (conn != null) {
                conn.disconnect();
            }
        }
    }

    void handleResponse(ApiResponse response, String resourceType) {
        if (response.getStatusCode() == HttpURLConnection.HTTP_OK || response.getStatusCode() == HttpURLConnection.HTTP_CREATED) {
            log.info(resourceType + " created successfully. Response: " + response.getResponseBody());
        } else {
            log.info(
                "Failed to create " + resourceType + ". Status Code: " + response.getStatusCode() + ", Error: " + response.getResponseBody()
            );
            throw new RuntimeException("Failed to create " + resourceType + ": " + response.getResponseBody());
        }
    }

    // Helper class to store API response
    static class ApiResponse {

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
