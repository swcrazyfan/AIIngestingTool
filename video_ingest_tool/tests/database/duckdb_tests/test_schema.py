import pytest
import duckdb
from video_ingest_tool.database.duckdb.connection import get_db_connection
from video_ingest_tool.database.duckdb.schema import initialize_schema, APP_DATA_SCHEMA, PREFECT_SCHEMA

@pytest.fixture(scope="function")
def db_connection():
    """Fixture to provide an initialized in-memory DuckDB connection for schema tests."""
    con = get_db_connection(db_path=":memory:")
    initialize_schema(con) # Initialize the schema for each test function
    yield con
    con.close()

def test_schemas_created(db_connection):
    """Test if the app_data and prefect_orchestration schemas are created."""
    schemas = db_connection.execute("SELECT schema_name FROM information_schema.schemata;").fetchall()
    schema_names = [s[0] for s in schemas]
    assert APP_DATA_SCHEMA in schema_names, f"Schema '{APP_DATA_SCHEMA}' should be created."
    assert PREFECT_SCHEMA in schema_names, f"Schema '{PREFECT_SCHEMA}' should be created."

def test_tables_created(db_connection):
    """Test if all application tables are created in the app_data schema."""
    tables_query = f"SELECT table_name FROM information_schema.tables WHERE table_schema = '{APP_DATA_SCHEMA}';"
    tables = db_connection.execute(tables_query).fetchall()
    table_names = [t[0] for t in tables]
    
    expected_tables = ["clips", "segments", "analysis", "transcripts"]
    for table in expected_tables:
        assert table in table_names, f"Table '{table}' should be created in schema '{APP_DATA_SCHEMA}'."

def get_table_columns_info(con, table_name, schema_name=APP_DATA_SCHEMA):
    """Helper to get column names and types for a table."""
    query = f"""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_schema = '{schema_name}' AND table_name = '{table_name}'
        ORDER BY ordinal_position;
    """
    return {row[0]: row[1] for row in con.execute(query).fetchall()}

def test_clips_table_columns_and_types(db_connection):
    """Test key columns and their types in the 'clips' table."""
    columns_info = get_table_columns_info(db_connection, "clips")
    
    expected_columns = {
        "id": "UUID",
        "file_checksum": "VARCHAR",
        "summary_embedding": "FLOAT[1024]",
        "keyword_embedding": "FLOAT[1024]",
        "thumbnail_1_embedding": "FLOAT[768]",
        "searchable_content": "VARCHAR",
        "content_tags": "VARCHAR[]",
        "technical_metadata": "JSON"
    }
    
    for col, col_type in expected_columns.items():
        assert col in columns_info, f"Column '{col}' should exist in 'clips' table."
        assert columns_info[col].upper() == col_type.upper(), \
            f"Column '{col}' in 'clips' should have type '{col_type}', found '{columns_info[col]}'."

def test_segments_table_columns_and_types(db_connection):
    """Test key columns and their types in the 'segments' table."""
    columns_info = get_table_columns_info(db_connection, "segments")
    expected_columns = {
        "id": "UUID",
        "clip_id": "UUID",
        "segment_content": "VARCHAR", # Changed from TEXT to VARCHAR as DuckDB TEXT is an alias for VARCHAR
        "segment_embedding": "FLOAT[1024]"
    }
    for col, col_type in expected_columns.items():
        assert col in columns_info, f"Column '{col}' should exist in 'segments' table."
        assert columns_info[col].upper() == col_type.upper(), \
            f"Column '{col}' in 'segments' should have type '{col_type}', found '{columns_info[col]}'."

def test_analysis_table_columns_and_types(db_connection):
    """Test key columns and their types in the 'analysis' table."""
    columns_info = get_table_columns_info(db_connection, "analysis")
    expected_columns = {
        "id": "UUID",
        "clip_id": "UUID",
        "ai_analysis": "JSON"
    }
    for col, col_type in expected_columns.items():
        assert col in columns_info, f"Column '{col}' should exist in 'analysis' table."
        assert columns_info[col].upper() == col_type.upper(), \
            f"Column '{col}' in 'analysis' should have type '{col_type}', found '{columns_info[col]}'."

def test_transcripts_table_columns_and_types(db_connection):
    """Test key columns and their types in the 'transcripts' table."""
    columns_info = get_table_columns_info(db_connection, "transcripts")
    expected_columns = {
        "clip_id": "UUID",
        "full_text": "VARCHAR", # Changed from TEXT to VARCHAR
        "segments": "JSON",
        "transcript_embedding": "FLOAT[1024]"
    }
    for col, col_type in expected_columns.items():
        assert col in columns_info, f"Column '{col}' should exist in 'transcripts' table."
        assert columns_info[col].upper() == col_type.upper(), \
            f"Column '{col}' in 'transcripts' should have type '{col_type}', found '{columns_info[col]}'."

def test_indexes_created(db_connection):
    """Test if FTS, HNSW, and B-Tree indexes are created."""
    # Query for index_name, table_name, and the sql definition.
    # We will infer type from the sql string as 'index_type' can be unreliable.
    indexes_result = db_connection.execute(f"SELECT index_name, table_name, sql FROM duckdb_indexes() WHERE schema_name = '{APP_DATA_SCHEMA}';").fetchall()
    index_map = {(row[1], row[0]): {"sql": row[2]} for row in indexes_result} # (table_name, index_name) -> {"sql": sql_string}

    # FTS (Note: PRAGMA create_fts_index names are usually fts_main_<schema>_<table>)
    # DuckDB's duckdb_indexes() might not list FTS indexes created by PRAGMA in a straightforward way.
    # We'll check for HNSW and B-Tree, and assume FTS is created if PRAGMA didn't error.
    # A more robust FTS check would be to try a simple FTS query on an empty table.
    
    # HNSW Indexes
    expected_hnsw_indexes = {
        ("clips", "idx_clips_summary_vec"): "HNSW",
        ("clips", "idx_clips_keyword_vec"): "HNSW",
        ("clips", "idx_clips_thumbnail_1_vec"): "HNSW",
        ("clips", "idx_clips_thumbnail_2_vec"): "HNSW",
        ("clips", "idx_clips_thumbnail_3_vec"): "HNSW",
        ("segments", "idx_segments_embedding_vec"): "HNSW",
        ("transcripts", "idx_transcripts_embedding_vec"): "HNSW",
    }
    for (table, idx_name), _ in expected_hnsw_indexes.items(): # idx_type is HNSW
        assert (table, idx_name) in index_map, f"HNSW Index '{idx_name}' on table '{table}' should exist."
        index_sql = index_map[(table, idx_name)]["sql"]
        assert "USING HNSW" in index_sql.upper(), f"Index '{idx_name}' on table '{table}' should be HNSW (found 'USING HNSW' in SQL). SQL: {index_sql}"

    # B-Tree Indexes
    expected_btree_indexes = {
        ("clips", "idx_clips_file_checksum"): "ART", # ART is DuckDB's adaptive radix tree index, default for B-Tree like
        ("clips", "idx_clips_created_at"): "ART",
        ("segments", "idx_segments_clip_id"): "ART",
    }
    for (table, idx_name), _ in expected_btree_indexes.items(): # idx_type is ART/B-Tree
        assert (table, idx_name) in index_map, f"B-Tree Index '{idx_name}' on table '{table}' should exist."
        index_sql = index_map[(table, idx_name)]["sql"]
        # For B-Tree/ART, the SQL might be simple or mention ART.
        # We primarily check it's not HNSW and it exists.
        assert "USING HNSW" not in index_sql.upper(), f"Index '{idx_name}' on table '{table}' should be B-Tree/ART, not HNSW. SQL: {index_sql}"

    # Verify FTS index creation for app_data.clips by attempting a simple FTS query.
    # This is more robust than checking for internal FTS table names.
    try:
        # Attempt an FTS query on 'searchable_content', one of the indexed columns.
        # If the FTS index on 'app_data.clips' is set up, this query should execute
        # without a BinderException or InvalidInputException, even if the table is empty.
        # The function is match_bm25(input_id, query_string, ...), qualified by FTS virtual table name.
        # 'id' is the input_id for the 'clips' table FTS index.
        # If 'fields' is NULL (default), it searches all indexed text columns.
        db_connection.execute(f"""
            SELECT id FROM {APP_DATA_SCHEMA}.clips
            WHERE fts_app_data_clips.match_bm25(id, 'test_query_value') LIMIT 1;
        """).fetchall()
        # If no exception, FTS index is considered functional for this table.
    except (duckdb.BinderException, duckdb.InvalidInputException, duckdb.CatalogException) as e: # Added CatalogException here
        pytest.fail(
            f"FTS index for '{APP_DATA_SCHEMA}.clips' (using 'id' as input_id) "
            f"does not seem to be working. FTS query failed: {e}"
        )
    except Exception as e: # Catch-all for other unexpected issues during the FTS test
         pytest.fail(
            f"An unexpected error occurred during FTS functionality test for '{APP_DATA_SCHEMA}.clips': {e}"
        )


def test_foreign_keys_created(db_connection):
    """Test if foreign keys are correctly established."""
    # segments.clip_id -> clips.id
    constraints_seg = db_connection.execute(f"""
        SELECT constraint_type, table_name, constraint_column_names
        FROM duckdb_constraints()
        WHERE schema_name = '{APP_DATA_SCHEMA}' AND table_name = 'segments' AND constraint_type = 'FOREIGN KEY'
    """).fetchall()
    assert any('clip_id' in c[2] for c in constraints_seg), "segments.clip_id should have a FOREIGN KEY constraint involving 'clip_id'."

    # analysis.clip_id -> clips.id
    constraints_analysis = db_connection.execute(f"""
        SELECT constraint_type, table_name, constraint_column_names
        FROM duckdb_constraints()
        WHERE schema_name = '{APP_DATA_SCHEMA}' AND table_name = 'analysis' AND constraint_type = 'FOREIGN KEY'
    """).fetchall()
    assert any('clip_id' in c[2] for c in constraints_analysis), "analysis.clip_id should have a FOREIGN KEY constraint involving 'clip_id'."

    # transcripts.clip_id -> clips.id
    constraints_transcripts = db_connection.execute(f"""
        SELECT constraint_type, table_name, constraint_column_names
        FROM duckdb_constraints()
        WHERE schema_name = '{APP_DATA_SCHEMA}' AND table_name = 'transcripts' AND constraint_type = 'FOREIGN KEY'
    """).fetchall()
    assert any('clip_id' in c[2] for c in constraints_transcripts), "transcripts.clip_id should have a FOREIGN KEY constraint involving 'clip_id'."