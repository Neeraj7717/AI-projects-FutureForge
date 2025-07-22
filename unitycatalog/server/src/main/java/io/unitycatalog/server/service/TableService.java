package io.unitycatalog.server.service;

import static io.unitycatalog.server.model.SecurableType.CATALOG;
import static io.unitycatalog.server.model.SecurableType.METASTORE;
import static io.unitycatalog.server.model.SecurableType.SCHEMA;
import static io.unitycatalog.server.model.SecurableType.TABLE;

import com.linecorp.armeria.common.HttpResponse;
import com.linecorp.armeria.common.HttpStatus;
import com.linecorp.armeria.server.annotation.Delete;
import com.linecorp.armeria.server.annotation.ExceptionHandler;
import com.linecorp.armeria.server.annotation.Get;
import com.linecorp.armeria.server.annotation.Param;
import com.linecorp.armeria.server.annotation.Patch;
import com.linecorp.armeria.server.annotation.Post;
import com.linecorp.armeria.server.annotation.RequestObject;
import io.unitycatalog.server.auth.UnityCatalogAuthorizer;
import io.unitycatalog.server.auth.annotation.AuthorizeExpression;
import io.unitycatalog.server.auth.annotation.AuthorizeKey;
import io.unitycatalog.server.auth.annotation.AuthorizeKeys;
import io.unitycatalog.server.auth.decorator.UnityAccessEvaluator;
import io.unitycatalog.server.exception.GlobalExceptionHandler;
import io.unitycatalog.server.model.*;
import io.unitycatalog.server.model.CatalogInfo;
import io.unitycatalog.server.model.CreateTable;
import io.unitycatalog.server.model.ListTablesResponse;
import io.unitycatalog.server.model.SchemaInfo;
import io.unitycatalog.server.model.TableInfo;
import io.unitycatalog.server.persist.*;
import io.unitycatalog.server.persist.model.Privileges;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import java.util.stream.Collectors; // Added import for Collectors
import java.util.stream.Stream; // Added import for Stream
import lombok.SneakyThrows;

@ExceptionHandler(GlobalExceptionHandler.class)
public class TableService {

    private final TableRepository tableRepository;
    private final SchemaRepository schemaRepository;
    private final CatalogRepository catalogRepository;
    private final MetastoreRepository metastoreRepository;
    private final UserRepository userRepository;

    private final UnityCatalogAuthorizer authorizer;
    private final UnityAccessEvaluator evaluator;

    @SneakyThrows
    public TableService(UnityCatalogAuthorizer authorizer, Repositories repositories) {
        this.authorizer = authorizer;
        this.evaluator = new UnityAccessEvaluator(authorizer);
        this.tableRepository = repositories.getTableRepository();
        this.schemaRepository = repositories.getSchemaRepository();
        this.catalogRepository = repositories.getCatalogRepository();
        this.metastoreRepository = repositories.getMetastoreRepository();
        this.userRepository = repositories.getUserRepository();
    }

    @Post("")
    @AuthorizeExpression(
        """
            (#authorizeAny(#principal, #catalog, OWNER, USE_CATALOG) && #authorize(#principal, #schema, OWNER)) ||
            (#authorizeAny(#principal, #catalog, OWNER, USE_CATALOG) && #authorizeAll(#principal, #schema, USE_SCHEMA, CREATE_TABLE))
        """
    )
    @AuthorizeKey(METASTORE)
    public HttpResponse createTable(
        @AuthorizeKeys(
            { @AuthorizeKey(value = SCHEMA, key = "schema_name"), @AuthorizeKey(value = CATALOG, key = "catalog_name") }
        ) CreateTable createTable
    ) {
        assert createTable != null;
        TableInfo tableInfo = tableRepository.createTable(createTable);
        initializeAuthorizations(tableInfo);
        return HttpResponse.ofJson(tableInfo);
    }

    @Get("/{full_name}")
    @AuthorizeExpression(
        """
        #authorize(#principal, #metastore, OWNER) ||
        #authorize(#principal, #catalog, OWNER) ||
        (#authorize(#principal, #schema, OWNER) && #authorize(#principal, #catalog, USE_CATALOG)) ||
        (#authorize(#principal, #schema, USE_SCHEMA) && #authorize(#principal, #catalog, USE_CATALOG) && #authorizeAny(#principal, #table, OWNER, SELECT, MODIFY))
        """
    )
    @AuthorizeKey(METASTORE)
    public HttpResponse getTable(@Param("full_name") @AuthorizeKey(TABLE) String fullName) {
        assert fullName != null;
        TableInfo tableInfo = tableRepository.getTable(fullName);
        return HttpResponse.ofJson(tableInfo);
    }

    @Get("")
    @AuthorizeExpression("#defer")
    public HttpResponse listTables(
        @Param("catalog_name") String catalogName,
        @Param("schema_name") String schemaName,
        @Param("max_results") Optional<Integer> maxResults,
        @Param("page_token") Optional<String> pageToken,
        @Param("omit_properties") Optional<Boolean> omitProperties,
        @Param("omit_columns") Optional<Boolean> omitColumns
    ) {
        ListTablesResponse listTablesResponse = tableRepository.listTables(
            catalogName,
            schemaName,
            maxResults,
            pageToken,
            omitProperties.orElse(false),
            omitColumns.orElse(false)
        );

        filterTables(
            """
            #authorize(#principal, #metastore, OWNER) ||
            #authorize(#principal, #catalog, OWNER) ||
            (#authorize(#principal, #schema, OWNER) && #authorize(#principal, #catalog, USE_CATALOG)) ||
            (#authorize(#principal, #schema, USE_SCHEMA) && #authorize(#principal, #catalog, USE_CATALOG) && #authorizeAny(#principal, #table, OWNER, SELECT, MODIFY))
            """,
            listTablesResponse.getTables()
        );

        return HttpResponse.ofJson(listTablesResponse);
    }

    @Get("/search")
    @AuthorizeExpression("#defer")
    public HttpResponse searchTables(
        @Param("search") String searchText,
        @Param("catalog_name") String catalogName,
        @Param("schema_name") String schemaName,
        @Param("max_results") Optional<Integer> maxResults,
        @Param("page_token") Optional<String> pageToken
    ) {
        // Get all tables initially based on catalog and schema
        ListTablesResponse listTablesResponse = tableRepository.listTables(
            catalogName,
            schemaName,
            maxResults,
            pageToken,
            false, // don't omit properties
            true // omit columns to keep response lighter
        );

        // Filter tables based on search text in properties
        List<TableInfo> filteredTables = listTablesResponse
            .getTables()
            .stream()
            .filter(table -> {
                Map<String, String> properties = table.getProperties();
                if (properties != null) {
                    return properties
                        .entrySet()
                        .stream()
                        .anyMatch(entry ->
                            entry.getKey().toLowerCase().contains(searchText.toLowerCase()) ||
                            entry.getValue().toLowerCase().contains(searchText.toLowerCase())
                        );
                }
                return false;
            })
            .collect(Collectors.toList());

        // Apply authorization filtering
        filterTables(
            """
            #authorize(#principal, #metastore, OWNER) ||
            #authorize(#principal, #catalog, OWNER) ||
            (#authorize(#principal, #schema, OWNER) && #authorize(#principal, #catalog, USE_CATALOG)) ||
            (#authorize(#principal, #schema, USE_SCHEMA) && #authorize(#principal, #catalog, USE_CATALOG) && #authorizeAny(#principal, #table, OWNER, SELECT, MODIFY))
            """,
            filteredTables
        );

        // Create response with filtered tables
        ListTablesResponse filteredResponse = new ListTablesResponse();
        filteredResponse.setTables(filteredTables);
        // Preserve pagination if it exists
        if (listTablesResponse.getNextPageToken() != null) {
            filteredResponse.setNextPageToken(listTablesResponse.getNextPageToken());
        }

        return HttpResponse.ofJson(filteredResponse);
    }

    @Get("/labels")
    @AuthorizeExpression("#defer")
    public HttpResponse getTableProperties(
        @Param("catalog_name") String catalogName,
        @Param("schema_name") String schemaName,
        @Param("max_results") Optional<Integer> maxResults,
        @Param("page_token") Optional<String> pageToken
    ) {
        // Fetch all tables in the specified catalog and schema
        ListTablesResponse listTablesResponse = tableRepository.listTables(
            catalogName,
            schemaName,
            maxResults,
            pageToken,
            false, // Do not omit properties
            true // omit columns to focus on properties only
        );

        // Apply authorization filtering (same as listTables)
        filterTables(
            """
            #authorize(#principal, #metastore, OWNER) ||
            #authorize(#principal, #catalog, OWNER) ||
            (#authorize(#principal, #schema, OWNER) && #authorize(#principal, #catalog, USE_CATALOG)) ||
            (#authorize(#principal, #schema, USE_SCHEMA) && #authorize(#principal, #catalog, USE_CATALOG) && #authorizeAny(#principal, #table, OWNER, SELECT, MODIFY))
            """,
            listTablesResponse.getTables()
        );

        // Aggregate all properties into a list of key-value pairs, preserving duplicates
        List<Map<String, String>> allProperties = listTablesResponse
            .getTables()
            .stream()
            .flatMap(table -> {
                Map<String, String> properties = table.getProperties();
                return properties != null
                    ? properties
                        .entrySet()
                        .stream()
                        .map(entry -> {
                            Map<String, String> pair = new HashMap<>();
                            pair.put(entry.getKey(), entry.getValue());
                            return pair;
                        })
                    : Stream.empty();
            })
            .collect(Collectors.toList());

        // Create a response object
        Map<String, Object> response = new HashMap<>();
        response.put("labels", allProperties);
        if (listTablesResponse.getNextPageToken() != null) {
            response.put("next_page_token", listTablesResponse.getNextPageToken());
        }

        return HttpResponse.ofJson(response);
    }

    @Patch("/{full_name}")
    @AuthorizeExpression(
        """
        #authorize(#principal, #metastore, OWNER) ||
        #authorize(#principal, #catalog, OWNER) ||
        (#authorize(#principal, #schema, OWNER) && #authorize(#principal, #catalog, USE_CATALOG)) ||
        (#authorize(#principal, #schema, USE_SCHEMA) && #authorize(#principal, #catalog, USE_CATALOG) && #authorizeAny(#principal, #table, OWNER, MODIFY))
        """
    )
    @AuthorizeKey(METASTORE)
    @SneakyThrows
    public HttpResponse updateTable(@Param("full_name") @AuthorizeKey(TABLE) String fullName, PatchTableRequest patchRequest) {
        assert fullName != null;
        assert patchRequest != null;
        TableInfo updatedTableInfo = tableRepository.updateTable(fullName, patchRequest);
        return HttpResponse.ofJson(updatedTableInfo);
    }

    @Delete("/{full_name}")
    @AuthorizeExpression(
        """
        #authorize(#principal, #catalog, OWNER) ||
        (#authorize(#principal, #schema, OWNER) && #authorize(#principal, #catalog, USE_CATALOG)) ||
        (#authorize(#principal, #schema, USE_SCHEMA) && #authorize(#principal, #catalog, USE_CATALOG) && #authorize(#principal, #table, OWNER))
        """
    )
    public HttpResponse deleteTable(@Param("full_name") @AuthorizeKey(TABLE) String fullName) {
        TableInfo tableInfo = tableRepository.getTable(fullName);
        tableRepository.deleteTable(fullName);
        removeAuthorizations(tableInfo);
        return HttpResponse.of(HttpStatus.OK);
    }

    public void filterTables(String expression, List<TableInfo> entries) {
        UUID principalId = userRepository.findPrincipalId();

        evaluator.filter(
            principalId,
            expression,
            entries,
            ti -> {
                CatalogInfo catalogInfo = catalogRepository.getCatalog(ti.getCatalogName());
                SchemaInfo schemaInfo = schemaRepository.getSchema(ti.getCatalogName() + "." + ti.getSchemaName());
                return Map.of(
                    METASTORE,
                    metastoreRepository.getMetastoreId(),
                    CATALOG,
                    UUID.fromString(catalogInfo.getId()),
                    SCHEMA,
                    UUID.fromString(schemaInfo.getSchemaId()),
                    TABLE,
                    UUID.fromString(ti.getTableId())
                );
            }
        );
    }

    private void initializeAuthorizations(TableInfo tableInfo) {
        SchemaInfo schemaInfo = schemaRepository.getSchema(tableInfo.getCatalogName() + "." + tableInfo.getSchemaName());
        UUID principalId = userRepository.findPrincipalId();
        authorizer.grantAuthorization(principalId, UUID.fromString(tableInfo.getTableId()), Privileges.OWNER);
        authorizer.addHierarchyChild(UUID.fromString(schemaInfo.getSchemaId()), UUID.fromString(tableInfo.getTableId()));
    }

    private void removeAuthorizations(TableInfo tableInfo) {
        SchemaInfo schemaInfo = schemaRepository.getSchema(tableInfo.getCatalogName() + "." + tableInfo.getSchemaName());
        authorizer.clearAuthorizationsForResource(UUID.fromString(tableInfo.getTableId()));
        authorizer.removeHierarchyChild(UUID.fromString(schemaInfo.getSchemaId()), UUID.fromString(tableInfo.getTableId()));
    }
}
