package org.aialabs.dg.CatalogCreation;

import java.util.Map;

// POJO class to represent the Kafka message

public class KafkaMessage {

    private String dataAssetUri;
    private Map<String, String> labels;

    // Default constructor for Jackson deserialization
    public KafkaMessage() {}

    // Getters and Setters
    public String getDataAssetUri() {
        return dataAssetUri;
    }

    public void setDataAssetUri(String dataAssetUri) {
        this.dataAssetUri = dataAssetUri;
    }

    public Map<String, String> getLabels() {
        return labels;
    }

    public void setLabels(Map<String, String> labels) {
        this.labels = labels;
    }

    // Helper method to check if the message is for table creation
    public boolean isTableCreationMessage() {
        return dataAssetUri != null && !dataAssetUri.isEmpty();
    }

    // Helper method to check if the message is valid
    public boolean isValid() {
        return labels != null && !labels.isEmpty();
    }

    @Override
    public String toString() {
        return "KafkaMessage{" + "dataAssetUri='" + dataAssetUri + '\'' + ", labels=" + labels + '}';
    }

    public void setTableCreationMessage(boolean b) {
        // TODO Auto-generated method stub
        throw new UnsupportedOperationException("Unimplemented method 'setTableCreationMessage'");
    }
}
