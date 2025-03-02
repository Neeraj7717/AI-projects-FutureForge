package io.unitycatalog.server.model;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.Map;

public class PatchTableRequest {
  @JsonProperty("comment")
  private String comment;

  @JsonProperty("properties")
  private Map<String, String> properties;

  @JsonProperty("storage_location") // Matches Unity Catalog's snake_case convention
  private String storageLocation;

  public PatchTableRequest() {}

  public String getComment() {
    return comment;
  }

  public PatchTableRequest comment(String comment) {
    this.comment = comment;
    return this;
  }

  public Map<String, String> getProperties() {
    return properties;
  }

  public PatchTableRequest properties(Map<String, String> properties) {
    this.properties = properties;
    return this;
  }

  public String getStorageLocation() {
    return storageLocation;
  }

  public PatchTableRequest storageLocation(String storageLocation) {
    this.storageLocation = storageLocation;
    return this;
  }
}
