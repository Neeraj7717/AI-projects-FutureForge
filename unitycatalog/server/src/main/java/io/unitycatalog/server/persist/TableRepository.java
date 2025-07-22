package io.unitycatalog.server.persist;

import io.unitycatalog.server.exception.BaseException;
import io.unitycatalog.server.exception.ErrorCode;
import io.unitycatalog.server.model.*;
import io.unitycatalog.server.persist.dao.CatalogInfoDAO;
import io.unitycatalog.server.persist.dao.PropertyDAO;
import io.unitycatalog.server.persist.dao.SchemaInfoDAO;
import io.unitycatalog.server.persist.dao.TableInfoDAO;
import io.unitycatalog.server.persist.utils.FileOperations;
import io.unitycatalog.server.persist.utils.PagedListingHelper;
import io.unitycatalog.server.persist.utils.RepositoryUtils;
import io.unitycatalog.server.utils.Constants;
import io.unitycatalog.server.utils.IdentityUtils;
import io.unitycatalog.server.utils.ValidationUtils;
import java.util.*;
import java.util.stream.Collectors;
import org.hibernate.Session;
import org.hibernate.SessionFactory;
import org.hibernate.Transaction;
import org.hibernate.query.Query;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class TableRepository {

    private static final Logger LOGGER = LoggerFactory.getLogger(TableRepository.class);
    private final SessionFactory sessionFactory;
    private final Repositories repositories;
    private final FileOperations fileOperations;
    private static final PagedListingHelper<TableInfoDAO> LISTING_HELPER = new PagedListingHelper<>(TableInfoDAO.class);

    public TableRepository(Repositories repositories, SessionFactory sessionFactory) {
        this.repositories = repositories;
        this.sessionFactory = sessionFactory;
        this.fileOperations = repositories.getFileOperations();
    }

    public TableInfo getTableById(String tableId) {
        LOGGER.debug("Getting table by id: {}", tableId);
        try (Session session = sessionFactory.openSession()) {
            session.setDefaultReadOnly(true);
            Transaction tx = session.beginTransaction();
            try {
                TableInfoDAO tableInfoDAO = session.get(TableInfoDAO.class, UUID.fromString(tableId));
                if (tableInfoDAO == null) {
                    throw new BaseException(ErrorCode.NOT_FOUND, "Table not found: " + tableId);
                }
                SchemaInfoDAO schemaInfoDAO = session.get(SchemaInfoDAO.class, tableInfoDAO.getSchemaId());
                if (schemaInfoDAO == null) {
                    throw new BaseException(ErrorCode.NOT_FOUND, "Schema not found: " + tableInfoDAO.getSchemaId());
                }
                CatalogInfoDAO catalogInfoDAO = session.get(CatalogInfoDAO.class, schemaInfoDAO.getCatalogId());
                if (catalogInfoDAO == null) {
                    throw new BaseException(ErrorCode.NOT_FOUND, "Catalog not found: " + schemaInfoDAO.getCatalogId());
                }
                TableInfo tableInfo = tableInfoDAO.toTableInfo(true);
                tableInfo.setSchemaName(schemaInfoDAO.getName());
                tableInfo.setCatalogName(catalogInfoDAO.getName());
                tx.commit();
                return tableInfo;
            } catch (Exception e) {
                if (tx != null && tx.getStatus().canRollback()) {
                    tx.rollback();
                }
                throw e;
            }
        }
    }

    public TableInfo getTable(String fullName) {
        LOGGER.debug("Getting table: {}", fullName);
        try (Session session = sessionFactory.openSession()) {
            session.setDefaultReadOnly(true);
            Transaction tx = session.beginTransaction();
            try {
                String[] parts = fullName.split("\\.");
                if (parts.length != 3) {
                    throw new BaseException(ErrorCode.INVALID_ARGUMENT, "Invalid table name: " + fullName);
                }
                String catalogName = parts[0];
                String schemaName = parts[1];
                String tableName = parts[2];
                TableInfoDAO tableInfoDAO = findTable(session, catalogName, schemaName, tableName);
                if (tableInfoDAO == null) {
                    throw new BaseException(ErrorCode.NOT_FOUND, "Table not found: " + fullName);
                }
                TableInfo tableInfo = tableInfoDAO.toTableInfo(true);
                tableInfo.setCatalogName(catalogName);
                tableInfo.setSchemaName(schemaName);
                RepositoryUtils.attachProperties(tableInfo, tableInfo.getTableId(), Constants.TABLE, session);
                tx.commit();
                return tableInfo;
            } catch (Exception e) {
                if (tx != null && tx.getStatus().canRollback()) {
                    tx.rollback();
                }
                throw e;
            }
        }
    }

    public TableInfo updateTable(String fullName, PatchTableRequest patchRequest) throws Exception {
        LOGGER.debug("Updating table: {}", fullName);
        try (Session session = sessionFactory.openSession()) {
            Transaction tx = session.beginTransaction();
            try {
                String[] parts = fullName.split("\\.");
                if (parts.length != 3) {
                    throw new BaseException(ErrorCode.INVALID_ARGUMENT, "Invalid table name: " + fullName);
                }
                String catalogName = parts[0];
                String schemaName = parts[1];
                String tableName = parts[2];

                UUID schemaId = getSchemaId(session, catalogName, schemaName);
                TableInfoDAO tableInfoDAO = findBySchemaIdAndName(session, schemaId, tableName);
                if (tableInfoDAO == null) {
                    throw new BaseException(ErrorCode.NOT_FOUND, "Table not found: " + fullName);
                }
                LOGGER.debug("Found table with ID: {}", tableInfoDAO.getId());

                boolean updated = false;
                if (patchRequest != null) {
                    if (patchRequest.getComment() != null) {
                        tableInfoDAO.setComment(patchRequest.getComment());
                        updated = true;
                    }

                    if (patchRequest.getProperties() != null) {
                        List<PropertyDAO> existingProperties = PropertyRepository.findProperties(
                            session,
                            tableInfoDAO.getId(),
                            Constants.TABLE
                        );
                        Map<String, PropertyDAO> existingPropMap = existingProperties
                            .stream()
                            .collect(Collectors.toMap(PropertyDAO::getKey, p -> p));
                        LOGGER.debug("Existing properties before update: {}", existingPropMap.keySet());

                        Map<String, String> requestProperties = patchRequest.getProperties();
                        LOGGER.debug("Requested properties to merge: {}", requestProperties.keySet());

                        for (Map.Entry<String, String> entry : requestProperties.entrySet()) {
                            String key = entry.getKey();
                            String value = entry.getValue();
                            PropertyDAO existingProp = existingPropMap.get(key);

                            if (existingProp != null) {
                                if (!Objects.equals(value, existingProp.getValue())) {
                                    LOGGER.debug("Updating existing property: {} = {}", key, value);
                                    existingProp.setValue(value);
                                    session.merge(existingProp);
                                    updated = true;
                                }
                            } else {
                                LOGGER.debug("Adding new property: {} = {}", key, value);
                                PropertyDAO newProp = PropertyDAO
                                    .builder()
                                    .id(UUID.randomUUID())
                                    .entityId(tableInfoDAO.getId())
                                    .entityType(Constants.TABLE)
                                    .key(key)
                                    .value(value)
                                    .build();
                                session.merge(newProp);
                                updated = true;
                            }
                        }
                        LOGGER.debug("Properties after processing: {}", requestProperties);
                    }

                    if (patchRequest.getStorageLocation() != null) {
                        if (TableType.MANAGED.equals(tableInfoDAO.getType())) {
                            throw new BaseException(ErrorCode.INVALID_ARGUMENT, "Cannot update storage location for MANAGED tables");
                        }
                        tableInfoDAO.setUrl(FileOperations.convertRelativePathToURI(patchRequest.getStorageLocation()));
                        updated = true;
                    }

                    if (updated) {
                        String callerId = IdentityUtils.findPrincipalEmailAddress();
                        tableInfoDAO.setUpdatedAt(new Date());
                        tableInfoDAO.setUpdatedBy(callerId);
                        session.merge(tableInfoDAO);
                        session.flush();
                        LOGGER.debug("Table and properties updated in DB: {}", tableInfoDAO.getId());
                    }
                }

                TableInfo updatedTableInfo = tableInfoDAO.toTableInfo(true);
                updatedTableInfo.setCatalogName(catalogName);
                updatedTableInfo.setSchemaName(schemaName);
                RepositoryUtils.attachProperties(updatedTableInfo, tableInfoDAO.getId().toString(), Constants.TABLE, session);
                LOGGER.debug("Properties after update: {}", updatedTableInfo.getProperties());

                tx.commit();
                LOGGER.debug("Transaction committed for table: {}", fullName);
                return updatedTableInfo;
            } catch (Exception e) {
                if (tx != null && tx.getStatus().canRollback()) {
                    tx.rollback();
                    LOGGER.error("Transaction rolled back for table: {}", fullName, e);
                }
                LOGGER.error("Error updating table: {}", fullName, e);
                throw e instanceof BaseException
                    ? e
                    : new BaseException(ErrorCode.INTERNAL, "Error updating table: " + fullName + ". Cause: " + e.getMessage(), e);
            }
        }
    }

    public String getTableUniformMetadataLocation(Session session, String catalogName, String schemaName, String tableName) {
        TableInfoDAO dao = findTable(session, catalogName, schemaName, tableName);
        return dao.getUniformIcebergMetadataLocation();
    }

    private TableInfoDAO findTable(Session session, String catalogName, String schemaName, String tableName) {
        UUID schemaId = getSchemaId(session, catalogName, schemaName);
        return findBySchemaIdAndName(session, schemaId, tableName);
    }

    public TableInfo createTable(CreateTable createTable) {
        ValidationUtils.validateSqlObjectName(createTable.getName());
        String callerId = IdentityUtils.findPrincipalEmailAddress();
        List<ColumnInfo> columnInfos = createTable
            .getColumns()
            .stream()
            .map(c -> c.typeText(c.getTypeText().toLowerCase(Locale.ROOT)))
            .collect(Collectors.toList());
        Long createTime = System.currentTimeMillis();
        TableInfo tableInfo = new TableInfo()
            .tableId(UUID.randomUUID().toString())
            .name(createTable.getName())
            .catalogName(createTable.getCatalogName())
            .schemaName(createTable.getSchemaName())
            .tableType(createTable.getTableType())
            .dataSourceFormat(createTable.getDataSourceFormat())
            .columns(columnInfos)
            .storageLocation(FileOperations.convertRelativePathToURI(createTable.getStorageLocation()))
            .comment(createTable.getComment())
            .properties(createTable.getProperties())
            .owner(callerId)
            .createdAt(createTime)
            .createdBy(callerId)
            .updatedAt(createTime)
            .updatedBy(callerId);
        String fullName = getTableFullName(tableInfo);
        LOGGER.debug("Creating table: {}", fullName);

        Transaction tx;
        try (Session session = sessionFactory.openSession()) {
            String catalogName = tableInfo.getCatalogName();
            String schemaName = tableInfo.getSchemaName();
            UUID schemaId = getSchemaId(session, catalogName, schemaName);
            tx = session.beginTransaction();

            try {
                TableInfoDAO existingTable = findBySchemaIdAndName(session, schemaId, tableInfo.getName());
                if (existingTable != null) {
                    throw new BaseException(ErrorCode.ALREADY_EXISTS, "Table already exists: " + fullName);
                }
                if (TableType.MANAGED.equals(tableInfo.getTableType())) {
                    throw new BaseException(ErrorCode.INVALID_ARGUMENT, "MANAGED table creation is not supported yet.");
                }
                if (tableInfo.getStorageLocation() == null) {
                    throw new BaseException(ErrorCode.INVALID_ARGUMENT, "Storage location is required for external table");
                }
                TableInfoDAO tableInfoDAO = TableInfoDAO.from(tableInfo);
                tableInfoDAO.setSchemaId(schemaId);
                tableInfoDAO
                    .getColumns()
                    .forEach(c -> {
                        c.setId(UUID.randomUUID());
                        c.setTable(tableInfoDAO);
                    });
                PropertyDAO.from(tableInfo.getProperties(), tableInfoDAO.getId(), Constants.TABLE).forEach(session::persist);
                session.persist(tableInfoDAO);
                tx.commit();
            } catch (RuntimeException e) {
                if (tx != null && tx.getStatus().canRollback()) {
                    tx.rollback();
                }
                throw e;
            }
        } catch (RuntimeException e) {
            if (e instanceof BaseException) {
                throw e;
            }
            throw new BaseException(ErrorCode.INTERNAL, "Error creating table: " + fullName + ". " + e.getMessage(), e);
        }
        return tableInfo;
    }

    public TableInfoDAO findBySchemaIdAndName(Session session, UUID schemaId, String name) {
        String hql = "FROM TableInfoDAO t WHERE t.schemaId = :schemaId AND t.name = :name";
        Query<TableInfoDAO> query = session.createQuery(hql, TableInfoDAO.class);
        query.setParameter("schemaId", schemaId);
        query.setParameter("name", name);
        LOGGER.debug("Finding table by schemaId: {} and name: {}", schemaId, name);
        return query.uniqueResult();
    }

    private String getTableFullName(TableInfo tableInfo) {
        return tableInfo.getCatalogName() + "." + tableInfo.getSchemaName() + "." + tableInfo.getName();
    }

    public UUID getSchemaId(Session session, String catalogName, String schemaName) {
        SchemaInfoDAO schemaInfo = repositories.getSchemaRepository().getSchemaDAO(session, catalogName, schemaName);
        if (schemaInfo == null) {
            throw new BaseException(ErrorCode.NOT_FOUND, "Schema not found: " + schemaName);
        }
        return schemaInfo.getId();
    }

    public ListTablesResponse listTables(
        String catalogName,
        String schemaName,
        Optional<Integer> maxResults,
        Optional<String> pageToken,
        Boolean omitProperties,
        Boolean omitColumns
    ) {
        try (Session session = sessionFactory.openSession()) {
            session.setDefaultReadOnly(true);
            Transaction tx = session.beginTransaction();
            try {
                UUID schemaId = getSchemaId(session, catalogName, schemaName);
                ListTablesResponse response = listTables(
                    session,
                    schemaId,
                    catalogName,
                    schemaName,
                    maxResults,
                    pageToken,
                    omitProperties,
                    omitColumns
                );
                tx.commit();
                return response;
            } catch (Exception e) {
                if (tx != null && tx.getStatus().canRollback()) {
                    tx.rollback();
                }
                throw e;
            }
        }
    }

    public ListTablesResponse listTables(
        Session session,
        UUID schemaId,
        String catalogName,
        String schemaName,
        Optional<Integer> maxResults,
        Optional<String> pageToken,
        Boolean omitProperties,
        Boolean omitColumns
    ) {
        List<TableInfoDAO> tableInfoDAOList = LISTING_HELPER.listEntity(session, maxResults, pageToken, schemaId);
        String nextPageToken = LISTING_HELPER.getNextPageToken(tableInfoDAOList, maxResults);
        List<TableInfo> result = new ArrayList<>();
        for (TableInfoDAO tableInfoDAO : tableInfoDAOList) {
            TableInfo tableInfo = tableInfoDAO.toTableInfo(!omitColumns);
            if (!omitProperties) {
                RepositoryUtils.attachProperties(tableInfo, tableInfo.getTableId(), Constants.TABLE, session);
            }
            tableInfo.setCatalogName(catalogName);
            tableInfo.setSchemaName(schemaName);
            result.add(tableInfo);
        }
        return new ListTablesResponse().tables(result).nextPageToken(nextPageToken);
    }

    // New method to search tables by properties
    public ListTablesResponse searchTables(
        String catalogName,
        String schemaName,
        String searchText,
        Optional<Integer> maxResults,
        Optional<String> pageToken
    ) {
        try (Session session = sessionFactory.openSession()) {
            session.setDefaultReadOnly(true);
            Transaction tx = session.beginTransaction();
            try {
                UUID schemaId = getSchemaId(session, catalogName, schemaName);

                // Get all tables with properties
                List<TableInfoDAO> tableInfoDAOList = LISTING_HELPER.listEntity(session, maxResults, pageToken, schemaId);
                String nextPageToken = LISTING_HELPER.getNextPageToken(tableInfoDAOList, maxResults);

                // Filter tables based on property search
                List<TableInfo> result = new ArrayList<>();
                for (TableInfoDAO tableInfoDAO : tableInfoDAOList) {
                    TableInfo tableInfo = tableInfoDAO.toTableInfo(true); // Include columns
                    RepositoryUtils.attachProperties(tableInfo, tableInfo.getTableId(), Constants.TABLE, session);

                    Map<String, String> properties = tableInfo.getProperties();
                    if (properties != null && !properties.isEmpty()) {
                        boolean matches = properties
                            .entrySet()
                            .stream()
                            .anyMatch(entry ->
                                entry.getKey().toLowerCase().contains(searchText.toLowerCase()) ||
                                entry.getValue().toLowerCase().contains(searchText.toLowerCase())
                            );

                        if (matches) {
                            tableInfo.setCatalogName(catalogName);
                            tableInfo.setSchemaName(schemaName);
                            result.add(tableInfo);
                        }
                    }
                }

                tx.commit();
                return new ListTablesResponse().tables(result).nextPageToken(nextPageToken);
            } catch (Exception e) {
                if (tx != null && tx.getStatus().canRollback()) {
                    tx.rollback();
                }
                throw e;
            }
        }
    }

    public Map<String, String> getAllTableProperties(
        String catalogName,
        String schemaName,
        Optional<Integer> maxResults,
        Optional<String> pageToken
    ) {
        try (Session session = sessionFactory.openSession()) {
            session.setDefaultReadOnly(true);
            Transaction tx = session.beginTransaction();
            try {
                // Get schema ID for the catalog and schema
                UUID schemaId = getSchemaId(session, catalogName, schemaName);

                // Fetch all tables using the existing listing helper
                List<TableInfoDAO> tableInfoDAOList = LISTING_HELPER.listEntity(session, maxResults, pageToken, schemaId);

                // Aggregate all properties into a single map
                Map<String, String> allProperties = tableInfoDAOList
                    .stream()
                    .flatMap(tableInfoDAO -> {
                        // Fetch properties for each table
                        List<PropertyDAO> properties = PropertyRepository.findProperties(session, tableInfoDAO.getId(), Constants.TABLE);
                        return properties.stream().map(prop -> Map.entry(prop.getKey(), prop.getValue()));
                    })
                    .collect(
                        Collectors.toMap(
                            Map.Entry::getKey, // Property key
                            Map.Entry::getValue, // Property value
                            (existing, replacement) -> existing // Keep first value for duplicate keys
                        )
                    );

                tx.commit();
                return allProperties;
            } catch (Exception e) {
                if (tx != null && tx.getStatus().canRollback()) {
                    tx.rollback();
                }
                LOGGER.error("Error fetching table properties for catalog: {} and schema: {}", catalogName, schemaName, e);
                throw e;
            }
        }
    }

    public void deleteTable(String fullName) {
        try (Session session = sessionFactory.openSession()) {
            Transaction tx = session.beginTransaction();
            String[] parts = fullName.split("\\.");
            if (parts.length != 3) {
                throw new BaseException(ErrorCode.INVALID_ARGUMENT, "Invalid table name: " + fullName);
            }
            String catalogName = parts[0];
            String schemaName = parts[1];
            String tableName = parts[2];
            try {
                UUID schemaId = getSchemaId(session, catalogName, schemaName);
                deleteTable(session, schemaId, tableName);
                tx.commit();
            } catch (RuntimeException e) {
                if (tx != null && tx.getStatus().canRollback()) {
                    tx.rollback();
                }
                throw e;
            }
        }
    }

    public void deleteTable(Session session, UUID schemaId, String tableName) {
        TableInfoDAO tableInfoDAO = findBySchemaIdAndName(session, schemaId, tableName);
        if (tableInfoDAO == null) {
            throw new BaseException(ErrorCode.NOT_FOUND, "Table not found: " + tableName);
        }
        if (TableType.MANAGED.getValue().equals(tableInfoDAO.getType())) {
            try {
                fileOperations.deleteDirectory(tableInfoDAO.getUrl());
            } catch (Throwable e) {
                LOGGER.error("Error deleting table directory: {}", tableInfoDAO.getUrl(), e);
            }
        }
        PropertyRepository.findProperties(session, tableInfoDAO.getId(), Constants.TABLE).forEach(session::remove);
        session.remove(tableInfoDAO);
    }
}
