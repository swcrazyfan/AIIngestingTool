import duckdb
import structlog
# Removed unused import: from .connection import get_db_connection
# get_db_connection will be used by the main script or test runner

logger = structlog.get_logger(__name__)

APP_DATA_SCHEMA = "app_data"
PREFECT_SCHEMA = "prefect_orchestration" # Reserved for Prefect

def create_schemas(con: "duckdb.DuckDBPyConnection"):
    """Creates the necessary schemas if they don't exist."""
    try:
        con.execute(f"CREATE SCHEMA IF NOT EXISTS {APP_DATA_SCHEMA};")
        logger.info(f"Ensured schema '{APP_DATA_SCHEMA}' exists.")
        con.execute(f"CREATE SCHEMA IF NOT EXISTS {PREFECT_SCHEMA};")
        logger.info(f"Ensured schema '{PREFECT_SCHEMA}' exists for future Prefect use.")
    except Exception as e:
        logger.error("Failed to create schemas", error=str(e))
        raise

def create_clips_table(con: "duckdb.DuckDBPyConnection"):
    """Creates the 'clips' table in the app_data schema as per the final plan."""
    table_name = f"{APP_DATA_SCHEMA}.clips"
    try:
        con.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                id UUID PRIMARY KEY,
                local_path VARCHAR NOT NULL,
                file_name VARCHAR NOT NULL,
                file_checksum VARCHAR UNIQUE NOT NULL,
                file_size_bytes BIGINT NOT NULL,
                duration_seconds DOUBLE,
                created_at TIMESTAMP,
                processed_at TIMESTAMP,
                updated_at TIMESTAMP,
                width INTEGER,
                height INTEGER,
                frame_rate DOUBLE,
                codec VARCHAR,
                container VARCHAR,
                camera_make VARCHAR,
                camera_model VARCHAR,
                camera_details JSON,
                content_category VARCHAR,
                content_summary TEXT,
                content_tags VARCHAR[],
                searchable_content TEXT,
                full_transcript TEXT,
                transcript_preview VARCHAR,
                transcript_segments_json JSON,
                thumbnails VARCHAR[],
                primary_thumbnail_path VARCHAR,
                ai_selected_thumbnails_json JSON,
                technical_metadata JSON,
                audio_tracks JSON,
                subtitle_tracks JSON,
                full_ai_analysis_json JSON,
                summary_embedding FLOAT[1024],
                keyword_embedding FLOAT[1024],
                thumbnail_1_embedding FLOAT[768],
                thumbnail_2_embedding FLOAT[768],
                thumbnail_3_embedding FLOAT[768]
            );
        """)  # Correctly terminate the f-string here
        logger.info(f"Table '{table_name}' created or already exists.")
    except Exception as e: # Ensure except is properly aligned with try
        logger.error(f"Failed to create table '{table_name}'", error=str(e))
        raise

def create_indexes(con: "duckdb.DuckDBPyConnection"):
    """Creates FTS, HNSW, and other necessary indexes for the clips table."""
    logger.info("Attempting to create indexes for the clips table...")
    clips_table_fqn = f"{APP_DATA_SCHEMA}.clips"
    try:
        # FTS Index for clips table
        # Note: 'id' is the rowid column for FTS.
        # searchable_content, file_name, content_summary, transcript_preview, content_tags are indexed.
        con.execute(f"PRAGMA create_fts_index('{clips_table_fqn}', 'id', 'searchable_content', 'file_name', 'content_summary', 'transcript_preview', 'content_tags', overwrite=1);")
        logger.info(f"FTS index created for {clips_table_fqn}.")

        # HNSW (Vector) Indexes for clips table
        vector_columns_clips = [
            "summary_embedding", "keyword_embedding",
            "thumbnail_1_embedding", "thumbnail_2_embedding", "thumbnail_3_embedding"
        ]
        for col_name in vector_columns_clips:
            con.execute(f"CREATE INDEX IF NOT EXISTS idx_clips_{col_name.replace('_embedding','_vec')} ON {clips_table_fqn} USING HNSW ({col_name});")
            logger.info(f"HNSW index created for {clips_table_fqn}.{col_name}.")

        # Standard B-Tree Indexes for clips table
        con.execute(f"CREATE INDEX IF NOT EXISTS idx_clips_file_checksum ON {clips_table_fqn} (file_checksum);")
        logger.info(f"B-Tree index created for {clips_table_fqn}.file_checksum.")
        con.execute(f"CREATE INDEX IF NOT EXISTS idx_clips_created_at ON {clips_table_fqn} (created_at DESC);")
        logger.info(f"B-Tree index created for {clips_table_fqn}.created_at.")

    except Exception as e:
        logger.error("Failed to create indexes for clips table", error=str(e))
        raise

def initialize_schema(con: "duckdb.DuckDBPyConnection"):
    """Initializes the full database schema: creates schemas, the clips table, and indexes."""
    logger.info("Initializing database schema...")
    logger.info("Creating core schemas and the clips table...")
    con.begin()
    try:
        create_schemas(con)
        create_clips_table(con)
        con.commit()
        logger.info("Core schemas and clips table created and committed.")
    except Exception as e:
        con.rollback()
        logger.error("Core schema/clips table creation failed. Rolled back changes.", error=str(e))
        raise

    logger.info("Creating indexes for the clips table...")
    try:
        create_indexes(con) # Indexes are typically auto-committed or in their own transactions
        logger.info("Indexes for clips table created successfully.")
    except Exception as e:
        logger.error("Index creation for clips table failed.", error=str(e))
        # Depending on requirements, this might or might not be a critical failure.
        # For now, re-raise as tests might expect indexes.
        raise
    
    logger.info("Database schema initialization successfully completed.")

if __name__ == "__main__":
    # This part is for direct execution and testing of this script.
    # In the application, get_db_connection will be imported and used by other modules.
    from video_ingest_tool.database.duckdb.connection import get_db_connection

    logger.info("Running schema setup directly for testing...")
    db_connection = None
    try:
        db_connection = get_db_connection() # Gets a connection, usually to the default DB file
        initialize_schema(db_connection)
        logger.info("Schema setup script completed successfully.")
        
        # Example: Verify table creation
        result = db_connection.execute(f"SELECT table_name FROM information_schema.tables WHERE table_schema = '{APP_DATA_SCHEMA}' AND table_name = 'clips';").fetchone()
        if result:
            logger.info(f"Verification: Table 'clips' found in schema '{APP_DATA_SCHEMA}'.")
            # Verify columns (optional detailed check)
            # columns = db_connection.execute(f"PRAGMA table_info('{APP_DATA_SCHEMA!r}.clips');").fetchall() # Use !r for safety if schema name could have quotes
            # logger.info(f"Columns in clips table: {columns!r}")
        else:
            logger.error("Verification: Table 'clips' NOT found.")

    except Exception as e:
        logger.error("Error during direct schema setup", error=str(e))
    finally:
        if db_connection:
            db_connection.close()
            logger.info("Database connection closed.")