package org.aialabs.dg.CatalogCreation;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

public class SearchTags {

    private Map<String, List<String>> tableTags; // Map of table names to their tags

    public SearchTags(Map<String, List<String>> tableTags) {
        this.tableTags = tableTags;
    }

    public List<String> searchTablesByTag(String tag) {
        List<String> result = new ArrayList<>();
        for (Map.Entry<String, List<String>> entry : tableTags.entrySet()) {
            if (entry.getValue().contains(tag)) {
                result.add(entry.getKey());
            }
        }
        return result;
    }
}
