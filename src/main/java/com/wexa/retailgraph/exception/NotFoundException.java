package com.wexa.retailgraph.exception;

/** Thrown when a requested graph entity (product, customer, category, ...) does not exist. */
public class NotFoundException extends RuntimeException {

    public NotFoundException(String message) {
        super(message);
    }
}
