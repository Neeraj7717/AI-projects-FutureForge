package com.wexa.retailgraph.exception;

/** Thrown when CognoDB cannot be reached or a query fails against it. */
public class DatabaseUnavailableException extends RuntimeException {

    public DatabaseUnavailableException(String message, Throwable cause) {
        super(message, cause);
    }
}
