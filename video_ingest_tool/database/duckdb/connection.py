import duckdb
import os
import structlog

logger = structlog.get_logger(__name__)

class _InMemoryConnectionWrapper:
    """Wraps the actual in-memory connection to prevent close() by 'with' statements."""
    def __init__(self, actual_conn):
        self._actual_conn = actual_conn

    def __getattr__(self, name):
        # Delegate all attribute access to the actual connection
        return getattr(self._actual_conn, name)

    def close(self):
        # This is called by 'with ... as conn:' on exit.
        # We do nothing to keep the underlying cached connection open.
        logger.debug("InMemoryConnectionWrapper.close() called, but underlying connection is kept open.")
        pass

    def __enter__(self):
        # Allow the wrapper to be used in a 'with' statement directly if needed,
        # though get_db_connection returns the actual connection for the cache.
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close() # Call our no-op close

# Define the database file name and directory
DATABASE_DIR = "data"
DATABASE_NAME = "ai_ingest_local.duckdb"
DEFAULT_SCHEMA = "app_data"

def get_db_path() -> str:
    """Constructs the full path to the database file."""
    # Assuming the project root is the parent directory of 'video_ingest_tool'
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    db_dir_path = os.path.join(project_root, DATABASE_DIR)
    return os.path.join(db_dir_path, DATABASE_NAME)

def get_db_connection(db_path: str = None) -> "duckdb.DuckDBPyConnection":
    """
    Establishes a connection to the DuckDB database.
    Installs and loads required extensions (fts, vss).
    Sets the default search path.

    Args:
        db_path (str, optional): Path to the database file.
                                 If None, tries to get from Flask's current_app.config['DUCKDB_PATH'],
                                 then defaults to a persistent path in the project's data/ directory.

    Returns:
        duckdb.DuckDBPyConnection: An active DuckDB connection object.
    """
    final_db_path_determined = db_path # Start with the explicit db_path if provided

    # Attempt to use Flask app context for test connection or configured DUCKDB_PATH
    try:
        from flask import current_app
        if current_app:
            # PRIORITY 1: Use session-scoped test connection if available
            if current_app.config.get("TESTING") and \
               hasattr(current_app, 'extensions') and \
               '_duckdb_actual_test_conn' in current_app.extensions:
                
                actual_test_conn = current_app.extensions['_duckdb_actual_test_conn']
                # Basic check to see if the connection is alive
                try:
                    actual_test_conn.execute("SELECT 42;")
                    logger.debug("Using session-scoped actual test DB connection from app context via wrapper.")
                    return _InMemoryConnectionWrapper(actual_test_conn)
                except duckdb.ConnectionException as ce: # Handles if connection was somehow closed
                    logger.error(f"App-context test connection found but is closed/unusable: {ce}. This is unexpected. Will proceed to create new connection based on DUCKDB_PATH or default.")
                    # Let final_db_path_determined (which might be None or db_path) be re-evaluated or fall through.
                    # If DUCKDB_PATH is ':memory:', a new one will be made.

            # PRIORITY 2: Use DUCKDB_PATH from Flask app config if no specific test connection was used
            if final_db_path_determined is None and 'DUCKDB_PATH' in current_app.config:
                final_db_path_determined = current_app.config['DUCKDB_PATH']
                logger.debug(f"Using DUCKDB_PATH from Flask app config: {final_db_path_determined}")
    except ImportError: # Flask not available
        logger.debug("Flask not available during DB connection setup.")
    except RuntimeError: # Outside of application context
        logger.debug("Outside Flask app context during DB connection setup.")

    # If final_db_path_determined is still None, use the default file path
    if final_db_path_determined is None:
        final_db_path_determined = get_db_path()
        logger.debug(f"Using default DUCKDB_PATH: {final_db_path_determined}")
    
    # Now, final_db_path_determined holds the definitive path to connect to.
    # This will be a file path, or ":memory:" if configured for non-test in-memory use.
    # The test-specific shared :memory: connection is handled above and returns early.

    try:
        # Ensure the database directory exists for file-based DBs
        if final_db_path_determined != ":memory:":
            # Use final_db_path_determined for directory creation
            os.makedirs(os.path.dirname(final_db_path_determined), exist_ok=True)
        
        logger.info(f"Establishing new DuckDB connection to: {final_db_path_determined}")
        con = duckdb.connect(database=final_db_path_determined, read_only=False)

        # Load extensions for any newly created connection
        extensions_to_load = ["fts", "vss"]
        for ext_name in extensions_to_load:
            try:
                con.execute(f"INSTALL {ext_name};")
                logger.info(f"Installed DuckDB extension: {ext_name} for {final_db_path_determined}")
            except Exception: # More permissive for already installed
                logger.debug(f"DuckDB extension {ext_name} likely already installed for {final_db_path_determined}.")
                pass
            try:
                con.execute(f"LOAD {ext_name};")
                logger.info(f"Loaded DuckDB extension: {ext_name} for {final_db_path_determined}")
            except Exception as e_load:
                if "already loaded" in str(e_load).lower():
                    logger.debug(f"DuckDB extension {ext_name} already loaded for {final_db_path_determined}.")
                else:
                    logger.error(f"Failed to load extension {ext_name} for {final_db_path_determined}.", error=str(e_load))
                    raise
        
        # If this is a new :memory: connection (not the test session one), wrap it if it's meant to be shared via the old global cache.
        # However, the global _CACHED_IN_MEMORY_CONN is being phased out.
        # For now, if it's a :memory: path and not the test one, it's a fresh, non-shared instance.
        # If a wrapper is needed for non-test :memory: that might be used with 'with', this logic would need adjustment.
        # The current primary goal is to fix test isolation.
        
        return con
        
    except Exception as e:
        logger.error(f"Failed to connect to DuckDB or load extensions at {final_db_path_determined}", error=str(e))
        raise

if __name__ == "__main__":
    # Example usage and test
    logger.info("Attempting to establish DuckDB connection for testing...")
    try:
        connection = get_db_connection()
        if connection:
            logger.info("Test connection successful. DuckDB version:", connection.execute("SELECT version();").fetchone())
            
            # Verify extensions are loaded by trying to use a feature or checking pg_extensions
            try:
                # Example: Check if fts_main_table is a known entity (would fail if FTS not loaded properly)
                # This is a bit indirect. A direct check might be better if DuckDB offers it.
                # For now, successful load messages are the primary indicator.
                # connection.execute("DESCRIBE SELECT match_bm25(1, 'test');") # This would fail if no FTS index exists
                logger.info("FTS and VSS extensions assumed loaded based on execution flow.")
            except Exception as ext_e:
                logger.error("Failed to verify extension functionality", error=str(ext_e))
            
            connection.close()
            logger.info("Test connection closed.")
        else:
            logger.error("Test connection failed.")
    except Exception as e:
        logger.error("Error during connection test", error=str(e))