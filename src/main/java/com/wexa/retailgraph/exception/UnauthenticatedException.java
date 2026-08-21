package com.wexa.retailgraph.exception;

/** Thrown by AuthInterceptor when a request to a protected API endpoint has no valid session. */
public class UnauthenticatedException extends RuntimeException {

    public UnauthenticatedException(String message) {
        super(message);
    }
}
