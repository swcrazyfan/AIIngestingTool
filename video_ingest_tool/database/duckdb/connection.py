import duckdb
import os
import structlog

logger = structlog.get_logger(__name__)

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
                                 Defaults to a path in the project's data/ directory.

    Returns:
        duckdb.DuckDBPyConnection: An active DuckDB connection object.
    """
    if db_path is None:
        db_path = get_db_path()

    # Ensure the database directory exists, but not for in-memory databases
    if db_path != ":memory:":
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

    try:
        con = duckdb.connect(database=db_path, read_only=False)
        logger.info(f"Successfully connected to DuckDB at {db_path}")

        # Install and load extensions
        # Using try-except for INSTALL as it might fail if already installed by another connection/process
        # LOAD is generally safe to call multiple times.
        extensions_to_load = ["fts", "vss"]
        for ext_name in extensions_to_load:
            try:
                con.execute(f"INSTALL {ext_name};")
                logger.info(f"Installed DuckDB extension: {ext_name}")
            except duckdb.IOException as e: # More specific exception for "already installed"
                 if "already installed" in str(e).lower():
                    logger.debug(f"DuckDB extension {ext_name} already installed.")
                 else:
                    logger.warning(f"Could not install DuckDB extension {ext_name} (may be fine if preloaded): {e}")
            except duckdb.CatalogException as e: # For "already loaded" on LOAD if INSTALL was skipped
                if "already loaded" in str(e).lower():
                    logger.debug(f"DuckDB extension {ext_name} already loaded.")
                else:
                    logger.warning(f"Catalog exception for DuckDB extension {ext_name}: {e}")
            except Exception as e: # Catch-all for other INSTALL issues
                logger.warning(f"Error installing DuckDB extension {ext_name}: {e}")

            try:
                con.execute(f"LOAD {ext_name};")
                logger.info(f"Loaded DuckDB extension: {ext_name}")
            except duckdb.CatalogException as e: # For "already loaded"
                if "already loaded" in str(e).lower():
                    logger.debug(f"DuckDB extension {ext_name} already loaded.")
                else:
                    # If it's a CatalogException but not "already loaded", it's a problem.
                    logger.error(f"CatalogException while loading DuckDB extension {ext_name} (not 'already loaded'): {e}")
                    raise # Re-raise critical load errors
            except Exception as e: # Catch-all for other LOAD issues
                logger.error(f"Unexpected error loading DuckDB extension {ext_name}: {e}")
                raise # Re-raise critical load errors


        # Set default search path (schema)
        # Schemas will be created by the schema.py script
        # con.execute(f"SET search_path = '{DEFAULT_SCHEMA}';")
        # logger.info(f"Set default search path to '{DEFAULT_SCHEMA}'")
        # Note: Setting search_path might be better done after schema creation or per session need.
        # For now, we ensure extensions are loaded. Schema creation will handle CREATE SCHEMA.

        return con
    except Exception as e:
        logger.error(f"Failed to connect to DuckDB or load extensions at {db_path}", error=str(e))
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