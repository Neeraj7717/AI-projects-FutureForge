import logging

def setup_logger(name=None, level=logging.INFO):
    """
    Configure and return a logger with consistent formatting.
    
    Args:
        name (str, optional): Logger name. If None, returns the root logger.
        level (int, optional): Logging level. Default is INFO.
        
    Returns:
        logging.Logger: Configured logger instance
    """
    # Get logger
    logger = logging.getLogger(name)
    
    # Only configure if not already configured
    if not logger.hasHandlers():
        logger.setLevel(level)
        
        # Create formatter
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        
        # Create console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # Prevent propagation to avoid duplicate logs
        logger.propagate = False
    
    return logger

# Configure root logger only once
root_logger = setup_logger()